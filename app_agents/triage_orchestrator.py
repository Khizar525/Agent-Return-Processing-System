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

# from app_agents.policy_agent import policy_agent           # uncomment after M2 merges
# from app_agents.escalation_agent import escalation_agent   # uncomment after M4 merges
# from tools.crm_tools import get_customer_profile       # uncomment after M3 merges


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

    Step 1 — Classify the customer message into exactly one intent:
        - return_request:     customer wants to return an item, get a refund, or reports
                              a broken/wrong/damaged item.
        - order_status:       customer asks where their order is, tracking, delivery ETA.
        - billing_dispute:    customer was charged incorrectly or disputes a transaction.
        - general_inquiry:    any other question (store hours, policies, how-to).
        - edge_case_escalate: message contains legal threats, extreme distress, or
                              repeat fraud signals.

    Step 2 — Route:
        - return_request      → handoff to PolicyAgent
        - edge_case_escalate  → handoff to EscalationAgent
        - order_status        → call tracking_lookup tool
        - billing_dispute     → handoff to BillingAgent
        - general_inquiry     → call faq_lookup tool

    Always pass customer_id and session_id in every handoff context.
    Never attempt to process a refund or generate a label yourself.
    """,
    model="deepseek-v4-flash-free",
    output_type=TriageDecision,
    # handoffs=[policy_agent, escalation_agent],   # re-enable after teammates merge
    tools=[
        # policy_agent.as_tool(
        #     tool_name="validate_return",
        #     tool_description="Validate return eligibility for a customer order",
        # ),
        # get_customer_profile,
    ],
)


# ---------------------------------------------------------------------------
# Session-aware entry point
# ---------------------------------------------------------------------------

async def handle_customer_message(
    message: str,
    customer_id: str,
    channel: str = "web_chat",
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point called by the FastAPI webhook receiver.
    Loads existing session from Redis (if any), runs the triage agent,
    and persists updated session state.
    """
    import uuid

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

    # Run triage agent — output is a typed TriageDecision
    result = await Runner.run(triage_agent, input=message, context=context)
    decision: TriageDecision = result.final_output_as(TriageDecision)

    # Update session
    session["agent_chain"].append("TriageOrchestrator")
    session["last_intent"] = decision.intent
    session["last_output"] = decision.model_dump()
    new_session_id = await save_session(session, existing_id=session_id)

    return {
        "session_id": new_session_id,
        "intent": decision.intent,
        "reasoning": decision.reasoning,
        "suggested_action": decision.suggested_action,
        "resolution": decision.model_dump(),
        "agent_chain": session["agent_chain"],
    }
