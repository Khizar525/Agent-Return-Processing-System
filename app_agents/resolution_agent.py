"""
Resolution Agent
Owner: Member 3

Executes approved resolutions via the Member 3 tool suite.

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
from pydantic import BaseModel, Field

from tools.payment_tools import process_refund
from tools.shipping_tools import create_return_label, create_replacement_order
from guardrails.refund_cap import refund_cap_guardrail


class ResolutionSummary(BaseModel):
    success: bool = Field(description="Whether the resolution action was successfully executed.")
    refund_amount: float | None = Field(default=None, description="The amount refunded in USD, if applicable.")
    currency: str | None = Field(default=None, description="The currency of the refund (e.g. 'USD'), if applicable.")
    human_approval_required: bool = Field(default=False, description="Whether human approval is required.")
    amount: float | None = Field(default=None, description="The attempted refund amount if human approval is required.")
    reason: str | None = Field(default=None, description="The reason for the status or failure (e.g. 'exceeds_cap' or error message).")
    label_url: str | None = Field(default=None, description="The return label URL, if applicable.")
    tracking_number: str | None = Field(default=None, description="The return label tracking number, if applicable.")
    carrier: str | None = Field(default=None, description="The shipping carrier used for the return label, if applicable.")
    replacement_order_id: str | None = Field(default=None, description="The replacement order ID, if applicable.")
    estimated_delivery: str | None = Field(default=None, description="Estimated delivery date/time for replacement order, if applicable.")
    error: str | None = Field(default=None, description="Error message, if execution failed.")


resolution_agent = Agent(
    name="ResolutionAgent",
    instructions=(
        "You are the Resolution Specialist Agent, an autonomous decision-making agent responsible for executing approved returns/refunds, replacements, or shipping labels.\n\n"
        "Your guidelines are:\n"
        "1. Select and execute the correct resolution path autonomously based on the customer request and policy instructions:\n"
        "   - Refund: call process_refund(order_id, amount_usd, method) to issue a refund. Ensure you only refund the specified amount.\n"
        "   - Return Label: call create_return_label(order_id, carrier) to generate a prepaid return label.\n"
        "   - Replacement: call create_replacement_order(order_id) to clone and expedite the order.\n"
        "2. Sequencing multiple actions: If a return policy requires a return label to be generated first, and then a refund processed, execute them sequentially by invoking the return label tool first, and then invoking the refund tool.\n"
        "3. Refund Cap Compliance: You MUST enforce the refund limit of $500. Under no circumstances should you call process_refund for an amount exceeding $500. If the refund amount is greater than $500, you must stop execution and autonomously report that human approval is required by returning human_approval_required=True, amount=<amount>, and reason='exceeds_cap'.\n"
        "4. Graceful Failure Handling: If a tool returns an error (success=False), do not crash. Catch it and return a human-readable failure reason in the 'error' and 'reason' fields of your structured output summary.\n"
        "5. Output Format: Always produce a structured output summary conforming to the ResolutionSummary schema."
    ),
    model="gpt-4o-mini",
    tools=[process_refund, create_return_label, create_replacement_order],
    output_guardrails=[refund_cap_guardrail],
    output_type=ResolutionSummary,
)
