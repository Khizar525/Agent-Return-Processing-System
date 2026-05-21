"""
Resolution Agent
Owner: Member 3

Executes approved resolutions received from the Policy Agent.

Resolution paths:
    1. "refund"       → call process_refund
    2. "label"        → call create_return_label
    3. "replacement"  → call create_replacement_order

IMPORTANT: Always check refund_cap guardrail before calling process_refund.
           Never process a refund > $500 without human_approval_required flag.

Dependencies:
    - tools/payment_tools.py   (process_refund)          — Member 3 (you)
    - tools/shipping_tools.py  (create_return_label,
                                create_replacement_order) — Member 3 (you)
    - guardrails/refund_cap.py                           — Member 2
"""

# from tools.payment_tools import process_refund
# from tools.shipping_tools import create_return_label, create_replacement_order

# TODO (Member 3): implement resolution_agent below
# resolution_agent = Agent(
#     name="ResolutionAgent",
#     instructions="...",
#     model="gpt-4o-mini",
#     tools=[process_refund, create_return_label, create_replacement_order],
# )
