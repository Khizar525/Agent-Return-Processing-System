"""
Refund Cap — Output Guardrail
Owner: Member 2

Prevents the Resolution Agent from autonomously processing any refund
above REFUND_CAP_USD (default $500, set in .env).

Behaviour:
    - If refund amount <= cap  → allow, pass through unchanged
    - If refund amount >  cap  → block, return { "human_approval_required": true,
                                                  "amount": float,
                                                  "reason": "exceeds_cap" }

Must be applied as an output_guardrail on the Resolution Agent.

Usage:
    from guardrails.refund_cap import refund_cap_guardrail
    resolution_agent = Agent(..., output_guardrails=[refund_cap_guardrail])
"""

import os
from typing import Any
from agents import output_guardrail, GuardrailFunctionOutput  # type: ignore[attr-defined]

CAP = float(os.environ.get("REFUND_CAP_USD", "500.0"))


@output_guardrail  # type: ignore[untyped-decorator]
async def refund_cap_guardrail(ctx: Any, agent: Any, output: Any) -> GuardrailFunctionOutput:
    amount = output.get("refund_amount", 0) if isinstance(output, dict) else 0
    if amount > CAP:
        return GuardrailFunctionOutput(
            tripwire_triggered=True,
            output_dict={
                "human_approval_required": True,
                "amount": amount,
                "reason": "exceeds_cap",
            },
        )
    return GuardrailFunctionOutput(
        tripwire_triggered=False,
        output_dict=output if isinstance(output, dict) else {},
    )
