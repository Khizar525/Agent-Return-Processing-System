"""
Tracking Tools — Test Suite
Owner: Project Lead

Tests tracking_lookup and faq_lookup tools under normal, edge, and error cases.

Run:  pytest tests/test_tracking_tools.py -v
"""

from __future__ import annotations

import pytest

from tools.tracking_tools import (
    RAW_TRACKING_LOOKUP as tracking_lookup,
    RAW_FAQ_LOOKUP as faq_lookup,
    set_repo_for_testing,
    reset_repo_for_testing,
    reset_tracking_data_for_testing,
)
from database.repository import MemoryBackend


@pytest.fixture(autouse=True)
def _setup_test_repo() -> None:
    """Inject a fresh MemoryBackend before every test."""
    set_repo_for_testing(MemoryBackend())
    yield
    reset_repo_for_testing()
    reset_tracking_data_for_testing()


# ============================================================================
# TRACKING LOOKUP — NOMINAL PATHS
# ============================================================================


class TestTrackingLookupNominal:
    """Happy-path scenarios for order tracking."""

    @pytest.mark.asyncio
    async def test_delivered_order(self) -> None:
        r = await tracking_lookup("ORD-001")
        assert r["success"] is True
        assert r["found"] is True
        assert r["status"] == "delivered"
        assert r["carrier"] == "fedex"
        assert r["tracking_number"] is not None

    @pytest.mark.asyncio
    async def test_in_transit_order(self) -> None:
        r = await tracking_lookup("ORD-002")
        assert r["success"] is True
        assert r["found"] is True
        assert r["status"] == "in_transit"
        assert r["carrier"] == "ups"

    @pytest.mark.asyncio
    async def test_processing_order(self) -> None:
        r = await tracking_lookup("ORD-003")
        assert r["success"] is True
        assert r["found"] is True
        assert r["status"] == "processing"

    @pytest.mark.asyncio
    async def test_exception_order(self) -> None:
        r = await tracking_lookup("ORD-005")
        assert r["success"] is True
        assert r["found"] is True
        assert r["status"] == "exception"

    @pytest.mark.asyncio
    async def test_order_not_in_tracking_data_but_in_repo(self) -> None:
        """Order exists in repo but not in tracking data → defaults to processing."""
        r = await tracking_lookup("ORD-015")
        assert r["success"] is True
        assert r["found"] is True
        assert r["status"] == "processing"


# ============================================================================
# TRACKING LOOKUP — ERROR PATHS
# ============================================================================


class TestTrackingLookupErrors:
    """Error scenarios for order tracking."""

    @pytest.mark.asyncio
    async def test_order_not_found(self) -> None:
        r = await tracking_lookup("ORD-DOES-NOT-EXIST")
        assert r["success"] is False
        assert r["found"] is False
        assert r["error"] is not None
        assert "not found" in r["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_order_id(self) -> None:
        r = await tracking_lookup("")
        assert r["success"] is False
        assert r["error"] is not None

    @pytest.mark.asyncio
    async def test_whitespace_order_id(self) -> None:
        r = await tracking_lookup("   ")
        assert r["success"] is False
        assert r["error"] is not None

    @pytest.mark.asyncio
    async def test_none_like_order_id(self) -> None:
        r = await tracking_lookup("None")
        assert r["success"] is False
        assert r["error"] is not None


# ============================================================================
# TRACKING LOOKUP — OUTPUT CONTRACT
# ============================================================================


class TestTrackingLookupContract:
    """Verify output dict has all required keys with correct types."""

    @pytest.mark.asyncio
    async def test_success_output_keys(self) -> None:
        r = await tracking_lookup("ORD-001")
        expected_keys = {
            "success", "found", "status", "carrier",
            "tracking_number", "estimated_delivery", "last_update", "error",
        }
        assert set(r.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_error_output_keys(self) -> None:
        r = await tracking_lookup("ORD-NOPE")
        expected_keys = {
            "success", "found", "status", "carrier",
            "tracking_number", "estimated_delivery", "last_update", "error",
        }
        assert set(r.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_success_field_is_bool(self) -> None:
        r = await tracking_lookup("ORD-001")
        assert isinstance(r["success"], bool)

    @pytest.mark.asyncio
    async def test_found_field_is_bool(self) -> None:
        r = await tracking_lookup("ORD-001")
        assert isinstance(r["found"], bool)

    @pytest.mark.asyncio
    async def test_idempotent(self) -> None:
        r1 = await tracking_lookup("ORD-001")
        r2 = await tracking_lookup("ORD-001")
        assert r1 == r2


# ============================================================================
# FAQ LOOKUP — NOMINAL PATHS
# ============================================================================


class TestFaqLookupNominal:
    """Happy-path scenarios for FAQ keyword matching."""

    @pytest.mark.asyncio
    async def test_return_window_question(self) -> None:
        r = await faq_lookup("What is your return window?")
        assert r["success"] is True
        assert r["matched_keyword"] == "return window"
        assert r["answer"] is not None
        assert len(r["answer"]) > 0

    @pytest.mark.asyncio
    async def test_refund_question(self) -> None:
        r = await faq_lookup("How long do refunds take?")
        assert r["success"] is True
        assert r["matched_keyword"] == "refund"

    @pytest.mark.asyncio
    async def test_shipping_question(self) -> None:
        r = await faq_lookup("What are your shipping options?")
        assert r["success"] is True
        assert r["matched_keyword"] == "shipping"

    @pytest.mark.asyncio
    async def test_tracking_question(self) -> None:
        r = await faq_lookup("How do I track my order?")
        assert r["success"] is True
        assert r["matched_keyword"] in ("tracking", "track")

    @pytest.mark.asyncio
    async def test_damaged_item_question(self) -> None:
        r = await faq_lookup("My item arrived damaged. What do I do?")
        assert r["success"] is True
        assert r["matched_keyword"] == "damaged"

    @pytest.mark.asyncio
    async def test_exchange_question(self) -> None:
        r = await faq_lookup("Can I exchange my item?")
        assert r["success"] is True
        assert r["matched_keyword"] == "exchange"

    @pytest.mark.asyncio
    async def test_cancel_question(self) -> None:
        r = await faq_lookup("Can I cancel my order?")
        assert r["success"] is True
        assert r["matched_keyword"] == "cancel"

    @pytest.mark.asyncio
    async def test_warranty_question(self) -> None:
        r = await faq_lookup("Do you offer a warranty?")
        assert r["success"] is True
        assert r["matched_keyword"] == "warranty"

    @pytest.mark.asyncio
    async def test_price_match_question(self) -> None:
        r = await faq_lookup("Do you price match?")
        assert r["success"] is True
        assert r["matched_keyword"] == "price match"


# ============================================================================
# FAQ LOOKUP — ERROR PATHS
# ============================================================================


class TestFaqLookupErrors:
    """Error scenarios for FAQ matching."""

    @pytest.mark.asyncio
    async def test_no_match(self) -> None:
        r = await faq_lookup("How do I reset my password?")
        assert r["success"] is False
        assert r["matched_keyword"] is None
        assert r["error"] is not None

    @pytest.mark.asyncio
    async def test_empty_query(self) -> None:
        r = await faq_lookup("")
        assert r["success"] is False
        assert r["error"] is not None

    @pytest.mark.asyncio
    async def test_whitespace_query(self) -> None:
        r = await faq_lookup("   ")
        assert r["success"] is False
        assert r["error"] is not None

    @pytest.mark.asyncio
    async def test_unrelated_query(self) -> None:
        r = await faq_lookup("What is the meaning of life?")
        assert r["success"] is False
        assert r["matched_keyword"] is None


# ============================================================================
# FAQ LOOKUP — OUTPUT CONTRACT
# ============================================================================


class TestFaqLookupContract:
    """Verify output dict has all required keys with correct types."""

    @pytest.mark.asyncio
    async def test_success_output_keys(self) -> None:
        r = await faq_lookup("refund")
        expected_keys = {"success", "matched_keyword", "answer", "confidence", "error"}
        assert set(r.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_error_output_keys(self) -> None:
        r = await faq_lookup("xyzzy")
        expected_keys = {"success", "matched_keyword", "answer", "confidence", "error"}
        assert set(r.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_confidence_is_float(self) -> None:
        r = await faq_lookup("return window")
        assert isinstance(r["confidence"], float)

    @pytest.mark.asyncio
    async def test_confidence_between_0_and_1(self) -> None:
        r = await faq_lookup("return window")
        assert 0.0 <= r["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_idempotent(self) -> None:
        r1 = await faq_lookup("refund")
        r2 = await faq_lookup("refund")
        assert r1 == r2
