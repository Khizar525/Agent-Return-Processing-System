"""
Billing Agent Tests
Owner: Project Lead

Tests the agent definition, tool configuration, guardrails, and
output contract.

Run:
    pytest tests/test_billing_agent.py -v
"""

from __future__ import annotations

import json

import pytest
import respx

from agents.tool import ToolContext

from app_agents.billing_agent import billing_agent, BillingDecision
from tools.payment_tools import process_refund
from guardrails.refund_cap import refund_cap_guardrail


_STRIPE_REFUND_URL = "https://api.stripe.com/v1/refunds"


async def _invoke_process_refund(order_id: str, amount_usd: float, method: str) -> dict:
    """Invoke process_refund through the FunctionTool wrapper."""
    args = json.dumps({"order_id": order_id, "amount_usd": amount_usd, "method": method})
    ctx = ToolContext(
        context=None,
        tool_name="process_refund",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await process_refund.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        return json.loads(result)
    return result


# ---------------------------------------------------------------------------
# Agent definition tests
# ---------------------------------------------------------------------------


def test_agent_name():
    assert billing_agent.name == "BillingAgent"


def test_agent_has_correct_model():
    assert billing_agent.model == "deepseek-v4-flash-free"


def test_agent_has_process_refund_tool():
    tool_names = [t.name for t in billing_agent.tools]
    assert "process_refund" in tool_names


def test_agent_has_refund_cap_guardrail():
    assert len(billing_agent.output_guardrails) > 0


def test_agent_has_output_type():
    assert billing_agent.output_type is not None
    assert billing_agent.output_type.__name__ == "BillingDecision"


def test_agent_instructions_mention_billing():
    assert (
        "billing" in billing_agent.instructions.lower()
        or "dispute" in billing_agent.instructions.lower()
    )


def test_agent_instructions_mention_refund_cap():
    assert "500" in billing_agent.instructions


def test_agent_instructions_mention_duplicate():
    assert "duplicate" in billing_agent.instructions.lower()


# ---------------------------------------------------------------------------
# BillingDecision schema tests
# ---------------------------------------------------------------------------


class TestBillingDecisionSchema:
    def test_all_fields_present(self):
        fields = BillingDecision.model_fields.keys()
        expected = {
            "dispute_type",
            "eligible_for_refund",
            "recommended_action",
            "refund_amount",
            "payment_method",
            "reasoning",
            "customer_message",
            "error",
        }
        assert expected.issubset(set(fields)), f"Missing fields: {expected - set(fields)}"

    def test_valid_refund_decision(self):
        d = BillingDecision(
            dispute_type="duplicate_charge",
            eligible_for_refund=True,
            recommended_action="refund",
            refund_amount=49.99,
            payment_method="stripe",
            reasoning="Customer charged twice for same order",
            customer_message="We've processed a refund of $49.99 to your card.",
            error=None,
        )
        assert d.eligible_for_refund is True
        assert d.recommended_action == "refund"
        assert d.refund_amount == 49.99

    def test_valid_reject_decision(self):
        d = BillingDecision(
            dispute_type="incorrect_amount",
            eligible_for_refund=False,
            recommended_action="reject",
            refund_amount=None,
            payment_method=None,
            reasoning="Charge matches order total",
            customer_message="After review, the charge is correct.",
            error=None,
        )
        assert d.recommended_action == "reject"

    def test_valid_escalate_decision(self):
        d = BillingDecision(
            dispute_type="unauthorized_transaction",
            eligible_for_refund=False,
            recommended_action="escalate",
            refund_amount=None,
            payment_method=None,
            reasoning="Potential fraud, needs human review",
            customer_message="We're escalate this to our security team.",
            error=None,
        )
        assert d.recommended_action == "escalate"

    def test_recommended_action_is_valid(self):
        valid = {"refund", "reject", "escalate"}
        for action in valid:
            d = BillingDecision(
                dispute_type="other",
                eligible_for_refund=action == "refund",
                recommended_action=action,
                reasoning="test",
                customer_message="test",
            )
            assert d.recommended_action in valid


# ---------------------------------------------------------------------------
# Tool invocation tests (via FunctionTool wrapper)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_refund_success():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post(_STRIPE_REFUND_URL).respond(
            json={"id": "re_123", "status": "succeeded"},
            status_code=200,
        )
        result = await _invoke_process_refund("ORD-001", 25.0, "stripe")
        assert result["success"] is True
        assert result["refund_amount"] == 25.0
        assert result["transaction_id"] == "re_123"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_empty_order_id():
    result = await _invoke_process_refund("", 25.0, "stripe")
    assert result["success"] is False
    assert result["error"] is not None


@pytest.mark.asyncio
async def test_process_refund_unsupported_method():
    result = await _invoke_process_refund("ORD-001", 25.0, "bitcoin")
    assert result["success"] is False
    assert "unsupported" in result["error"].lower() or "method" in result["error"].lower()


# ---------------------------------------------------------------------------
# Guardrail enforcement (direct tool test, no LLM needed)
# ---------------------------------------------------------------------------


class TestRefundCapEnforcement:
    @pytest.mark.asyncio
    async def test_guardrail_allows_under_cap_direct(self):
        """process_refund succeeds for amount <= cap."""
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
        monkeypatch.setenv("REFUND_CAP_USD", "500")

        async with respx.mock:
            respx.post(_STRIPE_REFUND_URL).respond(
                json={"id": "re_789", "status": "succeeded"},
                status_code=200,
            )
            result = await _invoke_process_refund("ORD-001", 200.0, "stripe")
            assert result["success"] is True

        monkeypatch.undo()

    def test_cap_enforcement_exists(self):
        """Verify the agent has the refund_cap_guardrail wired."""
        assert len(billing_agent.output_guardrails) > 0
        assert billing_agent.output_guardrails[0] is refund_cap_guardrail
