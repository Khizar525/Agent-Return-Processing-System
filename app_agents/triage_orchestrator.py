"""
Triage Orchestrator — Agent 01 Entry Point
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
    ("return_request", ["return order", "return item", "send back", "damaged", "broken", "wrong item", "replace my"]),
    ("billing_dispute", ["charged", "billing", "invoice", "transaction", "overcharged", "double charged"]),
    ("order_status", ["track", "where is", "delivery", "shipped", "tracking", "order status"]),
]


def _classify_intent_keywords(message: str) -> str:
    """
    Rule-based intent classification. Deterministic, fast, zero-cost.
    Used as primary classifier — LLM classification is optional enrichment.
    """
    lower = message.lower()
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

    # ── 2. Classify intent ───────────────────────────────────────
    # Keyword classification is primary — fast, deterministic, free.
    # LLM classification is optional enrichment for reasoning quality.
    intent = _classify_intent_keywords(message)
    reasoning = "Classified by keyword rules"
    suggested_action = f"Route to {intent}"
    llm_ok = False

    try:
        result = await Runner.run(triage_agent, input=message, context=context)
        decision: TriageDecision = result.final_output_as(TriageDecision)
        intent = decision.intent
        reasoning = decision.reasoning
        suggested_action = decision.suggested_action
        llm_ok = True
        logger.info("LLM classification: intent=%s", intent)
    except Exception as exc:
        logger.warning("LLM classification failed (%s), using keyword fallback: %s", type(exc).__name__, intent)

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

    return {
        "session_id": new_session_id,
        "intent": intent,
        "reasoning": reasoning,
        "suggested_action": suggested_action,
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
