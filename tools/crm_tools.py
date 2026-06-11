"""
CRM Tools
Owner: Member 3

Fetches customer data from the CRM API.

Interface Spec (do not change signatures without Lead approval):
    get_customer_profile(customer_id: str) -> dict
        Returns:
            {
                "customer_id": str,
                "name": str,
                "email": str,
                "phone": str,
                "loyalty_tier": str,       # "bronze" | "silver" | "gold" | "platinum"
                "order_history": list[dict],
                "past_returns": list[dict],
                "fraud_flag": bool,
                "fraud_reason": str | None,
            }

Environment variables required:
    CRM_BASE_URL
    CRM_API_KEY
"""

from typing import Any
from agents import function_tool  # type: ignore[attr-defined]


# TODO (Member 3): implement get_customer_profile below
@function_tool  # type: ignore[untyped-decorator]
async def get_customer_profile(customer_id: str) -> dict[str, Any]:
    """Fetch full customer profile including order history and fraud flags."""
    raise NotImplementedError("Member 3: implement get_customer_profile")
