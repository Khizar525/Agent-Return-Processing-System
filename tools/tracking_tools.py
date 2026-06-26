"""
Tracking Tools — Order Tracking & FAQ Lookup
Owner: Project Lead

Provides two tool-call targets for the Triage Orchestrator:
  - tracking_lookup: looks up order shipping status from the repository
  - faq_lookup: keyword-matches customer questions against an FAQ database

These are tool-call targets (not handoffs) — the Triage Orchestrator retains
context and responds directly to the customer.

Output contracts defined in docs/tool_interface_spec.md.
"""

from __future__ import annotations

from typing import Any

from agents import function_tool

from database.repository import create_repository, Repository

# ── Repository singleton ─────────────────────────────────────────────────────

_repo: Repository | None = None


def _get_repo() -> Repository:
    global _repo
    if _repo is None:
        _repo = create_repository()
    return _repo


def set_repo_for_testing(repo: Repository) -> None:
    """Inject a test repository (used by tests only)."""
    global _repo
    _repo = repo


def reset_repo_for_testing() -> None:
    """Reset to default repository (used by tests only)."""
    global _repo
    _repo = None


# ── Tracking status mock data ────────────────────────────────────────────────
# In production this would come from FedEx/UPS API.
# For dev/test, we use a simple dict keyed by order_id.

_TRACKING_DATA: dict[str, dict[str, Any]] = {
    "ORD-001": {
        "status": "delivered",
        "carrier": "fedex",
        "tracking_number": "FX-9283746510",
        "estimated_delivery": "2026-05-20T18:00:00Z",
        "last_update": "2026-05-19T14:32:00Z",
    },
    "ORD-002": {
        "status": "in_transit",
        "carrier": "ups",
        "tracking_number": "UP-1827364510",
        "estimated_delivery": "2026-06-28T12:00:00Z",
        "last_update": "2026-06-23T09:15:00Z",
    },
    "ORD-003": {
        "status": "processing",
        "carrier": "fedex",
        "tracking_number": "FX-5647382910",
        "estimated_delivery": "2026-06-30T18:00:00Z",
        "last_update": "2026-06-22T16:45:00Z",
    },
    "ORD-004": {
        "status": "delivered",
        "carrier": "ups",
        "tracking_number": "UP-3746581920",
        "estimated_delivery": "2026-05-10T12:00:00Z",
        "last_update": "2026-05-09T11:20:00Z",
    },
    "ORD-005": {
        "status": "exception",
        "carrier": "fedex",
        "tracking_number": "FX-8372615409",
        "estimated_delivery": "2026-06-25T18:00:00Z",
        "last_update": "2026-06-21T08:00:00Z",
    },
    "ORD-006": {
        "status": "in_transit",
        "carrier": "fedex",
        "tracking_number": "FX-4657382910",
        "estimated_delivery": "2026-06-27T18:00:00Z",
        "last_update": "2026-06-23T10:00:00Z",
    },
    "ORD-007": {
        "status": "processing",
        "carrier": "ups",
        "tracking_number": "UP-9283746510",
        "estimated_delivery": "2026-06-29T12:00:00Z",
        "last_update": "2026-06-23T08:30:00Z",
    },
    "ORD-008": {
        "status": "in_transit",
        "carrier": "fedex",
        "tracking_number": "FX-1728394051",
        "estimated_delivery": "2026-06-26T18:00:00Z",
        "last_update": "2026-06-23T11:45:00Z",
    },
    "ORD-009": {
        "status": "delivered",
        "carrier": "ups",
        "tracking_number": "UP-5849302716",
        "estimated_delivery": "2026-05-25T12:00:00Z",
        "last_update": "2026-05-24T15:10:00Z",
    },
    "ORD-010": {
        "status": "in_transit",
        "carrier": "fedex",
        "tracking_number": "FX-3948576012",
        "estimated_delivery": "2026-06-28T18:00:00Z",
        "last_update": "2026-06-22T13:20:00Z",
    },
}


def set_tracking_data_for_testing(data: dict[str, dict[str, Any]]) -> None:
    """Inject test tracking data."""
    _TRACKING_DATA.update(data)


def reset_tracking_data_for_testing() -> None:
    """Reset tracking data to defaults."""
    _TRACKING_DATA.clear()
    _TRACKING_DATA.update(_DEFAULT_TRACKING_DATA)


# Keep a copy of defaults for reset
_DEFAULT_TRACKING_DATA = dict(_TRACKING_DATA)


# ── FAQ database ─────────────────────────────────────────────────────────────

_FAQ_DATABASE: list[dict[str, str]] = [
    {
        "keyword": "return window",
        "question": "What is your return window?",
        "answer": "Our return window is 30 days from the date of purchase. "
        "Items must be in their original condition with receipt.",
    },
    {
        "keyword": "return",
        "question": "How do I return an item?",
        "answer": "To return an item, go to My Orders, select the order, "
        "and click 'Start Return'. You'll receive a prepaid shipping label.",
    },
    {
        "keyword": "refund",
        "question": "How long do refunds take?",
        "answer": "Refunds are processed within 5-7 business days after we "
        "receive the returned item. The credit will appear on your statement "
        "within 1-2 billing cycles.",
    },
    {
        "keyword": "shipping",
        "question": "What are your shipping options?",
        "answer": "We offer Standard (5-7 days), Expedited (2-3 days), and "
        "Overnight shipping. Free standard shipping on orders over $50.",
    },
    {
        "keyword": "tracking",
        "question": "Where is my order?",
        "answer": "You can track your order in My Orders. Click the tracking "
        "link next to your order for real-time updates from the carrier.",
    },
    {
        "keyword": "track",
        "question": "How do I track my order?",
        "answer": "You can track your order in My Orders. Click the tracking "
        "link next to your order for real-time updates from the carrier.",
    },
    {
        "keyword": "damaged",
        "question": "My item arrived damaged. What do I do?",
        "answer": "We're sorry about that! Please take photos of the damage "
        "and contact us within 48 hours. We'll arrange a replacement or full refund.",
    },
    {
        "keyword": "exchange",
        "question": "Can I exchange my item?",
        "answer": "Yes! You can request an exchange within 30 days. Select "
        "'Exchange' when starting your return and choose the new item.",
    },
    {
        "keyword": "payment",
        "question": "What payment methods do you accept?",
        "answer": "We accept Visa, Mastercard, American Express, Discover, PayPal, and Apple Pay.",
    },
    {
        "keyword": "account",
        "question": "How do I create an account?",
        "answer": "Click 'Sign Up' on our homepage. You'll need an email "
        "address and password. You can also sign up during checkout.",
    },
    {
        "keyword": "cancel",
        "question": "Can I cancel my order?",
        "answer": "Orders can be cancelled within 1 hour of placement. "
        "After that, the order enters processing and cannot be cancelled.",
    },
    {
        "keyword": "warranty",
        "question": "Do you offer a warranty?",
        "answer": "All electronics come with a 1-year manufacturer warranty. "
        "Extended warranty options are available at checkout.",
    },
    {
        "keyword": "price match",
        "question": "Do you price match?",
        "answer": "Yes! We offer price matching within 14 days of purchase. "
        "Contact us with the competitor's link and we'll adjust the price.",
    },
]


# ── Tool implementations ─────────────────────────────────────────────────────


async def _tracking_lookup_impl(order_id: str) -> dict[str, Any]:
    """
    Look up shipping/tracking information for an order.

    Returns tracking status, carrier, tracking number, and estimated delivery.
    """
    try:
        if not order_id or not order_id.strip():
            return {
                "success": False,
                "found": False,
                "status": None,
                "carrier": None,
                "tracking_number": None,
                "estimated_delivery": None,
                "last_update": None,
                "error": "Order ID is required",
            }

        order_id = order_id.strip()

        # Check tracking data first
        tracking = _TRACKING_DATA.get(order_id)
        if tracking:
            return {
                "success": True,
                "found": True,
                "status": tracking["status"],
                "carrier": tracking["carrier"],
                "tracking_number": tracking["tracking_number"],
                "estimated_delivery": tracking["estimated_delivery"],
                "last_update": tracking["last_update"],
                "error": None,
            }

        # Fall back to repository — if order exists, generate a basic tracking response
        repo = _get_repo()
        order = await repo.get_order(order_id)
        if order is None:
            return {
                "success": False,
                "found": False,
                "status": None,
                "carrier": None,
                "tracking_number": None,
                "estimated_delivery": None,
                "last_update": None,
                "error": f"Order {order_id} not found",
            }

        # Order exists but no tracking data — assume processing
        return {
            "success": True,
            "found": True,
            "status": "processing",
            "carrier": "fedex",
            "tracking_number": f"FX-{order_id.upper().replace('-', '')}",
            "estimated_delivery": None,
            "last_update": None,
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "found": False,
            "status": None,
            "carrier": None,
            "tracking_number": None,
            "estimated_delivery": None,
            "last_update": None,
            "error": f"Unexpected error: {exc}",
        }


async def _faq_lookup_impl(query: str) -> dict[str, Any]:
    """
    Look up an answer to a customer FAQ question via keyword matching.

    Returns the matched keyword and answer if found, or an error if no match.
    """
    if not query or not query.strip():
        return {
            "success": False,
            "matched_keyword": None,
            "answer": None,
            "confidence": 0.0,
            "error": "Query is required",
        }

    query_lower = query.lower().strip()

    best_match: dict[str, str] | None = None
    best_score = 0

    for faq in _FAQ_DATABASE:
        keyword = faq["keyword"].lower()
        # Exact keyword match
        if keyword in query_lower:
            score = len(keyword) / len(query_lower)
            if score > best_score:
                best_score = score
                best_match = faq

    if best_match:
        return {
            "success": True,
            "matched_keyword": best_match["keyword"],
            "answer": best_match["answer"],
            "confidence": min(best_score, 1.0),
            "error": None,
        }

    return {
        "success": False,
        "matched_keyword": None,
        "answer": None,
        "confidence": 0.0,
        "error": f"No FAQ match found for query: {query[:100]}",
    }


# ── FunctionTool wrappers ────────────────────────────────────────────────────

RAW_TRACKING_LOOKUP = _tracking_lookup_impl
RAW_FAQ_LOOKUP = _faq_lookup_impl

tracking_lookup = function_tool(_tracking_lookup_impl)
faq_lookup = function_tool(_faq_lookup_impl)
