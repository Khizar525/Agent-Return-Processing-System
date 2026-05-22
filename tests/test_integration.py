"""
Integration Tests — Phase 1
Owner: Project Lead

Tests the check_return_policy tool, triage agent tools (tracking_lookup,
faq_lookup), and fixture data integrity.

Run:
    pytest tests/test_integration.py -v
"""

import json
import os

import pytest

from tools.policy_tools import check_return_policy_impl as check_return_policy

_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


# ---------------------------------------------------------------------------
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
