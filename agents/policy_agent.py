"""
Policy Agent
Owner: Member 2 (updated Phase 2 — Project Lead)

Validates return eligibility against business rules.
Called via handoff from Triage Orchestrator.

Output JSON:
    {
        "eligible": bool,
        "reason": str,
        "recommended_action": str   # "refund" | "replacement" | "reject" | "escalate"
    }

Dependencies:
    - tools/policy_tools.py    (check_return_policy)    — Project Lead
    - tools/crm_tools.py       (get_customer_profile)   — Member 3 (optional)

Rules to enforce:
    1. Return window <= RETURN_WINDOW_DAYS (default 30, set in .env)
    2. Item not in exclusion list (digital goods, perishables, final-sale)
    3. No active fraud flag on customer account
    4. Cross-reference request against fraud DB before approving
"""

from agents import Agent

from tools.policy_tools import check_return_policy

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
    tools=[check_return_policy],
)
