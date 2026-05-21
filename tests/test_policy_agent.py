"""
Policy Agent Unit Tests
Owner: Member 2

Tests check_return_policy directly with deterministic mock data
from tools/policy_tools.py (no external fixtures needed).

Run:
    pytest tests/test_policy_agent.py -v
"""

import pytest
from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return_policy

TOOL_CONTRACT_KEYS = [
    "eligible", "reason", "recommended_action",
    "return_window_days", "days_since_purchase", "item_category",
    "exclusion_reason", "fraud_signal", "error",
]

VALID_ACTIONS = {"refund", "replacement", "reject", "escalate"}


@pytest.mark.asyncio
async def test_eligible_return_within_window() -> None:
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
    assert result["eligible"] is True
    assert result["error"] is None
    assert result["days_since_purchase"] == 15
    assert result["exclusion_reason"] is None
    assert result["fraud_signal"] is False


@pytest.mark.asyncio
async def test_ineligible_return_outside_window() -> None:
    result = await check_return_policy(order_id="ORD-002", customer_id="CUST-001")
    assert result["eligible"] is False
    assert result["error"] is None
    assert "exceeded" in result["reason"].lower()
    assert result["days_since_purchase"] == 45
    assert result["recommended_action"] == "reject"


@pytest.mark.asyncio
async def test_ineligible_item_in_exclusion_list() -> None:
    result = await check_return_policy(order_id="ORD-003", customer_id="CUST-002")
    assert result["eligible"] is False
    assert result["error"] is None
    assert result["exclusion_reason"] is not None
    assert "digital_goods" in result["exclusion_reason"]
    assert result["recommended_action"] == "reject"


@pytest.mark.asyncio
async def test_fraud_flag_blocks_return() -> None:
    result = await check_return_policy(order_id="ORD-005", customer_id="CUST-004")
    assert result["eligible"] is False
    assert result["fraud_signal"] is True
    assert result["error"] is None
    assert result["recommended_action"] == "reject"


@pytest.mark.asyncio
async def test_output_is_valid_json() -> None:
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
    for key in TOOL_CONTRACT_KEYS:
        assert key in result, f"Missing key: {key}"
    assert result["recommended_action"] in VALID_ACTIONS, f"Unexpected action: {result['recommended_action']}"
    assert isinstance(result["eligible"], bool)
    assert isinstance(result["reason"], str)
    assert isinstance(result["return_window_days"], int)
    assert isinstance(result["days_since_purchase"], int)
    assert isinstance(result["fraud_signal"], bool)


@pytest.mark.asyncio
async def test_recommended_action_refund() -> None:
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
    assert result["eligible"] is True
    assert result["recommended_action"] == "refund"


@pytest.mark.asyncio
async def test_recommended_action_replacement() -> None:
    result = await check_return_policy(order_id="ORD-004", customer_id="CUST-003")
    assert result["eligible"] is True
    assert result["recommended_action"] == "replacement"


@pytest.mark.asyncio
async def test_recommended_action_reject() -> None:
    result = await check_return_policy(order_id="ORD-002", customer_id="CUST-001")
    assert result["eligible"] is False
    assert result["recommended_action"] == "reject"


@pytest.mark.asyncio
async def test_recommended_action_escalate() -> None:
    result = await check_return_policy(order_id="ORD-006", customer_id="CUST-005")
    assert result["eligible"] is False
    assert result["fraud_signal"] is True
    assert result["recommended_action"] == "escalate"


@pytest.mark.asyncio
async def test_fraud_detection_cross_reference() -> None:
    result = await check_return_policy(order_id="ORD-006", customer_id="CUST-005")
    assert result["fraud_signal"] is True
    assert result["eligible"] is False
    assert "fraud db match" in result["reason"].lower()
    assert result["error"] is None


@pytest.mark.asyncio
async def test_order_not_found() -> None:
    result = await check_return_policy(order_id="ORD-999", customer_id="CUST-001")
    assert result.get("success") is False
    assert "not found" in result.get("error", "").lower()
    assert result.get("eligible") is False


@pytest.mark.asyncio
async def test_customer_not_found() -> None:
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-999")
    assert result.get("success") is False
    assert "not found" in result.get("error", "").lower()
    assert result.get("eligible") is False


@pytest.mark.asyncio
async def test_order_customer_mismatch() -> None:
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-002")
    assert result.get("success") is False
    assert "does not belong" in result.get("error", "").lower()
    assert result.get("eligible") is False
