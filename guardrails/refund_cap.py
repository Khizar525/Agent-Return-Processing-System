"""
Refund Cap — Output Guardrail
Owner: Project Lead (wired for Phase 2)

Prevents the Resolution Agent from autonomously processing any refund
above REFUND_CAP_USD (default $500, set in .env).

Behaviour:
    - If refund amount <= cap  → allow, pass through unchanged
    - If refund amount >  cap  → block, trip guardrail with
      { "human_approval_required": true, "amount": float, "reason": "exceeds_cap" }

Must be applied as an output_guardrail on the Resolution Agent.

Usage:
    from guardrails.refund_cap import refund_cap_guardrail
    resolution_agent = Agent(..., output_guardrails=[refund_cap_guardrail])
"""

import os
import re

from agents import GuardrailFunctionOutput, output_guardrail

REFUND_CAP_USD = float(os.environ.get("REFUND_CAP_USD", "500"))


@output_guardrail
async def refund_cap_guardrail(ctx, agent, output) -> GuardrailFunctionOutput:
    """
    Inspect the Resolution Agent's output for refund amounts.
    If any amount exceeds REFUND_CAP_USD, trip the guardrail so the
    flow escalates to a human agent for approval.
    """
    output_text = str(output)
    amounts = re.findall(r"\$?(\d+(?:\.\d{2})?)", output_text)

    for amount_str in amounts:
        try:
            amount = float(amount_str)
            if amount > REFUND_CAP_USD:
                return GuardrailFunctionOutput(
                    output_info={
                        "human_approval_required": True,
                        "amount": amount,
                        "reason": "exceeds_cap",
                        "cap": REFUND_CAP_USD,
                    },
                    tripwire_triggered=True,
                )
        except ValueError:
            continue

    return GuardrailFunctionOutput(
        output_info={"allowed": True},
        tripwire_triggered=False,
    )
