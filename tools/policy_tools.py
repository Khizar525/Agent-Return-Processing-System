"""
Policy Tools — Return Policy Checker
Owner: Member 2

Validates return eligibility against business rules.
Called by the Policy Agent via @function_tool.

Output contract defined in docs/tool_interface_spec.md.
"""

import os
from typing import Any
from agents import function_tool  # type: ignore[attr-defined]

RAW_CHECK_RETURN_POLICY: Any = None
check_return_policy: Any = None

RETURN_WINDOW_DAYS = int(os.environ.get("RETURN_WINDOW_DAYS", "30"))
EXCLUDED_CATEGORIES = {"digital_goods", "perishables", "final_sale"}

MOCK_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-001": {"customer_id": "CUST-001", "item_category": "electronics", "days_since_purchase": 15, "price": 199.99, "damaged": False},
    "ORD-002": {"customer_id": "CUST-001", "item_category": "electronics", "days_since_purchase": 45, "price": 299.99, "damaged": False},
    "ORD-003": {"customer_id": "CUST-002", "item_category": "digital_goods", "days_since_purchase": 5, "price": 49.99, "damaged": False},
    "ORD-004": {"customer_id": "CUST-003", "item_category": "clothing", "days_since_purchase": 10, "price": 89.99, "damaged": True},
    "ORD-005": {"customer_id": "CUST-004", "item_category": "home_goods", "days_since_purchase": 20, "price": 150.00, "damaged": False},
    "ORD-006": {"customer_id": "CUST-005", "item_category": "electronics", "days_since_purchase": 3, "price": 799.99, "damaged": False},
}

MOCK_CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-001": {"fraud_flag": False, "fraud_reason": None},
    "CUST-002": {"fraud_flag": False, "fraud_reason": None},
    "CUST-003": {"fraud_flag": False, "fraud_reason": None},
    "CUST-004": {"fraud_flag": True, "fraud_reason": "chargeback_history"},
    "CUST-005": {"fraud_flag": False, "fraud_reason": None},
}

FRAUD_DB_MATCHES: dict[str, str] = {
    "CUST-005": "suspicious_pattern_alpha",
}


def _build_error(error: str, days: int = 0, category: str = "") -> dict[str, Any]:
    return {
        "success": False,
        "error": error,
        "eligible": False,
        "reason": error,
        "recommended_action": "reject",
        "return_window_days": RETURN_WINDOW_DAYS,
        "days_since_purchase": days,
        "item_category": category,
        "exclusion_reason": None,
        "fraud_signal": False,
    }


async def _check_return_policy_impl(order_id: str, customer_id: str) -> dict[str, Any]:
    order = MOCK_ORDERS.get(order_id)
    if order is None:
        return _build_error(f"Order {order_id} not found")

    customer = MOCK_CUSTOMERS.get(customer_id)
    if customer is None:
        return _build_error(
            f"Customer {customer_id} not found",
            days=order["days_since_purchase"],
            category=str(order["item_category"]),
        )

    if order["customer_id"] != customer_id:
        return _build_error(
            "Order does not belong to this customer",
            days=order["days_since_purchase"],
            category=str(order["item_category"]),
        )

    window_ok = order["days_since_purchase"] <= RETURN_WINDOW_DAYS
    not_excluded = order["item_category"] not in EXCLUDED_CATEGORIES
    fraud_flag = bool(customer["fraud_flag"])
    fraud_db_match = FRAUD_DB_MATCHES.get(customer_id)
    fraud_signal = fraud_flag or fraud_db_match is not None

    reasons: list[str] = []
    exclusion_reason: str | None = None
    if not window_ok:
        reasons.append(f"Return window of {RETURN_WINDOW_DAYS} days exceeded ({order['days_since_purchase']} days since purchase)")
    if not not_excluded:
        exclusion_reason = f"Item category '{order['item_category']}' is excluded"
        reasons.append(exclusion_reason)
    if fraud_flag:
        reasons.append(f"Fraud flag on account: {customer['fraud_reason']}")
    if fraud_db_match:
        reasons.append(f"Fraud DB match: {fraud_db_match}")

    eligible = window_ok and not_excluded and not fraud_flag and fraud_db_match is None
    reason = "; ".join(reasons) if reasons else "Return eligible"

    if fraud_flag:
        recommended_action = "reject"
    elif fraud_db_match and not fraud_flag:
        recommended_action = "escalate"
    elif not eligible:
        recommended_action = "reject"
    elif order["damaged"]:
        recommended_action = "replacement"
    else:
        recommended_action = "refund"

    return {
        "eligible": eligible,
        "reason": reason,
        "recommended_action": recommended_action,
        "return_window_days": RETURN_WINDOW_DAYS,
        "days_since_purchase": order["days_since_purchase"],
        "item_category": order["item_category"],
        "exclusion_reason": exclusion_reason,
        "fraud_signal": fraud_signal,
        "error": None,
    }

RAW_CHECK_RETURN_POLICY = _check_return_policy_impl
check_return_policy = function_tool(_check_return_policy_impl)
