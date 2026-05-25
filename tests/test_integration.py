"""
Integration Tests — Full Pipeline
Owner: Project Lead

Tests the end-to-end flow: Triage → Policy → Resolution → Communication.
Run after all specialist agent branches have been merged to develop.

Run:
    pytest tests/test_integration.py -v
"""

import importlib.util
import json
import os
import site
import sys

# Ensure site-packages takes priority over the local agents/ package
# so the openai-agents SDK's `agents` module is found first.
site_packages = [p for p in site.getsitepackages() if "site-packages" in p]
for sp in site_packages:
    if sp in sys.path:
        sys.path.remove(sp)
        sys.path.insert(0, sp)

import pytest

# Load resolution_agent via importlib to avoid shadowing between the
# local agents/ package and the SDK's agents module.
_project_root = os.path.dirname(os.path.dirname(__file__))
_spec = importlib.util.spec_from_file_location(
    "resolution_agent",
    os.path.join(_project_root, "agents", "resolution_agent.py"),
)
ra = importlib.util.module_from_spec(_spec)
sys.modules["resolution_agent"] = ra
_spec.loader.exec_module(ra)
resolve_return = ra.resolve_return
ResolutionOutput = ra.ResolutionOutput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_return_message():
    return {
        "customer_id": "cust_001",
        "channel": "web_chat",
        "raw_message": "I want to return my order #12345. It arrived damaged.",
    }


@pytest.fixture
def sample_tracking_message():
    return {
        "customer_id": "cust_002",
        "channel": "email",
        "raw_message": "Where is my order? It's been 10 days and I haven't received it.",
    }


@pytest.fixture
def sample_escalation_message():
    return {
        "customer_id": "cust_003",
        "channel": "web_chat",
        "raw_message": "This is absolutely unacceptable. I'm going to take legal action if this isn't resolved NOW.",
    }


# ---------------------------------------------------------------------------
# resolve_return — determinisitic orchestrator tests
# ---------------------------------------------------------------------------


async def _mock_success(**overrides) -> dict:
    return {"success": True, "error": None, **overrides}


async def _mock_failure(error: str = "Tool error") -> dict:
    return {"success": False, "error": error}


@pytest.mark.asyncio
async def test_resolve_return_reject():
    """recommended_action='reject' returns rejected without calling tools."""
    output = await resolve_return(
        {"recommended_action": "reject", "eligible": True,
         "reason": "Item is final sale"},
    )
    assert output.resolution_action == "rejected"
    assert "final sale" in output.reason
    assert output.error is None
    assert output.human_approval_required is False


@pytest.mark.asyncio
async def test_resolve_return_not_eligible():
    """A not-eligible policy decision returns rejected without calling tools."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_replacement(*args):
        raise AssertionError("No tool should be called for non-eligible")
    monkeypatch.setattr(ra, "_execute_replacement", mock_replacement)

    output = await resolve_return(
        {"recommended_action": "replacement", "eligible": False,
         "reason": "Return window expired"},
        order_id="ORD-001",
    )

    assert output.resolution_action == "rejected"
    assert "expired" in output.reason
    assert output.error is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_policy_error():
    """A policy decision with error field returns error without calling tools."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_replacement(*args):
        raise AssertionError("No tool should be called after policy error")
    monkeypatch.setattr(ra, "_execute_replacement", mock_replacement)

    output = await resolve_return(
        {"recommended_action": "replacement", "eligible": True,
         "error": "Policy engine unavailable"},
        order_id="ORD-001",
    )

    assert output.resolution_action == "error"
    assert "Policy engine unavailable" in output.reason

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_escalate():
    """recommended_action='escalate' returns escalated without calling tools."""
    output = await resolve_return(
        {"recommended_action": "escalate", "eligible": True,
         "reason": "Customer requested manager"},
    )
    assert output.resolution_action == "escalated"
    assert "manager" in output.reason
    assert output.human_approval_required is False


@pytest.mark.asyncio
async def test_resolve_return_replacement_success():
    """Successful replacement returns replacement_created with order ID."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_replacement(order_id):
        return {"success": True, "replacement_order_id": "REP-001",
                "estimated_delivery": "2026-06-01T00:00:00Z", "error": None}
    monkeypatch.setattr(ra, "_execute_replacement", mock_replacement)

    output = await resolve_return(
        {"recommended_action": "replacement", "eligible": True},
        order_id="ORD-001",
    )

    assert output.resolution_action == "replacement_created"
    assert output.replacement_order_id == "REP-001"
    assert output.estimated_delivery == "2026-06-01T00:00:00Z"
    assert output.error is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_replacement_failure():
    """Failed replacement returns replacement_failed with error."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_replacement(order_id):
        return {"success": False, "error": "OMS API returned HTTP 500"}
    monkeypatch.setattr(ra, "_execute_replacement", mock_replacement)

    output = await resolve_return(
        {"recommended_action": "replacement", "eligible": True},
        order_id="ORD-001",
    )

    assert output.resolution_action == "replacement_failed"
    assert "OMS API" in output.error
    assert output.replacement_order_id == ""

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_refund_success():
    """Successful refund returns refund_completed with transaction_id."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_refund(order_id, amount, method):
        return {"success": True, "transaction_id": "re_stripe_123",
                "refund_amount": amount, "error": None}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=50.0, payment_method="stripe",
    )

    assert output.resolution_action == "refund_completed"
    assert output.transaction_id == "re_stripe_123"
    assert output.refund_amount == 50.0
    assert output.error is None
    assert output.human_approval_required is False

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_refund_with_label_success():
    """Successful refund + label returns refund_completed with label fields."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_refund(order_id, amount, method):
        return {"success": True, "transaction_id": "re_456",
                "refund_amount": amount, "error": None}

    async def mock_label(order_id, carrier):
        return {"success": True, "label_url": "https://fedex.com/label.pdf",
                "tracking_number": "FDX789", "carrier": "fedex", "error": None}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)
    monkeypatch.setattr(ra, "_execute_label", mock_label)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=25.0, payment_method="stripe",
        carrier="fedex", label_needed=True,
    )

    assert output.resolution_action == "refund_completed"
    assert output.transaction_id == "re_456"
    assert output.refund_amount == 25.0
    assert output.label_url == "https://fedex.com/label.pdf"
    assert output.tracking_number == "FDX789"
    assert output.carrier == "fedex"
    assert output.error is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_refund_failure():
    """Failed refund returns refund_failed without calling label."""
    monkeypatch = pytest.MonkeyPatch()
    label_called = False

    async def mock_refund(order_id, amount, method):
        return {"success": False, "error": "Stripe API returned HTTP 500"}

    async def mock_label(*args):
        nonlocal label_called
        label_called = True
        return {"success": True}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)
    monkeypatch.setattr(ra, "_execute_label", mock_label)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=50.0, payment_method="stripe",
        label_needed=True,
    )

    assert output.resolution_action == "refund_failed"
    assert "Stripe API" in output.error
    assert output.transaction_id == ""
    assert output.label_url == ""
    assert label_called is False

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_guardrail_escalation():
    """Guardrail signal escalates without calling label."""
    monkeypatch = pytest.MonkeyPatch()
    label_called = False

    async def mock_refund(order_id, amount, method):
        return {"success": False, "human_approval_required": True,
                "error": "human_approval_required"}

    async def mock_label(*args):
        nonlocal label_called
        label_called = True
        return {"success": True}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)
    monkeypatch.setattr(ra, "_execute_label", mock_label)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=600.0, payment_method="stripe",
        label_needed=True,
    )

    assert output.resolution_action == "escalated"
    assert output.human_approval_required is True
    assert output.refund_amount == 600.0
    assert label_called is False

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_label_not_after_guardrail():
    """create_return_label is never called after guardrail escalation."""
    monkeypatch = pytest.MonkeyPatch()
    label_called = False

    async def mock_refund(order_id, amount, method):
        return {"success": False, "human_approval_required": True, "error": "cap"}

    async def mock_label(*args):
        nonlocal label_called
        label_called = True
        return {"success": True}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)
    monkeypatch.setattr(ra, "_execute_label", mock_label)

    await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=600.0, payment_method="stripe",
        label_needed=True,
    )

    assert label_called is False

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_label_not_after_refund_failure():
    """create_return_label is never called after refund failure."""
    monkeypatch = pytest.MonkeyPatch()
    label_called = False

    async def mock_refund(order_id, amount, method):
        return {"success": False, "error": "API error"}

    async def mock_label(*args):
        nonlocal label_called
        label_called = True
        return {"success": True}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)
    monkeypatch.setattr(ra, "_execute_label", mock_label)

    await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=50.0, payment_method="stripe",
        label_needed=True,
    )

    assert label_called is False

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_unknown_action():
    """An unknown recommended_action returns error."""
    output = await resolve_return(
        {"recommended_action": "bogus_action", "eligible": True},
    )
    assert output.resolution_action == "error"
    assert "bogus_action" in output.reason


@pytest.mark.asyncio
async def test_resolve_return_malformed_tool_result():
    """A tool result missing expected fields is handled gracefully."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_refund(order_id, amount, method):
        return {"success": True}
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=50.0, payment_method="stripe",
    )

    assert output.resolution_action == "refund_completed"
    assert output.transaction_id == ""
    assert output.refund_amount == 50.0

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_tool_exception_isolation():
    """_execute_refund catches exceptions from _call_tool."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_call_tool(*args, **kwargs):
        raise RuntimeError("Unexpected crash in tool")
    monkeypatch.setattr(ra, "_call_tool", mock_call_tool)

    result = await ra._execute_refund("ORD-001", 50.0, "stripe")

    assert result["success"] is False
    assert "Unexpected crash" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_resolve_return_top_level_exception():
    """Top-level safety net catches unexpected exceptions from tool mocks."""
    monkeypatch = pytest.MonkeyPatch()

    async def mock_refund(*args):
        raise RuntimeError("Unhandled crash in mock")
    monkeypatch.setattr(ra, "_execute_refund", mock_refund)

    output = await resolve_return(
        {"recommended_action": "refund", "eligible": True},
        order_id="ORD-001", amount_usd=50.0, payment_method="stripe",
    )

    assert output.resolution_action == "error"
    assert "Unhandled crash" in output.reason

    monkeypatch.undo()
