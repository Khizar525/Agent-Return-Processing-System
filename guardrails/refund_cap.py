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
from agents import output_guardrail, GuardrailFunctionOutput

CAP = float(os.environ.get("REFUND_CAP_USD", "500.0"))


async def _refund_cap_impl(ctx: Any, agent: Any, output: Any) -> GuardrailFunctionOutput:
    try:
        amount = float(output.get("refund_amount", 0)) if isinstance(output, dict) else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    if amount > CAP:
        return GuardrailFunctionOutput(
            tripwire_triggered=True,
            output_info={
                "human_approval_required": True,
                "amount": amount,
                "reason": "exceeds_cap",
            },
        )
    return GuardrailFunctionOutput(
        tripwire_triggered=False,
        output_info=output if isinstance(output, dict) else {},
    )


RAW_REFUND_CAP = _refund_cap_impl
refund_cap_guardrail: Any = output_guardrail()(_refund_cap_impl)
