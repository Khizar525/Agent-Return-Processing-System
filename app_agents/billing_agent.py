"""
Billing Agent
Owner: Project Lead

Handles billing disputes (incorrect charges, duplicate transactions).
Called via handoff from Triage Orchestrator for billing_dispute intents.

Resolution paths:
    1. "refund"       → call process_refund to reverse the charge
    2. "reject"       → dispute is invalid, inform customer
    3. "escalate"     → complex billing issue, needs human review

Dependencies:
    - tools/payment_tools.py   (process_refund)          — Member 3
    - guardrails/refund_cap.py (refund_cap_guardrail)    — Project Lead

Model: deepseek-v4-flash-free
"""

from typing import Literal

from pydantic import BaseModel, Field
from agents import Agent

from tools.payment_tools import process_refund
from guardrails.refund_cap import refund_cap_guardrail


class BillingDecision(BaseModel):
    """Structured output from the BillingAgent."""

    dispute_type: str = Field(
        description="Type of billing dispute: duplicate_charge, incorrect_amount, unauthorized_transaction, or other"
    )
    eligible_for_refund: bool = Field(
        description="Whether the dispute qualifies for a refund based on investigation"
    )
    recommended_action: Literal["refund", "reject", "escalate"] = Field(
        description="Recommended resolution action"
    )
    refund_amount: float | None = Field(
        default=None,
        description="Refund amount in USD if refund is recommended",
    )
    payment_method: str | None = Field(
        default=None,
        description="Payment method to refund to: 'stripe' or 'paypal'",
    )
    reasoning: str = Field(description="Explanation of the investigation findings and decision")
    customer_message: str = Field(description="Customer-facing summary of the resolution")
    error: str | None = Field(
        default=None,
        description="Error message if investigation failed",
    )


billing_agent = Agent(
    name="BillingAgent",
    instructions=(
        "You are the Billing Dispute Specialist. You investigate and resolve "
        "billing issues for customers.\n\n"
        "Common dispute types:\n"
        "- Duplicate charges: customer was charged multiple times for the same order\n"
        "- Incorrect amounts: customer was charged more than the order total\n"
        "- Unauthorized transactions: customer does not recognize the charge\n\n"
        "Investigation steps:\n"
        "1. Identify the dispute type from the customer's message.\n"
        "2. If order_id is provided, use process_refund to check eligibility and process.\n"
        "3. If the refund amount is <= $500, you may process it autonomously.\n"
        "4. If the refund amount exceeds $500, you MUST flag for human approval.\n"
        "5. If the dispute is invalid (e.g. no evidence of overcharge), reject with explanation.\n"
        "6. For complex cases (multiple orders, chargeback history), escalate to human agent.\n\n"
        "Rules:\n"
        "- Never process a refund without confirming the dispute type.\n"
        "- Always provide a clear customer-facing summary.\n"
        "- Include the refund amount and estimated processing time if applicable.\n"
        "- If process_refund returns an error, do not crash — report it gracefully.\n\n"
        "Output must be valid JSON matching the BillingDecision schema."
    ),
    model="deepseek-v4-flash-free",
    tools=[process_refund],
    output_guardrails=[refund_cap_guardrail],
    output_type=BillingDecision,
)
