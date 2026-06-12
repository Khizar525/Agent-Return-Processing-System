"""
Billing Agent
Owner: TBD (Phase 2)

Handles billing disputes (incorrect charges, duplicate transactions).
Called via handoff from Triage Orchestrator for billing_dispute intents.

Dependencies:
    - tools/payment_tools.py  (process_refund)          — Member 3
    - guardrails/refund_cap.py                          — Member 2

Model: deepseek-v4-flash-free
"""

from agents import Agent

# TODO: implement billing agent with proper tools from M3 and M4
billing_agent = Agent(
    name="BillingAgent",
    instructions=(
        "You are the Billing Dispute Specialist.\n\n"
        "Your job is to investigate and resolve billing issues:\n"
        "- Duplicate charges\n"
        "- Incorrect amounts\n"
        "- Unauthorized transactions\n\n"
        "Steps:\n"
        "1. Ask for order_id if not provided.\n"
        "2. Investigate the transaction history.\n"
        "3. If a refund is needed, explain the amount and seek confirmation.\n"
        "4. Never process a refund over $500 without human approval.\n\n"
        "Output a clear summary of the dispute and resolution."
    ),
    model="deepseek-v4-flash-free",
    # tools=[process_refund],  # uncomment after M3 merges
)
