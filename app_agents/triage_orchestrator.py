"""
Triage Orchestrator — Agent Nemo Entry Point
Owner: Project Lead

Classifies every inbound customer message by intent and routes it to the
correct specialist agent via handoff or tool call.

Architecture:
    LLM classification → deterministic tool dispatch → structured response

The LLM is used ONLY for intent classification (its strength).
Tools are executed deterministically in code (code's strength).
This avoids the SDK limitation where tool call results are consumed
internally by the Runner and never exposed to the caller.

Intents:
    - return_request      → Tool: check_return_policy → Handoff: PolicyAgent
    - order_status        → Tool: tracking_lookup
    - billing_dispute     → Handoff: BillingAgent
    - general_inquiry     → Tool: faq_lookup
    - edge_case_escalate  → Handoff: EscalationAgent
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Literal

from agents import Agent, Runner
from pydantic import BaseModel

from guardrails.pii_scrubber import pii_scrubber_guardrail
from guardrails.sentiment_monitor import sentiment_monitor_guardrail

from app_agents.policy_agent import policy_agent
from app_agents.billing_agent import billing_agent
from app_agents.escalation_agent import escalation_agent
from tools.crm_tools import get_customer_profile
from tools.tracking_tools import RAW_TRACKING_LOOKUP as _raw_tracking_lookup
from tools.tracking_tools import RAW_FAQ_LOOKUP as _raw_faq_lookup
from tools.policy_tools import RAW_CHECK_RETURN_POLICY as _raw_check_return_policy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output schema — enforces structured intent classification
# ---------------------------------------------------------------------------


class TriageDecision(BaseModel):
    """Structured output from the TriageOrchestrator agent."""

    intent: Literal[
        "return_request",
        "order_status",
        "billing_dispute",
        "general_inquiry",
        "edge_case_escalate",
    ]
    reasoning: str
    customer_id: str
    channel: str
    suggested_action: str


# ---------------------------------------------------------------------------
# Tool dispatch table — deterministic routing based on classified intent
# ---------------------------------------------------------------------------

ORDER_PATTERN = re.compile(r"ORD[-_]?\d+", re.IGNORECASE)
CUSTOMER_PATTERN = re.compile(r"CUST[-_]?\d+", re.IGNORECASE)


def _extract_order_id(message: str) -> str | None:
    """Extract order ID from the customer message."""
    m = ORDER_PATTERN.search(message)
    return m.group(0).upper() if m else None


def _extract_customer_id(message: str, fallback: str) -> str:
    """Extract customer ID from message, or use the provided fallback."""
    m = CUSTOMER_PATTERN.search(message)
    return m.group(0).upper() if m else fallback


async def _dispatch_tool(
    intent: str,
    message: str,
    customer_id: str,
) -> tuple[str, dict[str, Any]]:
    """
    Execute the appropriate tool for the given intent.
    Returns (tool_name, tool_result).
    """
    if intent == "order_status":
        order_id = _extract_order_id(message) or "ORD-001"
        result = await _raw_tracking_lookup(order_id)
        return "tracking_lookup", result

    elif intent == "general_inquiry":
        result = await _raw_faq_lookup(message)
        return "faq_lookup", result

    elif intent == "return_request":
        order_id = _extract_order_id(message) or "ORD-001"
        cid = _extract_customer_id(message, customer_id)
        result = await _raw_check_return_policy(order_id, cid)
        return "check_return_policy", result

    # billing_dispute and edge_case_escalate are handoffs — no tool to execute
    return "", {}


# ---------------------------------------------------------------------------
# Keyword-based classification — fast fallback, zero latency
# ---------------------------------------------------------------------------

_KEYWORD_RULES: list[tuple[str, list[str]]] = [
    ("edge_case_escalate", ["sue", "lawyer", "attorney", "court", "legal action", "litigation"]),
    (
        "return_request",
        [
            "return order",
            "return item",
            "send back",
            "damaged",
            "broken",
            "wrong item",
            "replace my",
        ],
    ),
    (
        "billing_dispute",
        ["charged", "billing", "invoice", "transaction", "overcharged", "double charged"],
    ),
    ("order_status", ["track", "where is", "delivery", "shipped", "tracking", "order status"]),
]

# Frustration / complaint signals — route to escalation, not FAQ
_FRUSTRATION_KEYWORDS = [
    "terrible",
    "stupid",
    "awful",
    "horrible",
    "worst",
    "unacceptable",
    "fix this",
    "fix it",
    "right now",
    "immediately",
    "ridiculous",
    "never again",
    "waste of time",
    "absolutely not",
    "furious",
    "outraged",
    "disgusted",
    "pathetic",
    "incompetent",
    "useless",
]


def _classify_intent_keywords(message: str) -> str:
    """
    Rule-based intent classification. Deterministic, fast, zero-cost.
    Used as primary classifier — LLM classification is optional enrichment.
    """
    lower = message.lower()

    # Check for frustration/complaint FIRST — these override other intents
    if any(kw in lower for kw in _FRUSTRATION_KEYWORDS):
        return "edge_case_escalate"

    for intent, keywords in _KEYWORD_RULES:
        if any(kw in lower for kw in keywords):
            return intent
    return "general_inquiry"


# ---------------------------------------------------------------------------
# Triage Orchestrator definition — classification only, no tools
# ---------------------------------------------------------------------------

triage_agent = Agent(
    name="TriageOrchestrator",
    instructions="""
    You are a message classifier for a customer support system.

    Your ONLY job is to classify the customer message into one intent.
    Do NOT call any tools. Do NOT attempt to resolve the issue.
    Just classify and return JSON.

    Return exactly this JSON:
    {
      "intent": "<one of: return_request, order_status, billing_dispute, general_inquiry, edge_case_escalate>",
      "reasoning": "<one sentence explaining why>",
      "customer_id": "<from context>",
      "channel": "<from context>",
      "suggested_action": "<one sentence describing next step>"
    }

    Intent definitions:
        - return_request:     wants to return, refund, replace, or reports damaged/broken item
        - order_status:       asks about tracking, delivery, shipping status, or wants to change/cancel
        - billing_dispute:    billing error, incorrect charge, transaction dispute
        - general_inquiry:    any other question (policies, how-to, store info)
        - edge_case_escalate: legal threats, extreme distress, litigation language

    Always return valid JSON. Never return free text.
    """,
    model="openai/gpt-oss-120b:free",
    output_type=TriageDecision,
    input_guardrails=[pii_scrubber_guardrail, sentiment_monitor_guardrail],
    handoffs=[policy_agent, billing_agent, escalation_agent],
    tools=[get_customer_profile],
)


# ---------------------------------------------------------------------------
# Guardrail detection — detects and reports guardrail activations
# ---------------------------------------------------------------------------

_CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
_SENTIMENT_THRESHOLD = float(os.environ.get("SENTIMENT_ESCALATION_THRESHOLD", "0.8"))
_SENTIMENT_LEGAL = {"sue", "lawyer", "attorney", "court", "legal", "litigation"}
_SENTIMENT_DISTRESS = {"crying", "desperate", "ruined", "outrageous", "unacceptable", "furious"}
_SENTIMENT_PROFANITY = re.compile(
    r"\b(f[\W_]*u[\W_]*c[\W_]*k|s[\W_]*h[\W_]*i[\W_]*t|crap|damn|bastard|asshole)\b",
    re.IGNORECASE,
)
_SENTIMENT_EXCLAMATION = re.compile(r"[!?]{2,}")


def _detect_guardrails(message: str) -> list[dict[str, Any]]:
    """
    Detect which guardrails would activate for the given message.
    Returns a list of guardrail activation dicts.
    """
    activations: list[dict[str, Any]] = []

    # ── PII Scrubber ─────────────────────────────────────────────
    has_cc = bool(_CC_PATTERN.search(message))
    has_ssn = bool(_SSN_PATTERN.search(message))
    if has_cc or has_ssn:
        pii_types = []
        if has_cc:
            pii_types.append("credit_card")
        if has_ssn:
            pii_types.append("ssn")
        activations.append(
            {
                "name": "PII Scrubber",
                "type": "input",
                "action": "scrubbed",
                "detail": f"Detected {', '.join(pii_types)} — replaced with [REDACTED]",
                "icon": "🛡️",
            }
        )

    # ── Sentiment Monitor ────────────────────────────────────────
    score = 0.0
    lower = message.lower()
    signals = []

    if message.isupper() and len(message) > 10:
        score += 0.3
        signals.append("ALL CAPS (+0.3)")

    if any(kw in lower for kw in _SENTIMENT_LEGAL):
        score += 0.4
        signals.append("legal keywords (+0.4)")

    if any(kw in lower for kw in _SENTIMENT_DISTRESS):
        score += 0.2
        signals.append("distress keywords (+0.2)")

    if _SENTIMENT_PROFANITY.search(lower):
        score += 0.2
        signals.append("profanity (+0.2)")

    excl = _SENTIMENT_EXCLAMATION.findall(message)
    if excl:
        bonus = min(0.2, len(excl) * 0.1)
        score += bonus
        signals.append(f"exclamations (+{bonus})")

    score = min(round(score, 10), 1.0)
    if score >= _SENTIMENT_THRESHOLD:
        activations.append(
            {
                "name": "Sentiment Monitor",
                "type": "input",
                "action": "escalated",
                "detail": f"Score {score:.1f} >= {_SENTIMENT_THRESHOLD} — routing override to EscalationAgent",
                "signals": signals,
                "icon": "⚠️",
            }
        )

    # ── Refund Cap (check if message requests a large refund) ────
    refund_match = re.search(r"\$\s*(\d+(?:\.\d{2})?)", message)
    if refund_match:
        amount = float(refund_match.group(1))
        if amount > 500:
            activations.append(
                {
                    "name": "Refund Cap",
                    "type": "output",
                    "action": "blocked",
                    "detail": f"Refund ${amount:.2f} exceeds $500 cap — requires human approval",
                    "icon": "🚫",
                }
            )

    # ── Brand Voice (check for prohibited language in message) ───
    prohibited = [
        "stupid",
        "hate",
        "useless",
        "idiot",
        "scam",
        "damn",
        "it was our fault",
        "we are liable",
        "we guarantee",
        "you will definitely",
        "terrible",
        "worthless",
        "fix this now",
    ]
    found_prohibited = [word for word in prohibited if word in lower]
    if found_prohibited:
        activations.append(
            {
                "name": "Brand Voice",
                "type": "output",
                "action": "rewriting",
                "detail": f"Prohibited language detected: {', '.join(found_prohibited)} — rewriting",
                "icon": "✍️",
            }
        )

    return activations


# ---------------------------------------------------------------------------
# Natural language response generation — turns tool results into chatbot replies
# ---------------------------------------------------------------------------


def _generate_response(
    intent: str,
    message: str,
    tool_name: str,
    tool_result: dict[str, Any],
) -> str:
    """
    Convert tool results into a natural language chatbot response.
    This is what the customer sees — friendly, helpful, and concise.
    """

    # ── Return request ────────────────────────────────────────────
    if intent == "return_request" and tool_name == "check_return_policy":
        eligible = tool_result.get("eligible", False)
        if eligible:
            days_left = (tool_result.get("return_window_days") or 30) - (
                tool_result.get("days_since_purchase") or 0
            )
            action = tool_result.get("recommended_action", "process your return")
            response = (
                f"Good news! Your order is eligible for a return. "
                f"You have {days_left} days left in the return window. "
            )
            if action == "refund":
                response += "I can process a full refund for you. "
            elif action == "replacement":
                response += "I can send you a replacement right away. "
            response += "Would you like me to proceed, or do you have any other questions?"
            return response
        else:
            reason = tool_result.get("reason", "policy requirements")
            return (
                f"I've checked the return policy for your order, but unfortunately "
                f"it's not eligible for a return at this time. "
                f"Reason: {reason}. "
                f"If you believe this is an error, I can connect you with a specialist "
                f"who can review your case."
            )

    # ── Order tracking ────────────────────────────────────────────
    if intent == "order_status" and tool_name == "tracking_lookup":
        if tool_result.get("found"):
            status = tool_result.get("status", "unknown")
            carrier = tool_result.get("carrier", "our carrier").upper()
            tracking = tool_result.get("tracking_number", "")
            eta = tool_result.get("estimated_delivery", "")
            order_id = _extract_order_id(message) or "your order"

            response = f"Here's the latest on {order_id}: "
            status_map = {
                "in_transit": "It's on its way!",
                "delivered": "It has been delivered!",
                "processing": "It's being processed and will ship soon.",
                "shipped": "It has been shipped!",
                "pending": "It's being prepared for shipment.",
            }
            response += status_map.get(status, f"Current status: {status.replace('_', ' ')}.")
            response += f" Carrier: {carrier}"
            if tracking:
                response += f" (Tracking: {tracking})"
            if eta:
                from datetime import datetime

                try:
                    dt = datetime.fromisoformat(eta.replace("Z", "+00:00"))
                    response += f". Estimated delivery: {dt.strftime('%B %d')}"
                except (ValueError, AttributeError):
                    response += f". Estimated delivery: {eta}"
            response += ". Need anything else?"
            return response
        else:
            return (
                "I couldn't find tracking information for that order. "
                "Could you double-check the order number? It should look like ORD-XXXX."
            )

    # ── FAQ lookup ────────────────────────────────────────────────
    if intent == "general_inquiry" and tool_name == "faq_lookup":
        if tool_result.get("success"):
            answer = tool_result.get("answer", "")
            if answer:
                return f"{answer}\n\nIs there anything else I can help with?"
        # No FAQ match — give a helpful generic response
        return (
            "That's a great question! I don't have a specific answer in my knowledge base, "
            "but I'd be happy to help. Could you tell me a bit more about what you're looking for? "
            "I can also connect you with a human specialist if needed."
        )

    # ── Billing dispute (handoff) ─────────────────────────────────
    if intent == "billing_dispute":
        return (
            "I understand you have a billing concern, and I want to make sure this gets "
            "resolved quickly. I'm connecting you with our billing specialist who can "
            "review your account and charges in detail. They'll be with you shortly."
        )

    # ── Escalation (legal / extreme distress) ─────────────────────
    if intent == "edge_case_escalate":
        # Detect specific signals to personalize the response
        lower = message.lower()
        has_legal = any(
            kw in lower for kw in ["sue", "lawyer", "attorney", "court", "legal", "litigation"]
        )
        has_frustration = any(
            kw in lower
            for kw in [
                "terrible",
                "stupid",
                "awful",
                "horrible",
                "worst",
                "unacceptable",
                "fix this",
                "fix it",
                "right now",
                "ridiculous",
                "furious",
                "outraged",
            ]
        )

        if has_legal:
            return (
                "I take your concerns very seriously. I'm immediately escalating this "
                "to a senior specialist who can address the legal aspects of your inquiry. "
                "They will review your case with priority and reach out to you directly."
            )
        elif has_frustration:
            return (
                "I hear you, and I'm sorry you've had this experience. You deserve better. "
                "I'm connecting you right now with a senior agent who can take immediate action "
                "on your behalf. They'll have the full context and authority to resolve this."
            )
        else:
            return (
                "I understand this is a serious situation and I want to make sure you get "
                "the help you need. I'm immediately connecting you with a senior specialist "
                "who can give this the attention it deserves. Please hold for just a moment."
            )

    # ── Fallback ──────────────────────────────────────────────────
    return (
        "Thank you for reaching out! I'm here to help with returns, order tracking, "
        "billing questions, and more. Could you tell me a bit more about what you need?"
    )


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

try:
    from infra.redis_config import get_session as _redis_get, save_session as _redis_save

    _redis_available = True
except Exception:
    _redis_available = False


async def get_session(session_id: str) -> dict[str, Any]:
    if _redis_available:
        try:
            return await _redis_get(session_id)
        except Exception:
            pass
    return {}


async def save_session(session: dict[str, Any], existing_id: str | None = None) -> str:
    if _redis_available:
        try:
            return await _redis_save(session, existing_id)
        except Exception:
            pass
    import uuid as _uuid

    return existing_id or str(_uuid.uuid4())


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def handle_customer_message(
    message: str,
    customer_id: str,
    channel: str = "web_chat",
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point called by the FastAPI webhook receiver.

    Flow:
        1. Load session from Redis
        2. Classify intent (keyword-first, LLM enrichment)
        3. Execute tool deterministically based on intent
        4. Persist session and return structured response
    """

    # ── 1. Load session ──────────────────────────────────────────
    session = await get_session(session_id) if session_id else {}
    session.setdefault("customer_id", customer_id)
    session.setdefault("channel", channel)
    session.setdefault("agent_chain", [])

    context = {
        "customer_id": customer_id,
        "channel": channel,
        "session": session,
    }

    # ── 2. Detect guardrail activations ──────────────────────────
    guardrails = _detect_guardrails(message)

    # ── 3. Classify intent ───────────────────────────────────────
    # Keyword classification is primary — fast, deterministic, free.
    # LLM classification is optional enrichment for reasoning quality.
    keyword_intent = _classify_intent_keywords(message)
    intent = keyword_intent
    reasoning = "Classified by keyword rules"
    suggested_action = f"Route to {intent}"
    llm_ok = False

    try:
        result = await Runner.run(triage_agent, input=message, context=context)
        decision: TriageDecision = result.final_output_as(TriageDecision)
        llm_intent = decision.intent
        # LLM can refine intent, BUT keyword classification wins for
        # escalation signals (frustration, legal threats, anger)
        # because the LLM often misclassifies angry messages as general_inquiry
        if keyword_intent == "edge_case_escalate":
            intent = keyword_intent  # Keep escalation — don't let LLM downgrade it
            reasoning = f"Keyword escalation override (LLM suggested: {llm_intent})"
        else:
            intent = llm_intent
            reasoning = decision.reasoning
            suggested_action = decision.suggested_action
        llm_ok = True
        logger.info("LLM classification: intent=%s", intent)
    except Exception as exc:
        logger.warning(
            "LLM classification failed (%s), using keyword fallback: %s", type(exc).__name__, intent
        )

    # ── 3. Execute tool ──────────────────────────────────────────
    tool_name, tool_result = await _dispatch_tool(intent, message, customer_id)

    if tool_name:
        session["agent_chain"].append(tool_name)
        logger.info("Tool executed: %s success=%s", tool_name, tool_result.get("success", "?"))

    # ── 4. Update session ────────────────────────────────────────
    session["agent_chain"].append("TriageOrchestrator")
    session["last_intent"] = intent
    session["last_output"] = {
        "intent": intent,
        "reasoning": reasoning,
        "tool": tool_name,
        "tool_success": tool_result.get("success") if tool_result else None,
    }
    new_session_id = await save_session(session, existing_id=session_id)

    # ── 5. Build response ────────────────────────────────────────
    tool_results = {tool_name: tool_result} if tool_name else None

    # Generate natural language response for the customer
    chat_response = _generate_response(intent, message, tool_name, tool_result)

    return {
        "session_id": new_session_id,
        "response": chat_response,
        "intent": intent,
        "reasoning": reasoning,
        "suggested_action": suggested_action,
        "guardrails": guardrails,
        "tool_results": tool_results,
        "resolution": {
            "intent": intent,
            "reasoning": reasoning,
            "customer_id": customer_id,
            "channel": channel,
            "suggested_action": suggested_action,
            "llm_classified": llm_ok,
        },
        "agent_chain": session["agent_chain"],
    }
