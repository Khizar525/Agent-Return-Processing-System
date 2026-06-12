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
"""

import os
import re
from typing import Any
from agents import output_guardrail, GuardrailFunctionOutput

CAP = float(os.environ.get("REFUND_CAP_USD", "500.0"))
REFUND_CAP_USD = CAP


async def _refund_cap_impl(ctx: Any, agent: Any, output: Any) -> GuardrailFunctionOutput:
    """
    Inspect the Resolution Agent's output for refund amounts.
    If any amount exceeds REFUND_CAP_USD, trip the guardrail so the
    flow escalates to a human agent for approval.
    """
    amount = 0.0
    if output is not None:
        if isinstance(output, dict):
            try:
                amount = float(output.get("refund_amount", 0) or output.get("amount", 0))
            except (ValueError, TypeError):
                amount = 0.0
        elif hasattr(output, "refund_amount") and getattr(output, "refund_amount") is not None:
            try:
                amount = float(getattr(output, "refund_amount"))
            except (ValueError, TypeError):
                amount = 0.0
        elif hasattr(output, "amount") and getattr(output, "amount") is not None:
            try:
                amount = float(getattr(output, "amount"))
            except (ValueError, TypeError):
                amount = 0.0
        else:
            # Fallback to regex on string representation
            output_text = str(output)
            amounts = re.findall(r"\$?(\d+(?:\.\d{2})?)", output_text)
            for amount_str in amounts:
                try:
                    val = float(amount_str)
                    if val > amount:
                        amount = val
                except ValueError:
                    continue

    if amount > CAP:
        return GuardrailFunctionOutput(
            tripwire_triggered=True,
            output_info={
                "human_approval_required": True,
                "amount": amount,
                "reason": "exceeds_cap",
                "cap": CAP,
            },
        )

    # Prepare output info
    output_info = {"allowed": True}
    if isinstance(output, dict):
        output_info.update(output)
    elif hasattr(output, "model_dump"):
        output_info.update(output.model_dump())

    return GuardrailFunctionOutput(
        tripwire_triggered=False,
        output_info=output_info,
    )


RAW_REFUND_CAP = _refund_cap_impl
refund_cap_guardrail: Any = output_guardrail()(_refund_cap_impl)
