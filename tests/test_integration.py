"""
Integration Tests — Phase 1
Owner: Project Lead

Tests the check_return_policy tool, triage agent tools (tracking_lookup,
faq_lookup), and fixture data integrity.

Run:
    pytest tests/test_integration.py -v
"""

import importlib.util
import json
import os
import site
import sys

import pytest

# ── Step 1: Load local agents package FIRST ──
# This triggers the re-export strategy in agents/__init__.py, which makes
# the local package a superset of the SDK's agents module (with __path__
# including both the SDK directory and the local directory).  Submodules
# like triage_orchestrator are then discoverable regardless of sys.path
# ordering later.
import agents

# ── Step 2: Put site-packages first ──
# So any subsequent direct SDK module lookups favour the installed SDK.
site_packages = [p for p in site.getsitepackages() if "site-packages" in p]
for sp in site_packages:
    if sp in sys.path:
        sys.path.remove(sp)
        sys.path.insert(0, sp)

# ── Step 3: Load resolution_agent via importlib ──
# (Still needed because the importlib approach avoids the local agents/
#  package entirely when the function is imported — but now the agents
#  module is already cached by Step 1.)
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

from tools.policy_tools import check_return_policy_impl as check_return_policy

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


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

# Fixture loaders
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def orders() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "orders.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def customers() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "customers.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def messages() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "messages.json")) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def resolutions() -> list[dict]:
    with open(os.path.join(_FIXTURE_DIR, "resolutions.json")) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Fixture integrity
# ---------------------------------------------------------------------------


class TestFixtureIntegrity:
    def test_orders_have_required_fields(self, orders: list[dict]) -> None:
        required = {"order_id", "customer_id", "days_since_purchase", "items", "status"}
        for order in orders:
            missing = required - set(order.keys())
            assert not missing, f"Order {order['order_id']} missing fields: {missing}"

    def test_customers_have_required_fields(self, customers: list[dict]) -> None:
        required = {"customer_id", "name", "loyalty_tier", "fraud_flag", "order_history"}
        for cust in customers:
            missing = required - set(cust.keys())
            assert not missing, f"Customer {cust['customer_id']} missing fields: {missing}"

    def test_messages_have_required_fields(self, messages: list[dict]) -> None:
        required = {"message_id", "customer_id", "raw_message", "expected_intent", "expected_route"}
        for msg in messages:
            missing = required - set(msg.keys())
            assert not missing, f"Message {msg['message_id']} missing fields: {missing}"

    def test_resolutions_have_required_fields(self, resolutions: list[dict]) -> None:
        required = {"resolution_id", "message_id", "customer_id", "expected_agent_chain"}
        for res in resolutions:
            missing = required - set(res.keys())
            assert not missing, f"Resolution {res['resolution_id']} missing fields: {missing}"

    def test_all_customer_ids_in_orders_exist(self, orders: list[dict], customers: list[dict]) -> None:
        customer_ids = {c["customer_id"] for c in customers}
        for order in orders:
            assert order["customer_id"] in customer_ids, (
                f"Order {order['order_id']} references unknown customer {order['customer_id']}"
            )

    def test_all_message_customer_ids_exist(self, messages: list[dict], customers: list[dict]) -> None:
        customer_ids = {c["customer_id"] for c in customers}
        for msg in messages:
            assert msg["customer_id"] in customer_ids, (
                f"Message {msg['message_id']} references unknown customer {msg['customer_id']}"
            )

    def test_all_resolution_message_ids_exist(self, resolutions: list[dict], messages: list[dict]) -> None:
        message_ids = {m["message_id"] for m in messages}
        for res in resolutions:
            assert res["message_id"] in message_ids, (
                f"Resolution {res['resolution_id']} references unknown message {res['message_id']}"
            )

    def test_intents_are_valid(self, messages: list[dict]) -> None:
        valid_intents = {"return_request", "order_status", "billing_dispute", "general_inquiry", "edge_case_escalate"}
        for msg in messages:
            assert msg["expected_intent"] in valid_intents, (
                f"Message {msg['message_id']} has invalid intent {msg['expected_intent']}"
            )


# ---------------------------------------------------------------------------
# check_return_policy tool
# ---------------------------------------------------------------------------


class TestCheckReturnPolicy:
    @pytest.mark.asyncio
    async def test_eligible_within_window(self) -> None:
        result = await check_return_policy("ord_1002", "cust_001")
        assert result["eligible"] is True
        assert result["recommended_action"] == "refund"
        assert result["fraud_signal"] is False
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_ineligible_outside_window(self) -> None:
        result = await check_return_policy("ord_1001", "cust_001")
        assert result["eligible"] is False
        assert result["recommended_action"] == "reject"
        assert "return window" in result["reason"].lower()
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_ineligible_excluded_category(self) -> None:
        result = await check_return_policy("ord_2002", "cust_002")
        assert result["eligible"] is False
        assert result["recommended_action"] == "reject"
        assert result["item_category"] == "digital_goods"
        assert result["exclusion_reason"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_ineligible_fraud_flag(self) -> None:
        result = await check_return_policy("ord_4003", "cust_004")
        assert result["eligible"] is False
        assert result["recommended_action"] == "escalate"
        assert result["fraud_signal"] is True
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_ineligible_final_sale(self) -> None:
        result = await check_return_policy("ord_6001", "cust_006")
        assert result["eligible"] is False
        assert result["recommended_action"] == "reject"
        assert "final_sale" in (result.get("exclusion_reason") or "").lower() or "final" in result["reason"].lower()
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_eligible_mid_value_clean_account(self) -> None:
        result = await check_return_policy("ord_5002", "cust_005")
        assert result["eligible"] is True
        assert result["recommended_action"] == "refund"
        assert result["fraud_signal"] is False
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_unknown_order_returns_ineligible(self) -> None:
        result = await check_return_policy("ord_does_not_exist", "cust_001")
        assert result["eligible"] is False
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_unknown_customer_returns_ineligible(self) -> None:
        result = await check_return_policy("ord_1002", "cust_unknown")
        assert result["eligible"] is False
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_eligible_high_value(self) -> None:
        result = await check_return_policy("ord_3004", "cust_003")
        assert result["eligible"] is True
        assert result["recommended_action"] == "refund"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_return_schema_matches_spec(self) -> None:
        result = await check_return_policy("ord_1002", "cust_001")
        expected_keys = {
            "eligible", "success", "reason", "recommended_action",
            "return_window_days", "days_since_purchase", "item_category",
            "exclusion_reason", "fraud_signal", "error",
        }
        assert set(result.keys()) == expected_keys, f"Extra/missing keys: {set(result.keys()) ^ expected_keys}"


# ---------------------------------------------------------------------------
# tracking_lookup tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tracking_lookup_found() -> None:
    from agents.triage_orchestrator import tracking_lookup_impl as tracking_lookup

    result = await tracking_lookup("ord_1001")
    assert result["success"] is True
    assert result["found"] is True
    assert result["status"] == "delivered"
    assert result["carrier"] == "fedex"


@pytest.mark.asyncio
async def test_tracking_lookup_not_found() -> None:
    from agents.triage_orchestrator import tracking_lookup_impl as tracking_lookup

    result = await tracking_lookup("ord_does_not_exist")
    assert result["success"] is False
    assert result["found"] is False
    assert result["error"] is not None


# ---------------------------------------------------------------------------
# faq_lookup tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_faq_lookup_matches_keyword() -> None:
    from agents.triage_orchestrator import faq_lookup_impl as faq_lookup

    result = await faq_lookup("What is your return window?")
    assert result["success"] is True
    assert result["matched_keyword"] is not None
    assert result["error"] is None


@pytest.mark.asyncio
async def test_faq_lookup_no_match() -> None:
    from agents.triage_orchestrator import faq_lookup_impl as faq_lookup

    result = await faq_lookup("How do I reset my password?")
    assert result["success"] is False
    assert result["matched_keyword"] is None
    assert result["error"] is not None


# ---------------------------------------------------------------------------
# Session management helpers (unit-level, no Redis required)
# ---------------------------------------------------------------------------


class TestSessionHelpers:
    def test_session_structure_defaults(self) -> None:
        session: dict[str, object] = {}
        session.setdefault("customer_id", "cust_001")
        session.setdefault("channel", "web_chat")
        session.setdefault("agent_chain", [])
        assert session["customer_id"] == "cust_001"
        assert session["channel"] == "web_chat"
        assert session["agent_chain"] == []

    def test_agent_chain_appends(self) -> None:
        chain: list[str] = []
        chain.append("TriageOrchestrator")
        chain.append("PolicyAgent")
        assert chain == ["TriageOrchestrator", "PolicyAgent"]

    def test_expected_agent_chains_from_resolutions(self, resolutions: list[dict]) -> None:
        for res in resolutions:
            chain = res["expected_agent_chain"]
            assert isinstance(chain, list)
            assert len(chain) >= 1
            assert chain[0] == "TriageOrchestrator", (
                f"Resolution {res['resolution_id']}: chain must start with TriageOrchestrator"
            )


# ---------------------------------------------------------------------------
# Intent classification mapping (pure logic, no LLM call)
# ---------------------------------------------------------------------------


class TestIntentMapping:
    def test_all_messages_mapped_to_known_route(self, messages: list[dict]) -> None:
        route_map = {
            "return_request": "PolicyAgent",
            "order_status": "tracking_lookup",
            "billing_dispute": "BillingAgent",
            "general_inquiry": "faq_lookup",
            "edge_case_escalate": "EscalationAgent",
        }
        for msg in messages:
            intent = msg["expected_intent"]
            expected_route = msg["expected_route"]
            assert intent in route_map, f"Message {msg['message_id']}: unknown intent {intent}"
            assert expected_route == route_map[intent], (
                f"Message {msg['message_id']}: expected route {expected_route} "
                f"does not match mapping for intent {intent} ({route_map[intent]})"
            )

