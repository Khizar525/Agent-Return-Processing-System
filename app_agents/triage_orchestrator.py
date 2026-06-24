"""
Triage Orchestrator — Agent 01 Entry Point
Owner: Project Lead

Classifies every inbound customer message by intent and routes it to the
correct specialist agent via handoff or tool call.

Intents:
    - return_request      → Handoff → PolicyAgent
    - order_status        → Tool call → tracking_lookup
    - billing_dispute     → Handoff → BillingAgent
    - general_inquiry     → Tool call → faq_lookup
    - edge_case_escalate  → Handoff → EscalationAgent
"""

from __future__ import annotations

from typing import Any, Literal

from agents import Agent, Runner
from pydantic import BaseModel

from guardrails.pii_scrubber import pii_scrubber_guardrail
from guardrails.sentiment_monitor import sentiment_monitor_guardrail

from app_agents.policy_agent import policy_agent
from app_agents.billing_agent import billing_agent
from app_agents.escalation_agent import escalation_agent
from tools.crm_tools import get_customer_profile
from tools.tracking_tools import RAW_TRACKING_LOOKUP as tracking_lookup, RAW_FAQ_LOOKUP as faq_lookup


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
# Triage Orchestrator definition
# ---------------------------------------------------------------------------

triage_agent = Agent(
    name="TriageOrchestrator",
    instructions="""
    You are the entry point for all customer support messages.

    IMPORTANT: Your final response MUST be a valid JSON object with these exact keys:
    {
      "intent": "<one of: return_request, order_status, billing_dispute, general_inquiry, edge_case_escalate>",
      "reasoning": "<brief explanation of why you chose this intent>",
      "customer_id": "<the customer_id from context>",
      "channel": "<the channel from context>",
      "suggested_action": "<what should happen next>"
    }

    Step 1 — Classify the customer message into exactly one intent:
        - return_request:     customer wants to return an item, get a refund, or reports
                              a broken/wrong/damaged item.
        - order_status:       customer asks where their order is, tracking, delivery ETA,
                              or wants to change/modify/cancel their order.
        - general_inquiry:    any other question (store hours, policies, how-to, FAQ,
                              asking about refund policy without wanting to return).
        - edge_case_escalate: message contains legal threats, extreme distress, or
                              repeat fraud signals.

    Step 2 — Set the suggested_action to describe what should happen:
        - order_status        → "Look up tracking for order <order_id>"
        - general_inquiry     → "Search FAQ for: <the customer's question>"
        - return_request      → "Evaluate return eligibility for order <order_id>"
        - billing_dispute     → "Transfer to BillingAgent"
        - edge_case_escalate  → "Transfer to EscalationAgent"

    Step 3 — Return the JSON object. Do NOT return free text. Always return JSON.
    The system will automatically execute the appropriate tool after classification.

    Always pass customer_id and channel in the JSON.
    Never attempt to process a refund or generate a label yourself.
    """,
    model="openai/gpt-oss-120b:free",
    output_type=TriageDecision,
    input_guardrails=[pii_scrubber_guardrail, sentiment_monitor_guardrail],
    handoffs=[policy_agent, billing_agent, escalation_agent],
    tools=[
        get_customer_profile,
        tracking_lookup,
        faq_lookup,
    ],
)


# ---------------------------------------------------------------------------
# Session-aware entry point
# ---------------------------------------------------------------------------


async def _classify_intent(message: str) -> str:
    """Keyword-based intent classification as fallback when LLM output is invalid."""
    lower = message.lower()
    if any(kw in lower for kw in ("sue", "lawyer", "attorney", "court", "legal", "litigation")):
        return "edge_case_escalate"
    if any(phrase in lower for phrase in ("return order", "return item", "send back", "damaged", "broken", "wrong item")):
        return "return_request"
    if any(kw in lower for kw in ("charged", "billing", "invoice", "transaction", "overcharged", "double charged")):
        return "billing_dispute"
    if any(kw in lower for kw in ("track", "where is", "delivery", "shipped", "status of order")):
        return "order_status"
    return "general_inquiry"


async def handle_customer_message(
    message: str,
    customer_id: str,
    channel: str = "web_chat",
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point called by the FastAPI webhook receiver.
    Loads existing session from Redis (if any), runs the triage agent,
    executes the appropriate tool based on intent, and persists session state.
    """

    # Load or initialise session
    session = await get_session(session_id) if session_id else {}
    session.setdefault("customer_id", customer_id)
    session.setdefault("channel", channel)
    session.setdefault("agent_chain", [])

    context = {
        "customer_id": customer_id,
        "channel": channel,
        "session": session,
    }

    # Run triage agent — try LLM classification, fall back to keywords
    intent = None
    reasoning = ""
    suggested_action = ""
    try:
        result = await Runner.run(triage_agent, input=message, context=context)
        decision: TriageDecision = result.final_output_as(TriageDecision)
        intent = decision.intent
        reasoning = decision.reasoning
        suggested_action = decision.suggested_action
    except Exception:
        # LLM produced invalid JSON — use keyword fallback
        intent = await _classify_intent(message)
        reasoning = f"Keyword-based classification (LLM output was invalid)"
        suggested_action = f"Route to {intent}"

    # Execute tool based on classified intent
    tool_results: dict[str, Any] = {}
    import re as _re

    order_match = _re.search(r"ORD[-_]?\d+", message, _re.IGNORECASE)
    order_id = order_match.group(0).upper() if order_match else None

    if intent == "order_status":
        oid = order_id or "ORD-001"
        tool_results["tracking_lookup"] = await tracking_lookup(oid)
        session["agent_chain"].append("tracking_lookup")

    elif intent == "general_inquiry":
        tool_results["faq_lookup"] = await faq_lookup(message)
        session["agent_chain"].append("faq_lookup")

    elif intent == "return_request":
        cid = customer_id or "CUST-001"
        oid = order_id or "ORD-001"
        from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return_policy
        tool_results["check_return_policy"] = await check_return_policy(oid, cid)
        session["agent_chain"].append("check_return_policy")

    # Update session
    session["agent_chain"].append("TriageOrchestrator")
    session["last_intent"] = intent
    session["last_output"] = {"intent": intent, "reasoning": reasoning}
    new_session_id = await save_session(session, existing_id=session_id)

    return {
        "session_id": new_session_id,
        "intent": intent,
        "reasoning": reasoning,
        "suggested_action": suggested_action,
        "tool_results": tool_results if tool_results else None,
        "resolution": {
            "intent": intent,
            "reasoning": reasoning,
            "customer_id": customer_id,
            "channel": channel,
            "suggested_action": suggested_action,
        },
        "agent_chain": session["agent_chain"],
    }
