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

import json
import os
from datetime import datetime, timezone

from agents import Agent, Runner, function_tool

from agents.billing_agent import billing_agent
from agents.escalation_agent import escalation_agent
from agents.policy_agent import policy_agent
from infra.redis_config import get_session, save_session

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

_FIXTURE_BASE = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")


async def tracking_lookup_impl(order_id: str) -> dict:
    """Implementation of tracking lookup — callable from tests directly."""
    try:
        path = os.path.join(_FIXTURE_BASE, "orders.json")
        with open(path) as f:
            orders: list[dict] = json.load(f)
    except Exception as exc:
        return {
            "success": False,
            "found": False,
            "status": "",
            "carrier": None,
            "tracking_number": None,
            "estimated_delivery": None,
            "error": f"Failed to load order data: {exc}",
        }

    order = next((o for o in orders if o["order_id"] == order_id), None)
    if not order:
        return {
            "success": False,
            "found": False,
            "status": "",
            "carrier": None,
            "tracking_number": None,
            "estimated_delivery": None,
            "error": f"Order {order_id} not found",
        }

    return {
        "success": True,
        "found": True,
        "status": order.get("status", "unknown"),
        "carrier": order.get("carrier"),
        "tracking_number": order.get("tracking_number"),
        "estimated_delivery": None,
        "error": None,
    }


@function_tool
async def tracking_lookup(order_id: str) -> dict:
    """Look up the shipping status and tracking info for a given order."""
    return await tracking_lookup_impl(order_id)


async def faq_lookup_impl(question: str) -> dict:
    """Implementation of FAQ lookup — callable from tests directly."""
    faq: dict[str, str] = {
        "return policy": "You have 30 days from the date of purchase to return most items. "
        "Items must be unworn, unwashed, and in original packaging. "
        "Digital goods, perishables, and final-sale items are excluded.",
        "return window": "The standard return window is 30 days from purchase.",
        "store hours": "Our online support is available 24/7. "
        "Physical store hours vary by location — please check our store locator.",
        "shipping": "Standard shipping takes 5–7 business days. "
        "Expedited shipping (2–3 business days) is available for an additional fee.",
        "refund": "Refunds are processed within 5–7 business days after we receive your return. "
        "The refund will be issued to your original payment method.",
    }

    q_lower = question.lower()
    for keyword, answer in faq.items():
        if keyword in q_lower:
            return {
                "success": True,
                "answer": answer,
                "matched_keyword": keyword,
                "error": None,
            }

    return {
        "success": False,
        "answer": "I'm sorry, I don't have information on that topic. "
        "Please contact our support team for further assistance.",
        "matched_keyword": None,
        "error": "No matching FAQ entry found",
    }


@function_tool
async def faq_lookup(question: str) -> dict:
    """Answer common customer questions about store policies."""
    return await faq_lookup_impl(question)


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
    model="gpt-4o",
    handoffs=[policy_agent, escalation_agent, billing_agent],
    tools=[tracking_lookup, faq_lookup],
)


# ---------------------------------------------------------------------------
# Session-aware entry point
# ---------------------------------------------------------------------------

async def handle_customer_message(
    message: str,
    customer_id: str,
    channel: str = "web_chat",
    session_id: str | None = None,
) -> dict:
    """
    Main entry point called by the FastAPI webhook receiver.
    Loads existing session from Redis (if any), runs the triage agent,
    and persists updated session state.
    """
    session = await get_session(session_id) if session_id else {}
    session.setdefault("customer_id", customer_id)
    session.setdefault("channel", channel)
    session.setdefault("agent_chain", [])
    session.setdefault("timestamps", {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
    })

    context = {
        "customer_id": customer_id,
        "channel": channel,
        "session": session,
    }

    result = await Runner.run(triage_agent, input=message, context=context)

    session["agent_chain"].append("TriageOrchestrator")
    session["last_output"] = result.final_output
    new_session_id = await save_session(session, existing_id=session_id)

    return {
        "session_id": new_session_id,
        "resolution": result.final_output,
        "agent_chain": session["agent_chain"],
    }
