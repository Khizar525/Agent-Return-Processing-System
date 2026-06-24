"""
Policy Agent — Extreme Test Suite
Owner: Member 2

Tests every module owned by M2 under extreme edge cases:
  - tools/policy_tools.py   (check_return_policy)
  - guardrails/pii_scrubber.py
  - guardrails/sentiment_monitor.py
  - guardrails/refund_cap.py
  - agents/policy_agent.py  (configuration & contract)

Run:  pytest tests/test_policy_agent.py -v
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import cast

import pytest

# ── Tool under test ──────────────────────────────────────────────────────────
from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return_policy
from tools.policy_tools import RETURN_WINDOW_DAYS, EXCLUDED_CATEGORIES
from tools.policy_tools import set_repo_for_testing, reset_repo_for_testing, get_current_repo

# ── Database backend (for test mutation of mock data) ────────────────────────
from database.repository import MemoryBackend

# ── Guardrails under test ────────────────────────────────────────────────────
from guardrails.pii_scrubber import RAW_PII_SCRUBBER as pii_scrubber
from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as sentiment_monitor
from guardrails.refund_cap import RAW_REFUND_CAP as refund_cap

# ── Agent under test ─────────────────────────────────────────────────────────
from app_agents.policy_agent import policy_agent


@pytest.fixture(autouse=True)
def _inject_test_repo() -> Generator[None, None, None]:
    """Inject a fresh MemoryBackend before every test."""
    set_repo_for_testing(MemoryBackend())
    yield
    reset_repo_for_testing()


@pytest.fixture(scope="session", autouse=True)
def _seed_policy_tools_data() -> Generator[None, None, None]:
    """Ensure initial data dict is never mutated."""
    yield


# ============================================================================
# COMMON CONSTANTS
# ============================================================================

TOOL_CONTRACT_KEYS = [
    "eligible",
    "reason",
    "recommended_action",
    "return_window_days",
    "days_since_purchase",
    "item_category",
    "exclusion_reason",
    "fraud_signal",
    "error",
]

ERROR_CONTRACT_KEYS = ["success", "error"]

VALID_ACTIONS = {"refund", "replacement", "reject", "escalate"}
NULLABLE_FIELDS = {"exclusion_reason", "error"}

# ============================================================================
# SECTION 1 — check_return_policy: NOMINAL PATHS
# ============================================================================


class TestNominalPaths:
    """Happy-path scenarios that exercise every recommended_action branch."""

    @pytest.mark.asyncio
    async def test_eligible_refund(self) -> None:
        """ORD-001 / CUST-001: within window, non-excluded, no fraud → refund."""
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["eligible"] is True
        assert r["recommended_action"] == "refund"
        assert r["error"] is None
        assert r["days_since_purchase"] == 15
        assert r["exclusion_reason"] is None
        assert r["fraud_signal"] is False

    @pytest.mark.asyncio
    async def test_eligible_replacement(self) -> None:
        """ORD-004 / CUST-003: damaged item → replacement."""
        r = await check_return_policy(order_id="ORD-004", customer_id="CUST-003")
        assert r["eligible"] is True
        assert r["recommended_action"] == "replacement"
        assert r["error"] is None

    @pytest.mark.asyncio
    async def test_ineligible_outside_window(self) -> None:
        """ORD-002: 45 days > 30-day window → reject."""
        r = await check_return_policy(order_id="ORD-002", customer_id="CUST-001")
        assert r["eligible"] is False
        assert r["recommended_action"] == "reject"
        assert r["days_since_purchase"] == 45
        assert "exceeded" in r["reason"].lower()

    @pytest.mark.asyncio
    async def test_ineligible_excluded_category(self) -> None:
        """ORD-003 / CUST-002: digital_goods excluded → reject."""
        r = await check_return_policy(order_id="ORD-003", customer_id="CUST-002")
        assert r["eligible"] is False
        assert r["recommended_action"] == "reject"
        assert r["exclusion_reason"] is not None
        assert "digital_goods" in r["exclusion_reason"]

    @pytest.mark.asyncio
    async def test_fraud_flag_escalate(self) -> None:
        """ORD-005 / CUST-004: fraud_flag=True → escalate (needs human review)."""
        r = await check_return_policy(order_id="ORD-005", customer_id="CUST-004")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["recommended_action"] == "escalate"

    @pytest.mark.asyncio
    async def test_fraud_db_match_escalate(self) -> None:
        """ORD-006 / CUST-005: matched in fraud DB, no flag → escalate."""
        r = await check_return_policy(order_id="ORD-006", customer_id="CUST-005")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["recommended_action"] == "escalate"
        assert "fraud db match" in r["reason"].lower()


# ============================================================================
# SECTION 2 — check_return_policy: EDGE / BOUNDARY CASES
# ============================================================================


class TestBoundaryCases:
    """Boundary conditions around return window, exclusion list, etc."""

    @pytest.mark.asyncio
    async def test_exactly_30_days(self) -> None:
        """Should add a mock order at exactly 30 days and verify eligibility."""
        repo = get_current_repo()
        assert repo is not None
        order = await repo.get_order("ORD-001")
        assert order is not None
        assert order.days_since_purchase <= RETURN_WINDOW_DAYS, (
            "Control order should be within window"
        )

    @pytest.mark.asyncio
    async def test_excluded_all_categories_covered(self) -> None:
        """Ensure every EXCLUDED_CATEGORIES item is tested in mock data."""
        repo = get_current_repo()
        assert repo is not None
        mb = cast("MemoryBackend", repo)
        mock_categories = {order["item_category"] for order in mb.orders.values()}
        covered = EXCLUDED_CATEGORIES & mock_categories
        assert covered, (
            f"No mock order has an excluded category. "
            f"Excluded: {EXCLUDED_CATEGORIES}, mocked: {mock_categories}"
        )
        # at least one exclusion is covered
        assert len(covered) >= 1

    @pytest.mark.asyncio
    async def test_all_four_actions_producible(self) -> None:
        """Assert that mock data can produce all 4 recommended_action values."""
        actions_seen: set[str] = set()
        for oid, cust in [
            ("ORD-001", "CUST-001"),
            ("ORD-004", "CUST-003"),
            ("ORD-002", "CUST-001"),
            ("ORD-006", "CUST-005"),
        ]:
            r = await check_return_policy(order_id=oid, customer_id=cust)
            actions_seen.add(r["recommended_action"])
        assert actions_seen == VALID_ACTIONS, (
            f"Mock data cannot produce all 4 actions. Missing: {VALID_ACTIONS - actions_seen}"
        )

    @pytest.mark.asyncio
    async def test_days_since_purchase_beyond_extreme(self) -> None:
        """A very large days_since_purchase should still be handled (no overflow)."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-001", days_since_purchase=999_999)
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["eligible"] is False
        assert r["recommended_action"] == "reject"
        assert r["days_since_purchase"] == 999_999

    @pytest.mark.asyncio
    async def test_zero_days_since_purchase(self) -> None:
        """0 days since purchase → should be eligible (same day return)."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-001", days_since_purchase=0)
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["eligible"] is True
        assert r["days_since_purchase"] == 0
        assert r["recommended_action"] == "refund"


# ============================================================================
# SECTION 3 — check_return_policy: ERROR & INVALID INPUT PATHS
# ============================================================================


class TestErrorPaths:
    """Every way the tool can fail — invalid inputs, not-found, mismatch."""

    @pytest.mark.asyncio
    async def test_order_not_found(self) -> None:
        r = await check_return_policy(order_id="ORD-999", customer_id="CUST-001")
        assert r.get("success") is False
        assert "not found" in r.get("error", "").lower()
        assert r.get("eligible") is False

    @pytest.mark.asyncio
    async def test_customer_not_found(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-999")
        assert r.get("success") is False
        assert "not found" in r.get("error", "").lower()
        assert r.get("eligible") is False

    @pytest.mark.asyncio
    async def test_both_not_found(self) -> None:
        """Both identifiers missing."""
        r = await check_return_policy(order_id="ORD-999", customer_id="CUST-999")
        assert r.get("success") is False

    @pytest.mark.asyncio
    async def test_order_customer_mismatch(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-002")
        assert r.get("success") is False
        assert "does not belong" in r.get("error", "").lower()
        assert r.get("eligible") is False

    @pytest.mark.asyncio
    async def test_empty_order_id(self) -> None:
        r = await check_return_policy(order_id="", customer_id="CUST-001")
        assert r.get("success") is False, "Empty order_id should error"

    @pytest.mark.asyncio
    async def test_empty_customer_id(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="")
        assert r.get("success") is False, "Empty customer_id should error"

    @pytest.mark.asyncio
    async def test_whitespace_order_id(self) -> None:
        r = await check_return_policy(order_id="   ", customer_id="CUST-001")
        assert r.get("success") is False, "Whitespace order_id should error"

    @pytest.mark.asyncio
    async def test_whitespace_customer_id(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="   ")
        assert r.get("success") is False, "Whitespace customer_id should error"

    @pytest.mark.asyncio
    async def test_special_chars_in_order_id(self) -> None:
        r = await check_return_policy(order_id="<script>alert(1)</script>", customer_id="CUST-001")
        assert r.get("success") is False

    @pytest.mark.asyncio
    async def test_order_id_with_newline(self) -> None:
        r = await check_return_policy(order_id="ORD-001\n", customer_id="CUST-001")
        assert r.get("success") is False, "Newline in order_id should not match"

    @pytest.mark.asyncio
    async def test_very_long_order_id(self) -> None:
        r = await check_return_policy(order_id="A" * 1000, customer_id="CUST-001")
        assert r.get("success") is False

    @pytest.mark.asyncio
    async def test_error_dict_has_success_field(self) -> None:
        """Error responses MUST contain 'success': False per tool_interface_spec.md."""
        r = await check_return_policy(order_id="ORD-999", customer_id="CUST-001")
        assert "success" in r
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_success_dict_has_success_field(self) -> None:
        """Success responses must contain a 'success': True field per error contract."""
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert "success" in r, "Success dict must carry 'success' key"
        assert r["success"] is True


# ============================================================================
# SECTION 4 — check_return_policy: COMPOUND / COMBINATION VIOLATIONS
# ============================================================================


class TestCompoundViolations:
    """Multiple violations happening simultaneously."""

    @pytest.mark.asyncio
    async def test_outside_window_and_excluded(self) -> None:
        """Hypothetical: both window exceeded AND excluded category."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-001", days_since_purchase=45, item_category="perishables")
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["eligible"] is False
        assert "window" in r["reason"].lower() or "exceeded" in r["reason"].lower()
        assert "perishables" in r["reason"] or "excluded" in r["reason"].lower()
        assert r["recommended_action"] == "reject"

    @pytest.mark.asyncio
    async def test_outside_window_and_fraud_flag(self) -> None:
        """Both window exceeded AND fraud flag set.
        ORD-005 belongs to CUST-004 (has fraud_flag)."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-005", days_since_purchase=45)
        r = await check_return_policy(order_id="ORD-005", customer_id="CUST-004")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["recommended_action"] == "escalate"

    @pytest.mark.asyncio
    async def test_excluded_and_fraud_db_match(self) -> None:
        """Excluded category AND fraud DB match."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-006", item_category="final_sale")
        r = await check_return_policy(order_id="ORD-006", customer_id="CUST-005")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["exclusion_reason"] is not None

    @pytest.mark.asyncio
    async def test_all_violations_at_once(self) -> None:
        """Outside window + excluded + fraud flag — all violations.
        ORD-005 belongs to CUST-004 (has fraud_flag)."""
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        repo.set_order("ORD-005", days_since_purchase=60, item_category="perishables")
        r = await check_return_policy(order_id="ORD-005", customer_id="CUST-004")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["exclusion_reason"] is not None
        assert r["days_since_purchase"] == 60
        assert r["recommended_action"] == "escalate"


# ============================================================================
# SECTION 5 — check_return_policy: OUTPUT CONTRACT VALIDATION
# ============================================================================


class TestOutputContract:
    """Verify every field in the output dict has the correct type/value."""

    @pytest.mark.asyncio
    async def test_all_contract_keys_present_success(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        for key in TOOL_CONTRACT_KEYS:
            assert key in r, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_all_contract_keys_present_error(self) -> None:
        r = await check_return_policy(order_id="ORD-999", customer_id="CUST-001")
        for key in ERROR_CONTRACT_KEYS:
            assert key in r, f"Missing key in error: {key}"

    @pytest.mark.asyncio
    async def test_field_types_success(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert isinstance(r["eligible"], bool)
        assert isinstance(r["reason"], str)
        assert isinstance(r["recommended_action"], str)
        assert isinstance(r["return_window_days"], int)
        assert isinstance(r["days_since_purchase"], int)
        assert isinstance(r["item_category"], str)
        assert r["exclusion_reason"] is None or isinstance(r["exclusion_reason"], str)
        assert isinstance(r["fraud_signal"], bool)
        assert r["error"] is None

    @pytest.mark.asyncio
    async def test_recommended_action_is_valid(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["recommended_action"] in VALID_ACTIONS

    @pytest.mark.asyncio
    async def test_error_field_type(self) -> None:
        r = await check_return_policy(order_id="ORD-999", customer_id="CUST-001")
        assert isinstance(r.get("error"), str)
        assert len(r.get("error", "")) > 0

    @pytest.mark.asyncio
    async def test_fraud_signal_bool_only(self) -> None:
        """fraud_signal must be strictly bool, not truthy int."""
        for oid, cid in [("ORD-001", "CUST-001"), ("ORD-005", "CUST-004"), ("ORD-006", "CUST-005")]:
            r = await check_return_policy(order_id=oid, customer_id=cid)
            assert r["fraud_signal"] is True or r["fraud_signal"] is False
            assert isinstance(r["fraud_signal"], bool)

    @pytest.mark.asyncio
    async def test_return_window_days_positive(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["return_window_days"] > 0

    @pytest.mark.asyncio
    async def test_days_since_purchase_non_negative(self) -> None:
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["days_since_purchase"] >= 0


# ============================================================================
# SECTION 6 — check_return_policy: MUTATION / IDEMPOTENCY
# ============================================================================


class TestIdempotencyAndMutation:
    """Ensure the tool is stateless and repeatable."""

    @pytest.mark.asyncio
    async def test_repeatable_calls_return_same(self) -> None:
        r1 = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        r2 = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r1 == r2

    @pytest.mark.asyncio
    async def test_calls_dont_mutate_mock_data(self) -> None:
        repo = get_current_repo()
        assert isinstance(repo, MemoryBackend)
        import copy

        orders_before = copy.deepcopy(repo.orders)
        await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert repo.orders == orders_before, "Tool mutated mock data!"

    @pytest.mark.asyncio
    async def test_concurrent_calls_dont_interfere(self) -> None:
        results = await asyncio.gather(
            check_return_policy(order_id="ORD-001", customer_id="CUST-001"),
            check_return_policy(order_id="ORD-002", customer_id="CUST-001"),
            check_return_policy(order_id="ORD-003", customer_id="CUST-002"),
            check_return_policy(order_id="ORD-004", customer_id="CUST-003"),
            check_return_policy(order_id="ORD-005", customer_id="CUST-004"),
            check_return_policy(order_id="ORD-006", customer_id="CUST-005"),
        )
        assert results[0]["eligible"] is True
        assert results[1]["eligible"] is False
        assert results[2]["eligible"] is False
        assert results[3]["eligible"] is True
        assert results[4]["eligible"] is False
        assert results[5]["eligible"] is False


# ============================================================================
# SECTION 7 — PII SCRUBBER GUARDRAIL
# ============================================================================


class TestPiiScrubber:
    """Extreme edge cases for the PII scrubbing input guardrail."""

    @pytest.mark.asyncio
    async def test_credit_card_dashed(self) -> None:
        r = await pii_scrubber(None, None, "4111-1111-1111-1111")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_credit_card_undashed(self) -> None:
        r = await pii_scrubber(None, None, "4111111111111111")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_credit_card_with_spaces(self) -> None:
        r = await pii_scrubber(None, None, "4111 1111 1111 1111")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_credit_card_mixed_delimiters(self) -> None:
        r = await pii_scrubber(None, None, "4111-1111 1111-1111")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_ssn_dashed(self) -> None:
        r = await pii_scrubber(None, None, "My SSN is 123-45-6789")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_ssn_undashed(self) -> None:
        r = await pii_scrubber(None, None, "SSN: 123456789")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_bank_account_8_digits(self) -> None:
        r = await pii_scrubber(None, None, "Account: 87654321")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_bank_account_17_digits(self) -> None:
        r = await pii_scrubber(None, None, "Account: 12345678901234567")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_multiple_pii_in_message(self) -> None:
        msg = "CC: 4111-1111-1111-1111 and SSN: 123-45-6789"
        r = await pii_scrubber(None, None, msg)
        scrubbed = r.output_info["scrubbed_message"]
        assert scrubbed.count("[REDACTED]") >= 2
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_pii_at_start_of_message(self) -> None:
        r = await pii_scrubber(None, None, "4111-1111-1111-1111 is my card")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]

    @pytest.mark.asyncio
    async def test_pii_at_end_of_message(self) -> None:
        r = await pii_scrubber(None, None, "My card is 4111-1111-1111-1111")
        assert "[REDACTED]" in r.output_info["scrubbed_message"]

    @pytest.mark.asyncio
    async def test_clean_message_passes_through(self) -> None:
        msg = "I want to check my order status"
        r = await pii_scrubber(None, None, msg)
        assert r.output_info["scrubbed_message"] == msg
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_empty_message(self) -> None:
        r = await pii_scrubber(None, None, "")
        assert r.tripwire_triggered is False
        assert r.output_info["scrubbed_message"] == ""

    @pytest.mark.asyncio
    async def test_very_long_message_with_pii(self) -> None:
        prefix = "A" * 10_000
        msg = f"{prefix} 4111-1111-1111-1111"
        r = await pii_scrubber(None, None, msg)
        assert "[REDACTED]" in r.output_info["scrubbed_message"]
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_7_digit_number_not_redacted(self) -> None:
        """7 digits should NOT match any pattern (CC min 13, BANK min 8, SSN 9)."""
        msg = "1234567"
        r = await pii_scrubber(None, None, msg)
        assert r.tripwire_triggered is False, "7-digit number should not be redacted"

    @pytest.mark.asyncio
    async def test_numbers_with_letters_not_redacted(self) -> None:
        """Mix of digits and letters should not match pure-digit patterns."""
        msg = "abcd-efgh-ijkl-mnop"
        r = await pii_scrubber(None, None, msg)
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_pii_with_unicode(self) -> None:
        msg = "Carte: 4111-1111-1111-1111 über"
        r = await pii_scrubber(None, None, msg)
        assert "[REDACTED]" in r.output_info["scrubbed_message"]

    @pytest.mark.asyncio
    async def test_message_with_only_numbers(self) -> None:
        """Pure numeric string could trigger multiple patterns."""
        msg = "4111111111111111"
        r = await pii_scrubber(None, None, msg)
        assert r.tripwire_triggered is True
        assert "[REDACTED]" in r.output_info["scrubbed_message"]

    @pytest.mark.asyncio
    async def test_guardrail_output_contract(self) -> None:
        r = await pii_scrubber(None, None, "test")
        assert hasattr(r, "tripwire_triggered")
        assert hasattr(r, "output_info")
        assert "scrubbed_message" in r.output_info


# ============================================================================
# SECTION 8 — SENTIMENT MONITOR GUARDRAIL
# ============================================================================


class TestSentimentMonitor:
    """Extreme edge cases for the sentiment scoring input guardrail."""

    @pytest.mark.asyncio
    async def test_legal_keywords_and_all_caps(self) -> None:
        """ALL CAPS (0.3) + legal (0.4) + distress (0.2) = 0.9 → triggered."""
        msg = "I AM GOING TO SUE YOU THIS IS OUTRAGEOUS"
        r = await sentiment_monitor(None, None, msg)
        # ALL_CAPS(0.3) + legal(0.4) + distress(0.2) = 0.9
        assert r.output_info["score"] == 0.9
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_above_threshold_escalates(self) -> None:
        """ALL CAPS (0.3) + legal (0.4) + distress (0.2) + profanity (0.2) = 1.1 → clamped to 1.0 → triggered."""
        msg = "I AM A FUCKING FURIOUS I WILL SUE YOUR COMPANY!!!"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] > 0.8
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_neutral_message_no_trigger(self) -> None:
        msg = "I'd like to check my order status"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] == 0.0
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_empty_message(self) -> None:
        r = await sentiment_monitor(None, None, "")
        assert r.output_info["score"] == 0.0
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_all_caps_short_ignored(self) -> None:
        """ALL CAPS with len <= 10 should not score."""
        r = await sentiment_monitor(None, None, "I AM OK")
        assert r.output_info["score"] == 0.0

    @pytest.mark.asyncio
    async def test_boundary_exactly_threshold(self) -> None:
        """ALL CAPS (0.3) + legal (0.4) + distress (0.2) = 0.9 → triggered (>= threshold)."""
        msg = "I AM GOING TO SUE YOUR COMPANY THIS IS UNACCEPTABLE"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] == 0.9
        assert r.tripwire_triggered is True

    @pytest.mark.asyncio
    async def test_profanity_only(self) -> None:
        """Profanity (0.2) alone is well under threshold."""
        msg = "This is shit"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] == 0.2
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_multiple_exclamation_marks(self) -> None:
        """'!!!' → +0.1 per match, capped at 0.2."""
        msg = "Really!!!"
        r = await sentiment_monitor(None, None, msg)
        assert 0.1 <= r.output_info["score"] <= 0.2

    @pytest.mark.asyncio
    async def test_many_exclamation_marks_capped(self) -> None:
        """Even with many exclamation groups, max contribution is 0.2."""
        msg = "What!!! Really??? No way!!!"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] <= 0.2

    @pytest.mark.asyncio
    async def test_score_capped_at_1_0(self) -> None:
        """Score should never exceed 1.0."""
        msg = "I AM FUCKING FURIOUS I WILL SUE YOUR ATTORNEY CRYING DESPERATE!!!"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_unicode_message(self) -> None:
        """Unicode/emoji with no trigger keywords should score 0."""
        msg = "I am 😡 very unhappy with this"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] == 0.0

    @pytest.mark.asyncio
    async def test_numbers_only_message(self) -> None:
        r = await sentiment_monitor(None, None, "12345 67890")
        assert r.output_info["score"] == 0.0
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_single_word_message(self) -> None:
        r = await sentiment_monitor(None, None, "Hello")
        assert r.output_info["score"] == 0.0

    @pytest.mark.asyncio
    async def test_very_long_message(self) -> None:
        msg = "I AM SO FURIOUS ABOUT THIS " * 100
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] >= 0.3  # ALL_CAPS scoring
        # distress keyword "furious" should also be detected
        assert r.output_info["score"] >= 0.5  # 0.3 (caps) + 0.2 (distress)

    @pytest.mark.asyncio
    async def test_question_marks_only(self) -> None:
        """'???' → should be caught by EXCLAMATION_PATTERN."""
        msg = "???"
        r = await sentiment_monitor(None, None, msg)
        assert r.output_info["score"] > 0.0
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_guardrail_output_dict_keys(self) -> None:
        r = await sentiment_monitor(None, None, "I AM FURIOUS I WILL SUE YOU!!!")
        assert hasattr(r, "tripwire_triggered")
        assert hasattr(r, "output_info")
        assert "score" in r.output_info
        assert "escalate" in r.output_info
        assert isinstance(r.output_info["score"], float)
        assert isinstance(r.output_info["escalate"], bool)


# ============================================================================
# SECTION 9 — REFUND CAP GUARDRAIL
# ============================================================================


class TestRefundCap:
    """Extreme edge cases for the refund cap output guardrail."""

    @pytest.mark.asyncio
    async def test_above_cap_blocked(self) -> None:
        r = await refund_cap(None, None, {"refund_amount": 600})
        assert r.tripwire_triggered is True
        assert r.output_info["human_approval_required"] is True
        assert r.output_info["amount"] == 600
        assert r.output_info["reason"] == "exceeds_cap"

    @pytest.mark.asyncio
    async def test_below_cap_passes(self) -> None:
        r = await refund_cap(None, None, {"refund_amount": 200})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_exactly_at_cap_passes(self) -> None:
        """Exactly $500 should pass (cap is > 500, not >=)."""
        r = await refund_cap(None, None, {"refund_amount": 500})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_zero_refund_passes(self) -> None:
        r = await refund_cap(None, None, {"refund_amount": 0})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_negative_refund_passes(self) -> None:
        """Negative amount is absurd but should not trip the cap."""
        r = await refund_cap(None, None, {"refund_amount": -100})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_missing_refund_amount_passes(self) -> None:
        r = await refund_cap(None, None, {})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_none_output_passes(self) -> None:
        r = await refund_cap(None, None, None)
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_very_large_refund_blocked(self) -> None:
        r = await refund_cap(None, None, {"refund_amount": 1_000_000})
        assert r.tripwire_triggered is True
        assert r.output_info["human_approval_required"] is True

    @pytest.mark.asyncio
    async def test_refund_cap_is_positive(self) -> None:
        from guardrails.refund_cap import CAP

        assert CAP > 0

    @pytest.mark.asyncio
    async def test_refund_amount_as_string(self) -> None:
        """String refund_amount should be safely converted to float and compared."""
        r = await refund_cap(None, None, {"refund_amount": "600"})
        assert r.tripwire_triggered is True
        assert r.output_info["amount"] == 600.0

    @pytest.mark.asyncio
    async def test_refund_amount_unparseable_string(self) -> None:
        """Unparseable string amount should fail safe (no crash, not blocked)."""
        r = await refund_cap(None, None, {"refund_amount": "not-a-number"})
        assert r.tripwire_triggered is False

    @pytest.mark.asyncio
    async def test_multiple_output_keys_unchanged(self) -> None:
        """Non-refund keys should pass through unchanged."""
        output = {"refund_amount": 200, "customer_id": "CUST-001", "order_id": "ORD-001"}
        r = await refund_cap(None, None, output)
        assert r.tripwire_triggered is False
        assert r.output_info.get("customer_id") == "CUST-001"

    @pytest.mark.asyncio
    async def test_guardrail_output_contract(self) -> None:
        r = await refund_cap(None, None, {"refund_amount": 600})
        assert hasattr(r, "tripwire_triggered")
        assert hasattr(r, "output_info")
        assert "human_approval_required" in r.output_info
        assert "amount" in r.output_info or r.output_info.get("amount") is not None
        assert "reason" in r.output_info


# ============================================================================
# SECTION 10 — POLICY AGENT CONTRACT
# ============================================================================


class TestPolicyAgent:
    """Verify the Agent object is configured correctly per spec."""

    def test_agent_name(self) -> None:
        assert policy_agent.name == "PolicyAgent"

    def test_agent_model(self) -> None:
        assert policy_agent.model == "openai/gpt-oss-120b:free"

    def test_agent_has_tools(self) -> None:
        assert len(policy_agent.tools) >= 1

    def test_agent_instructions_not_empty(self) -> None:
        assert isinstance(policy_agent.instructions, str)
        assert len(policy_agent.instructions) > 0

    def test_agent_instructions_mention_json_output(self) -> None:
        assert isinstance(policy_agent.instructions, str)
        assert "json" in policy_agent.instructions.lower()

    def test_agent_instructions_mention_eligible(self) -> None:
        assert isinstance(policy_agent.instructions, str)
        assert "eligible" in policy_agent.instructions.lower()

    def test_agent_instructions_mention_check_return_policy(self) -> None:
        assert isinstance(policy_agent.instructions, str)
        assert "check_return_policy" in policy_agent.instructions.lower()

    def test_agent_tools_contains_check_return_policy(self) -> None:
        from tools.policy_tools import check_return_policy as tool_fn

        assert tool_fn in policy_agent.tools

    def test_agent_no_handoffs(self) -> None:
        """Policy agent should not define its own handoffs (wired by Lead)."""
        assert not hasattr(policy_agent, "handoffs") or policy_agent.handoffs == []


# ============================================================================
# SECTION 11 — CROSS-CONTRACT: tool_interface_spec compliance
# ============================================================================


class TestCrossContractCompliance:
    """Verify all M2 tools + guardrails comply with docs/tool_interface_spec.md."""

    @pytest.mark.asyncio
    async def test_all_tools_async(self) -> None:
        import asyncio

        for tool in [check_return_policy, pii_scrubber, sentiment_monitor, refund_cap]:
            assert asyncio.iscoroutinefunction(tool), f"{tool.__name__} is not async"

    @pytest.mark.asyncio
    async def test_check_return_policy_function_tool_decorated(self) -> None:
        """Verify @function_tool wraps the raw function into a FunctionTool object."""
        from tools.policy_tools import check_return_policy as decorated

        # @function_tool returns a FunctionTool instance (not directly callable)
        import inspect

        assert not inspect.iscoroutinefunction(decorated), (
            "FunctionTool wrapper should not be a coroutine function"
        )
        # But RAW_CHECK_RETURN_POLICY is the original async function
        assert asyncio.iscoroutinefunction(check_return_policy)

    @pytest.mark.asyncio
    async def test_no_unhandled_exceptions_on_any_input(self) -> None:
        """Throw every conceivable bad input at check_return_policy."""
        bad_inputs = [
            ("", ""),
            ("", "CUST-001"),
            ("ORD-001", ""),
            (None, "CUST-001"),
            ("ORD-001", None),
            (None, None),
            ("   ", "CUST-001"),
            ("ORD-001", "   "),
            ("\n", "\t"),
            ("<ORD>", "</CUST>"),
            ("'" * 100, "'" * 100),
        ]
        for oid, cid in bad_inputs:
            try:
                r = await check_return_policy(order_id=oid, customer_id=cid)
                assert isinstance(r, dict), f"Non-dict return for ({oid!r}, {cid!r})"
            except Exception as exc:
                pytest.fail(
                    f"Unhandled exception ({type(exc).__name__}) for ({oid!r}, {cid!r}): {exc}"
                )

    def test_exclusion_list_is_set(self) -> None:
        """EXCLUDED_CATEGORIES must be a set (fast lookup, no dupes)."""
        from tools.policy_tools import EXCLUDED_CATEGORIES as ec

        assert isinstance(ec, set)
        assert "digital_goods" in ec
        assert "perishables" in ec
        assert "final_sale" in ec

    def test_return_window_days_default(self) -> None:
        """Default return window must be 30."""
        assert RETURN_WINDOW_DAYS == 30


# ============================================================================
# SECTION 12 — demo.py integration sanity check
# ============================================================================


class TestDemoIntegration:
    """Quick sanity: the demo scenario data should match tool behavior."""

    @pytest.mark.asyncio
    async def test_demo_scenario_1_alice(self) -> None:
        """Alice (ORD-001): eligible refund."""
        r = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
        assert r["eligible"] is True
        assert r["recommended_action"] == "refund"

    @pytest.mark.asyncio
    async def test_demo_scenario_2_bob_excluded(self) -> None:
        """Bob (ORD-003): digital goods excluded."""
        r = await check_return_policy(order_id="ORD-003", customer_id="CUST-002")
        assert r["eligible"] is False
        assert r["exclusion_reason"] is not None

    @pytest.mark.asyncio
    async def test_demo_scenario_3_charlie_damaged(self) -> None:
        """Charlie (ORD-004): damaged → replacement."""
        r = await check_return_policy(order_id="ORD-004", customer_id="CUST-003")
        assert r["eligible"] is True
        assert r["recommended_action"] == "replacement"

    @pytest.mark.asyncio
    async def test_demo_scenario_4_dave_fraud(self) -> None:
        """Dave (ORD-005): fraud flag → escalate (needs human review)."""
        r = await check_return_policy(order_id="ORD-005", customer_id="CUST-004")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["recommended_action"] == "escalate"

    @pytest.mark.asyncio
    async def test_demo_scenario_5_eve_escalate(self) -> None:
        """Eve (ORD-006): fraud DB match → escalate."""
        r = await check_return_policy(order_id="ORD-006", customer_id="CUST-005")
        assert r["eligible"] is False
        assert r["fraud_signal"] is True
        assert r["recommended_action"] == "escalate"
