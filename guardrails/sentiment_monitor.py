"""
Sentiment Monitor — Passive Input Guardrail
Owner: Member 2

Scores every inbound message for CSAT risk (0.0 – 1.0).
If score > SENTIMENT_ESCALATION_THRESHOLD (default 0.8, set in .env),
override the Triage Orchestrator routing and send directly to the
Escalation Agent.

Signals that raise the score:
    - Profanity or abusive language
    - Legal keywords ("lawyer", "sue", "court", "attorney")
    - Emotional distress indicators ("crying", "desperate", "ruined")
    - ALL CAPS messages
    - Multiple exclamation marks / question marks

Usage:
    from guardrails.sentiment_monitor import sentiment_monitor_guardrail
    triage_agent = Agent(..., input_guardrails=[sentiment_monitor_guardrail])
"""

import os
import re
from typing import Any
from agents import input_guardrail, GuardrailFunctionOutput  # type: ignore[attr-defined]

THRESHOLD = float(os.environ.get("SENTIMENT_ESCALATION_THRESHOLD", "0.8"))

LEGAL_KEYWORDS = {"lawyer", "sue", "court", "attorney", "legal", "litigation"}
DISTRESS_KEYWORDS = {"crying", "desperate", "ruined", "outrageous", "unacceptable", "furious"}
PROFANITY_PATTERN = re.compile(r"\b(fuck|shit|crap|damn|bastard|asshole)\b", re.IGNORECASE)
EXCLAMATION_PATTERN = re.compile(r"[!?]{2,}")


@input_guardrail  # type: ignore[untyped-decorator]
async def sentiment_monitor_guardrail(ctx: Any, agent: Any, message: str) -> GuardrailFunctionOutput:
    score = 0.0
    lower = message.lower()

    if message.isupper() and len(message) > 10:
        score += 0.3

    if any(kw in lower for kw in LEGAL_KEYWORDS):
        score += 0.3

    if any(kw in lower for kw in DISTRESS_KEYWORDS):
        score += 0.2

    if PROFANITY_PATTERN.search(lower):
        score += 0.2

    exclamation_matches = EXCLAMATION_PATTERN.findall(message)
    if exclamation_matches:
        score += min(0.2, len(exclamation_matches) * 0.1)

    score = min(score, 1.0)
    escalate = score > THRESHOLD

    return GuardrailFunctionOutput(
        tripwire_triggered=escalate,
        output_dict={"score": score, "escalate": escalate},
    )
