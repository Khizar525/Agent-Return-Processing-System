"""
Resolution Agent
Owner: Member 3 (updated Phase 2 — Project Lead)

Executes approved resolutions received from the Policy Agent.

Resolution paths:
    1. "refund"       → call process_refund
    2. "label"        → call create_return_label
    3. "replacement"  → call create_replacement_order

IMPORTANT: Always check refund_cap guardrail before calling process_refund.
           Never process a refund > $500 without human_approval_required flag.

Dependencies:
    - tools/payment_tools.py   (process_refund)          — Member 3
    - tools/shipping_tools.py  (create_return_label,
                                create_replacement_order) — Member 3
    - guardrails/refund_cap.py (refund_cap_guardrail)    — Project Lead
"""

from agents import Agent

# ═══════════════════════════════════════════════════════════════════════════
# Ready-to-uncomment wiring
#
# When Member 3 merges feature/resolution-agent:
#   Uncomment lines A + B below to add resolution tools.
#
# When Member 2 merges refund_cap guardrail in guardrails/refund_cap.py:
#   Uncomment line C below to prevent auto-refunds over $500.
#
# After both PRs land, the agent definition looks like this:
#
#   from tools.payment_tools import process_refund
#   from tools.shipping_tools import create_return_label, create_replacement_order
#   from guardrails.refund_cap import refund_cap_guardrail
#
#   resolution_agent = Agent(
#       name="ResolutionAgent",
#       instructions="...",
#       model="gpt-4o-mini",
#       tools=[process_refund, create_return_label, create_replacement_order],   # ← A+B
#       output_guardrails=[refund_cap_guardrail],                                  # ← C
#   )
# ═══════════════════════════════════════════════════════════════════════════

# A+B: from tools.payment_tools import process_refund
# A+B: from tools.shipping_tools import create_return_label, create_replacement_order
# C:   from guardrails.refund_cap import refund_cap_guardrail

resolution_agent = Agent(
    name="ResolutionAgent",
    instructions=(
        "You are the Resolution Specialist.\n\n"
        "You receive policy decisions from the Policy Agent and execute them.\n\n"
        "Resolution paths:\n"
        '  - "refund"       → call process_refund(order_id, amount_usd, method)\n'
        '  - "label"        → call create_return_label(order_id, carrier)\n'
        '  - "replacement"  → call create_replacement_order(order_id)\n\n'
        "Rules:\n"
        "1. Never process a refund over $500 without human approval.\n"
        "2. Always confirm the refund amount with the customer before proceeding.\n"
        "3. Output a clear summary of what was executed.\n\n"
        "Never generate a label or process a refund without calling the appropriate tool."
    ),
    model="gpt-4o-mini",
    # tools=[process_refund, create_return_label, create_replacement_order],
    # output_guardrails=[refund_cap_guardrail],
)
