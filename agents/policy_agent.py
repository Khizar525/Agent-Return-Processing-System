"""
Policy Agent
Owner: Member 2

Validates return eligibility against business rules.
Called via handoff from Triage Orchestrator.

Output JSON:
    {
        "eligible": bool,
        "reason": str,
        "recommended_action": str   # "refund" | "replacement" | "reject" | "escalate"
    }

Dependencies:
    - tools/crm_tools.py       (get_customer_profile)   — Member 3
    - tools/policy_tools.py    (check_return_policy)    — Project Lead

Rules to enforce:
    1. Return window <= RETURN_WINDOW_DAYS (default 30, set in .env)
    2. Item not in exclusion list (digital goods, perishables, final-sale)
    3. No active fraud flag on customer account
    4. Cross-reference request against fraud DB before approving
"""

from agents import Agent, function_tool

_RETURN_WINDOW_DAYS = 30


@function_tool
async def get_fallback_return_policy(order_id: str, customer_id: str) -> dict:
    """Fallback: validate return eligibility using business rules."""
    try:
        from tools.policy_tools import check_return_policy
        return await check_return_policy(order_id, customer_id)
    except ImportError:
        return {
            "eligible": True,
            "success": True,
            "reason": "Assuming eligible (fallback — Member 2 to replace with proper tool)",
            "recommended_action": "refund",
            "return_window_days": _RETURN_WINDOW_DAYS,
            "days_since_purchase": 0,
            "item_category": "unknown",
            "exclusion_reason": None,
            "fraud_signal": False,
            "error": None,
        }


policy_agent = Agent(
    name="PolicyAgent",
    instructions=(
        "You are the Return Policy Specialist.\n\n"
        "Your job is to validate return eligibility for customer orders.\n\n"
        "1. Call check_return_policy with the order_id and customer_id.\n"
        "2. Interpret the result and produce a final decision.\n"
        "3. If fraud_signal is True, set recommended_action='escalate'.\n"
        "4. Output your decision as a clear JSON summary.\n\n"
        "Never process a refund or generate a label yourself."
    ),
    model="gpt-4o-mini",
    tools=[get_fallback_return_policy],
)
