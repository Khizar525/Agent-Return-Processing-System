"""
Policy Tools
Owner: Project Lead

Validates return eligibility against business rules.
Reads fixture data for Phase 1; production would hit CRM/OMS APIs.

Interface Spec (do not change signatures without Lead approval):
    check_return_policy(order_id: str, customer_id: str) -> dict
"""

import json
import os

from agents import function_tool

_RETURN_WINDOW_DAYS = int(os.environ.get("RETURN_WINDOW_DAYS", "30"))


def _load_fixtures() -> tuple[list, list]:
    base = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
    with open(os.path.join(base, "orders.json")) as f:
        orders: list[dict] = json.load(f)
    with open(os.path.join(base, "customers.json")) as f:
        customers: list[dict] = json.load(f)
    return orders, customers


async def check_return_policy_impl(order_id: str, customer_id: str) -> dict:
    """Implementation of return policy check — callable from tests directly."""
    try:
        orders, customers = _load_fixtures()
    except Exception as exc:
        return _error_result(f"Failed to load data: {exc}")

    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return _result(
            eligible=False,
            reason=f"Order {order_id} not found",
            recommended_action="reject",
            exclusion_reason="order_not_found",
        )

    customer = next((c for c in customers if c["customer_id"] == customer_id), None)
    if not customer:
        return _result(
            eligible=False,
            reason=f"Customer {customer_id} not found",
            recommended_action="reject",
            exclusion_reason="customer_not_found",
        )

    if customer.get("fraud_flag"):
        fraud_reason = customer.get("fraud_reason", "Active fraud flag on account")
        return _result(
            eligible=False,
            reason=fraud_reason,
            recommended_action="escalate",
            fraud_signal=True,
            item_category=_first_category(order),
            days_since_purchase=order.get("days_since_purchase", 0),
            exclusion_reason="fraud_flag",
        )

    items = order.get("items", [])
    if not items:
        return _result(
            eligible=False,
            reason="No items found in order",
            recommended_action="reject",
            item_category="unknown",
            days_since_purchase=order.get("days_since_purchase", 0),
            exclusion_reason="no_items",
        )

    item = items[0]
    days = order.get("days_since_purchase", 0)
    category = item.get("category", "unknown")
    excluded = item.get("excluded", False)

    if excluded:
        exclusion_reason = item.get(
            "exclusion_reason",
            f"Category '{category}' is excluded from returns policy",
        )
        return _result(
            eligible=False,
            reason=exclusion_reason,
            recommended_action="reject",
            item_category=category,
            days_since_purchase=days,
            exclusion_reason=exclusion_reason,
        )

    if days > _RETURN_WINDOW_DAYS:
        return _result(
            eligible=False,
            reason=f"Return window expired: {days} days since purchase (limit is {_RETURN_WINDOW_DAYS} days)",
            recommended_action="reject",
            item_category=category,
            days_since_purchase=days,
            exclusion_reason="return_window_expired",
        )

    return _result(
        eligible=True,
        reason="Item within 30-day return window, no fraud flag, category not excluded",
        recommended_action="refund",
        item_category=category,
        days_since_purchase=days,
    )


@function_tool
async def check_return_policy(order_id: str, customer_id: str) -> dict:
    """Validate whether a customer's order is eligible for return based on
    return window, item category exclusions, and fraud signals."""
    return await check_return_policy_impl(order_id, customer_id)


def _first_category(order: dict) -> str:
    items = order.get("items", [])
    return items[0].get("category", "unknown") if items else "unknown"


def _result(
    *,
    eligible: bool,
    reason: str,
    recommended_action: str,
    item_category: str = "unknown",
    days_since_purchase: int = 0,
    exclusion_reason: str | None = None,
    fraud_signal: bool = False,
) -> dict:
    return {
        "eligible": eligible,
        "success": False if not eligible else True,
        "reason": reason,
        "recommended_action": recommended_action,
        "return_window_days": _RETURN_WINDOW_DAYS,
        "days_since_purchase": days_since_purchase,
        "item_category": item_category,
        "exclusion_reason": exclusion_reason,
        "fraud_signal": fraud_signal,
        "error": None,
    }


def _error_result(error_msg: str) -> dict:
    return {
        "eligible": False,
        "success": False,
        "reason": "",
        "recommended_action": "reject",
        "return_window_days": _RETURN_WINDOW_DAYS,
        "days_since_purchase": 0,
        "item_category": "",
        "exclusion_reason": None,
        "fraud_signal": False,
        "error": error_msg,
    }
