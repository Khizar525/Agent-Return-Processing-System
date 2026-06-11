"""
Payment Tools
Owner: Member 3

Processes refunds via Stripe or PayPal.

Interface Spec (do not change signatures without Lead approval):
    process_refund(order_id: str, amount_usd: float, method: str) -> dict
        Args:
            order_id:   the original order identifier
            amount_usd: refund amount in USD (must be <= REFUND_CAP_USD from .env)
            method:     "stripe" | "paypal"
        Returns:
            {
                "success": bool,
                "transaction_id": str,
                "refund_amount": float,
                "currency": str,
                "estimated_days": int,
                "error": str | None,
            }

IMPORTANT: This tool must check the refund cap guardrail before calling
           the payment API. If amount_usd > REFUND_CAP_USD, raise a
           ValueError with message "human_approval_required".

Environment variables required:
    STRIPE_SECRET_KEY
    PAYPAL_CLIENT_ID
    PAYPAL_CLIENT_SECRET
    PAYPAL_BASE_URL
"""

from typing import Any
from agents import function_tool  # type: ignore[attr-defined]


# TODO (Member 3): implement process_refund below
@function_tool  # type: ignore[untyped-decorator]
async def process_refund(order_id: str, amount_usd: float, method: str) -> dict[str, Any]:
    """Issue a refund to the customer's original payment method."""
    raise NotImplementedError("Member 3: implement process_refund")
