"""
PII Scrubber — Input Guardrail
Owner: Member 2

Strips all Personally Identifiable Information from the raw customer
message BEFORE it is passed to any agent.

Patterns to scrub (replace with [REDACTED]):
    - Credit card numbers (Visa, MC, Amex, Discover — 13–16 digits)
    - Social Security Numbers (XXX-XX-XXXX or XXXXXXXXX)
    - Bank account numbers
    - Passwords or tokens embedded in messages

Must be applied as an input_guardrail on the Triage Orchestrator.

Usage:
    from guardrails.pii_scrubber import pii_scrubber_guardrail
    triage_agent = Agent(..., input_guardrails=[pii_scrubber_guardrail])
"""

import re
from typing import Any
from agents import input_guardrail, GuardrailFunctionOutput

CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
BANK_PATTERN = re.compile(r"\b\d{8,17}\b")


async def _pii_scrubber_impl(ctx: Any, agent: Any, message: Any) -> GuardrailFunctionOutput:
    if not isinstance(message, str):
        return GuardrailFunctionOutput(
            tripwire_triggered=False,
            output_info={"scrubbed_message": message},
        )
    scrubbed = message
    scrubbed = CC_PATTERN.sub("[REDACTED]", scrubbed)
    scrubbed = SSN_PATTERN.sub("[REDACTED]", scrubbed)
    scrubbed = BANK_PATTERN.sub("[REDACTED]", scrubbed)
    triggered = scrubbed != message
    return GuardrailFunctionOutput(
        tripwire_triggered=triggered,
        output_info={"scrubbed_message": scrubbed},
    )


RAW_PII_SCRUBBER = _pii_scrubber_impl
pii_scrubber_guardrail: Any = input_guardrail()(_pii_scrubber_impl)
