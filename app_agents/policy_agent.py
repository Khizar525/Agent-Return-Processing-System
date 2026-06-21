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
    - guardrails/refund_cap.py                           — Member 2 (you)

Rules to enforce:
    1. Return window <= RETURN_WINDOW_DAYS (default 30, set in .env)
    2. Item not in exclusion list (digital goods, perishables, final-sale)
    3. No active fraud flag on customer account
    4. Cross-reference request against fraud DB before approving
"""

from typing import Literal

from pydantic import BaseModel
from agents import Agent
from tools.policy_tools import check_return_policy
from tools.crm_tools import get_customer_profile


class PolicyDecision(BaseModel):
    eligible: bool
    reason: str
    recommended_action: Literal["refund", "replacement", "reject", "escalate"]


policy_agent = Agent(
    name="PolicyAgent",
    instructions="""
    You validate return eligibility for customer orders.

    Rules:
    1. Call check_return_policy(order_id, customer_id) to evaluate eligibility.
    2. If eligible is true and recommended_action is "refund" or "replacement", pass through to resolution.
    3. If eligible is false, explain the reason clearly.
    4. If recommended_action is "escalate", recommend human review.

    Always include customer_id and session_id in context when handing off.
    Output must be valid JSON: {{"eligible": bool, "reason": str, "recommended_action": str}}
    """,
    model="deepseek-v4-flash-free",
    tools=[check_return_policy, get_customer_profile],
    output_type=PolicyDecision,
)
