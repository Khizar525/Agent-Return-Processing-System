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

from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return_policy

from collections.abc import Generator
from database.repository import MemoryBackend
from tools.policy_tools import set_repo_for_testing, reset_repo_for_testing

@pytest.fixture(autouse=True)
def _setup_integration_test_repo(orders, customers, fraud_signals) -> Generator[None, None, None]:
    data = {
        "orders": {o["order_id"]: {
            "order_id": o["order_id"],
            "customer_id": o["customer_id"],
            "item_category": o.get("item_category") or (o["items"][0]["category"] if o.get("items") else "electronics"),
            "days_since_purchase": o["days_since_purchase"],
            "price": float(o.get("total_usd") or (sum(i["price_usd"] * i["qty"] for i in o["items"]) if o.get("items") else 100.0)),
            "damaged": any(i.get("damaged", False) for i in o.get("items", [])) or o.get("damaged", False),
        } for o in orders},
        "customers": {c["customer_id"]: {
            "customer_id": c["customer_id"],
            "fraud_flag": c["fraud_flag"],
            "fraud_reason": c.get("fraud_reason"),
        } for c in customers},
        "fraud_db_matches": {s["customer_id"]: {
            "customer_id": s["customer_id"],
            "match_reason": s["description"],
        } for s in fraud_signals},
    }
    set_repo_for_testing(MemoryBackend(data))
    yield
    reset_repo_for_testing()


_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


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
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unknown_customer_returns_ineligible(self) -> None:
        result = await check_return_policy("ord_1002", "cust_unknown")
        assert result["eligible"] is False
        assert result["error"] is not None
        assert "not found" in result["error"].lower()

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
            "success", "eligible", "reason", "recommended_action",
            "return_window_days", "days_since_purchase", "item_category",
            "exclusion_reason", "fraud_signal", "error",
        }
        assert set(result.keys()) == expected_keys, f"Extra/missing keys: {set(result.keys()) ^ expected_keys}"


# ---------------------------------------------------------------------------
# tracking_lookup tool
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="tracking_lookup_impl not yet in triage_orchestrator — M4/M3 task")
@pytest.mark.asyncio
async def test_tracking_lookup_found() -> None:
    from app_agents.triage_orchestrator import tracking_lookup_impl as tracking_lookup

    result = await tracking_lookup("ord_1001")
    assert result["success"] is True
    assert result["found"] is True
    assert result["status"] == "delivered"
    assert result["carrier"] == "fedex"


@pytest.mark.skip(reason="tracking_lookup_impl not yet in triage_orchestrator — M4/M3 task")
@pytest.mark.asyncio
async def test_tracking_lookup_not_found() -> None:
    from app_agents.triage_orchestrator import tracking_lookup_impl as tracking_lookup

    result = await tracking_lookup("ord_does_not_exist")
    assert result["success"] is False
    assert result["found"] is False
    assert result["error"] is not None


# ---------------------------------------------------------------------------
# faq_lookup tool
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="faq_lookup_impl not yet in triage_orchestrator — M4/M3 task")
@pytest.mark.asyncio
async def test_faq_lookup_matches_keyword() -> None:
    from app_agents.triage_orchestrator import faq_lookup_impl as faq_lookup

    result = await faq_lookup("What is your return window?")
    assert result["success"] is True
    assert result["matched_keyword"] is not None
    assert result["error"] is None


@pytest.mark.skip(reason="faq_lookup_impl not yet in triage_orchestrator — M4/M3 task")
@pytest.mark.asyncio
async def test_faq_lookup_no_match() -> None:
    from app_agents.triage_orchestrator import faq_lookup_impl as faq_lookup

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




# ---------------------------------------------------------------------------
# Pipeline test skeletons
# pytest.skip() until teammate branches are merged.
# Use conftest fixtures: get_resolution, get_message, get_customer, get_order
# Mock agent handoffs — do NOT import policy_agent / escalation_agent directly.
# ---------------------------------------------------------------------------


@pytest.mark.skip("Teammate PRs not yet merged — activate after feature/policy-agent + feature/resolution-agent land")
class TestPipelineSkeletons:
    """Skeleton integration tests for every resolution scenario.

    Unskip each test by removing the @pytest.mark.skip or calling
    pytest.skip() only conditionally when imports fail.
    """

    # ── res_001: Happy path (return → policy → resolution → communication) ──

    @pytest.mark.asyncio
    async def test_return_request_routes_to_policy_agent(self, get_message, get_resolution, get_customer, get_order):
        """msg_001 is a clean return request → must route to PolicyAgent.
        Expected chain: Triage → PolicyAgent → ResolutionAgent → CommunicationAgent."""
        msg = get_message("msg_001")
        res = get_resolution("res_001")
        assert msg is not None and res is not None

        _customer = get_customer(msg["customer_id"])
        _order = get_order(res["order_id"])
        _expected_chain = res["expected_agent_chain"]

        # TODO: call handle_customer_message() or mock Runner.run()
        # to verify the triage agent hands off through the full chain.
        # Assert final agent_chain == expected_chain.
        # Assert check_return_policy output matches res["expected_policy_output"].
        pytest.skip("Implement when PolicyAgent handoff is merged")

    # ── res_002: Rejection (expired return window) ──

    @pytest.mark.asyncio
    async def test_rejection_path_skips_resolution_agent(self, get_message, get_resolution):
        """msg_007 has a 31-day-old order → ineligible.
        Expected chain: Triage → PolicyAgent → CommunicationAgent."""
        msg = get_message("msg_007")
        res = get_resolution("res_002")
        assert msg is not None and res is not None

        expected_chain = res["expected_agent_chain"]
        assert "ResolutionAgent" not in expected_chain

        policy_exp = res["expected_policy_output"]
        assert policy_exp["eligible"] is False
        assert policy_exp["recommended_action"] == "reject"

        # TODO: mock Runner.run to return a rejected policy decision.
        # Assert the pipeline skips ResolutionAgent and goes to CommunicationAgent.
        pytest.skip("Implement when PolicyAgent handoff is merged")

    # ── res_003: Escalation (legal threat) ──

    @pytest.mark.asyncio
    async def test_legal_threat_routes_to_escalation_agent(self, get_message, get_resolution):
        """msg_005 contains legal threats → must bypass PolicyAgent.
        Expected chain: Triage → EscalationAgent."""
        msg = get_message("msg_005")
        res = get_resolution("res_003")
        assert msg is not None and res is not None

        expected_chain = res["expected_agent_chain"]
        assert "PolicyAgent" not in expected_chain
        assert "EscalationAgent" in expected_chain

        escalation_exp = res["expected_escalation_output"]
        assert escalation_exp["priority"] == "urgent"

        # TODO: mock Runner.run to return an escalation intent.
        # Assert the triage agent hands off directly to EscalationAgent.
        pytest.skip("Implement when EscalationAgent handoff is merged")

    # ── res_004: Refund cap (eligible but > $500) ──

    @pytest.mark.asyncio
    async def test_refund_cap_triggers_human_approval(self, get_message, get_resolution):
        """msg_008 wants to return a $1200 laptop → eligible but exceeds cap.
        Expected chain: Triage → PolicyAgent → ResolutionAgent → EscalationAgent."""
        msg = get_message("msg_008")
        res = get_resolution("res_004")
        assert msg is not None and res is not None

        expected_chain = res["expected_agent_chain"]
        assert expected_chain == ["TriageOrchestrator", "PolicyAgent", "ResolutionAgent", "EscalationAgent"]

        res_out = res["expected_resolution_output"]
        assert res_out["human_approval_required"] is True
        assert res_out["reason"] == "exceeds_cap"
        assert res_out["amount"] == 1200.00

        # TODO: mock Runner.run through Triage → Policy → Resolution.
        # Assert refund_cap_guardrail trips and the flow escalates.
        pytest.skip("Implement when ResolutionAgent + guardrail are merged")

    # ── res_005: Fraud flag on account ──

    @pytest.mark.asyncio
    async def test_fraud_flag_blocks_return_and_escalates(self, get_message, get_resolution, get_customer):
        """msg_006 comes from a fraud-flagged account.
        Expected chain: Triage → PolicyAgent → EscalationAgent."""
        msg = get_message("msg_006")
        res = get_resolution("res_005")
        assert msg is not None and res is not None

        customer = get_customer(msg["customer_id"])
        assert customer["fraud_flag"] is True

        expected_chain = res["expected_agent_chain"]
        assert "ResolutionAgent" not in expected_chain
        assert "EscalationAgent" in expected_chain

        policy_exp = res["expected_policy_output"]
        assert policy_exp["eligible"] is False
        assert policy_exp["recommended_action"] == "escalate"

        escalation_exp = res["expected_escalation_output"]
        assert escalation_exp["priority"] == "high"

        # TODO: mock Runner.run to return fraud flag → escalate decision.
        pytest.skip("Implement when PolicyAgent handoff is merged")

    # ── res_006: PII scrubbing ──

    @pytest.mark.asyncio
    async def test_pii_stripped_before_agent_receives_message(self, get_message, get_resolution):
        """msg_012 contains a credit card number and SSN.
        The PII guardrail must redact them before the Triage agent sees the message."""
        msg = get_message("msg_012")
        res = get_resolution("res_006")
        assert msg is not None and res is not None

        scrub_exp = res["expected_pii_scrub"]
        assert scrub_exp["original_contains_card"] is True
        assert scrub_exp["original_contains_ssn"] is True

        # TODO: call pii_scrubber guardrail on raw_message.
        # Assert the scrubbed message does not contain card digits or SSN.
        # Assert the scrubbed pattern matches [REDACTED].
        pytest.skip("Implement when PII guardrail module is merged")

    # ── res_007: Exclusion (digital goods) ──

    @pytest.mark.asyncio
    async def test_excluded_category_rejects_automatically(self, get_message, get_resolution):
        """msg_009 wants to return a digital book → ineligible.
        Expected chain: Triage → PolicyAgent → CommunicationAgent."""
        msg = get_message("msg_009")
        res = get_resolution("res_007")
        assert msg is not None and res is not None

        expected_chain = res["expected_agent_chain"]
        assert "ResolutionAgent" not in expected_chain

        policy_exp = res["expected_policy_output"]
        assert policy_exp["eligible"] is False
        assert policy_exp["recommended_action"] == "reject"

        # TODO: mock Runner.run to return exclusion decision.
        pytest.skip("Implement when PolicyAgent handoff is merged")

    # ── Session persistence ──

    @pytest.mark.asyncio
    async def test_session_persists_across_handoffs(self, get_message, get_resolution):
        """After the pipeline completes, the session must contain
        the full agent_chain matching the expected resolution chain."""
        res = get_resolution("res_001")
        assert res is not None

        _expected_chain = res["expected_agent_chain"]

        # TODO: mock Runner.run() + save_session().
        # Call handle_customer_message(), then load session from (mocked) Redis.
        # Assert session["agent_chain"] == expected_chain.
        # Assert session["timestamps"]["resolved_at"] is not None.
        pytest.skip("Implement when Redis session integration is tested")

    # ── Full end-to-end ──

    @pytest.mark.asyncio
    async def test_full_return_pipeline_end_to_end(self, get_message, get_resolution):
        """Full pipeline: Triage → Policy (eligible) → Resolution (refund) → Communication.
        Assert resolution contains transaction_id and label_url."""
        msg = get_message("msg_001")
        res = get_resolution("res_001")
        assert msg is not None and res is not None

        res_out = res["expected_resolution_output"]
        assert res_out["success"] is True
        assert res_out["refund_amount"] == 149.50

        comm_exp = res["expected_communication"]
        assert comm_exp["max_word_count"] <= 150

        # TODO: mock all tool calls and run handle_customer_message().
        # Assert the final output contains a transaction_id and label_url.
        # Assert the communication message is under 150 words.
        pytest.skip("Implement when all agents + tools are merged")
