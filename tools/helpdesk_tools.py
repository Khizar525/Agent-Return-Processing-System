"""
Helpdesk Tools
Owner: Member 4 (implemented), Lead (post-merge cleanup)

Creates human-agent tickets in Zendesk and logs resolution outcomes.

Interface Spec (do not change signatures without Lead approval):

    create_human_ticket(context_bundle: dict) -> dict
        Args:
            context_bundle: {
                "customer_id": str,
                "session_id": str,
                "agent_chain": list[str],
                "intent": str,
                "policy_decision": dict | None,
                "resolution_action": str | None,
                "escalation_reason": str,
                "order_history": list[dict],
                "timestamps": dict,
                "raw_conversation": list[dict],
            }
        Returns:
            {
                "success": bool,
                "ticket_id": str,
                "ticket_url": str,
                "priority": str,   # "low" | "normal" | "high" | "urgent"
                "error": str | None,
            }

    log_resolution(session_id: str, outcome: dict) -> dict
        Args:
            session_id: active session identifier
            outcome:    resolution summary for the data warehouse
        Returns:
            { "success": bool, "record_id": str, "error": str | None }

Environment variables required:
    ZENDESK_SUBDOMAIN, ZENDESK_API_TOKEN, ZENDESK_EMAIL
"""

from __future__ import annotations

import json
import os
import uuid
import datetime
from typing import Any

import httpx
from agents import function_tool

_HTTP_TIMEOUT = 15.0


@function_tool(strict_mode=False, name_override="create_human_ticket")
async def _create_human_ticket_tool(
    context_bundle: dict,
) -> dict:
    """Open a Zendesk ticket with full conversation context."""
    ticket_id = None
    ticket_url = None
    priority = "normal"
    error = None
    success = False

    try:
        zendesk_subdomain = os.environ.get("ZENDESK_SUBDOMAIN")
        zendesk_email = os.environ.get("ZENDESK_EMAIL")
        zendesk_api_token = os.environ.get("ZENDESK_API_TOKEN")

        if not zendesk_subdomain:
            return {
                "success": False,
                "ticket_id": None,
                "ticket_url": None,
                "priority": "normal",
                "error": "ZENDESK_SUBDOMAIN not set",
            }
        if not zendesk_email:
            return {
                "success": False,
                "ticket_id": None,
                "ticket_url": None,
                "priority": "normal",
                "error": "ZENDESK_EMAIL not set",
            }
        if not zendesk_api_token:
            return {
                "success": False,
                "ticket_id": None,
                "ticket_url": None,
                "priority": "normal",
                "error": "ZENDESK_API_TOKEN not set",
            }

        url = f"https://{zendesk_subdomain}.zendesk.com/api/v2/tickets.json"
        auth = (f"{zendesk_email}/token", zendesk_api_token)

        customer_id = context_bundle.get("customer_id", "unknown")
        session_id = context_bundle.get("session_id", "unknown")
        agent_chain = context_bundle.get("agent_chain", [])
        intent = context_bundle.get("intent", "unknown")
        policy_decision = context_bundle.get("policy_decision")
        resolution_action = context_bundle.get("resolution_action")
        escalation_reason = context_bundle.get("escalation_reason", "unknown")
        order_history = context_bundle.get("order_history", [])
        timestamps = context_bundle.get("timestamps", {})
        raw_conversation = context_bundle.get("raw_conversation", [])

        if escalation_reason in ("legal_threats", "high_value_order"):
            priority = "high"
        elif escalation_reason == "repeat_fraud":
            priority = "urgent"

        ticket_payload = {
            "ticket": {
                "subject": f"Customer Support Escalation: {intent}",
                "comment": {
                    "body": (
                        f"Customer ID: {customer_id}\n"
                        f"Session ID: {session_id}\n"
                        f"Intent: {intent}\n"
                        f"Escalation Reason: {escalation_reason}\n"
                        f"Agent Chain: {', '.join(agent_chain) if agent_chain else 'None'}\n"
                        f"Policy Decision: {json.dumps(policy_decision) if policy_decision else 'None'}\n"
                        f"Resolution Action: {resolution_action or 'None'}\n"
                        f"Order History: {json.dumps(order_history, indent=2) if order_history else 'None'}\n"
                        f"Timestamps: {json.dumps(timestamps, indent=2) if timestamps else 'None'}\n"
                        f"Raw Conversation: {json.dumps(raw_conversation, indent=2) if raw_conversation else 'None'}\n"
                        "---\nAuto-created by agent-nemo Customer Support System."
                    ),
                },
                "priority": priority,
                "tags": ["automated", "escalation", "agent-nemo"],
            }
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                json=ticket_payload,
                auth=auth,
                headers={"Content-Type": "application/json"},
            )

        if response.status_code == 201:
            data = response.json()
            ticket = data.get("ticket", {})
            ticket_id = str(ticket.get("id", ""))
            ticket_url = ticket.get("url", "")
            success = True
        else:
            error = f"Zendesk API returned {response.status_code}: {response.text[:200]}"

    except httpx.TimeoutException:
        error = "Zendesk API request timed out"
    except Exception as e:
        error = str(e)

    return {
        "success": success,
        "ticket_id": ticket_id,
        "ticket_url": ticket_url,
        "priority": priority,
        "error": error,
    }


@function_tool(strict_mode=False, name_override="log_resolution")
async def _log_resolution_tool(
    session_id: str,
    outcome: dict,
) -> dict:
    """Record resolution outcome in the data warehouse."""
    record_id = None
    error = None
    success = False

    try:
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        customer_id = outcome.get("customer_id", "unknown")
        resolution_data = outcome.get("resolution_data", {})
        escalation_bundle = outcome.get("escalation_bundle")
        notifications_sent = outcome.get("notifications_sent", [])
        final_outcome = outcome.get("final_outcome", "pending")
        resolution_time_seconds = outcome.get("resolution_time_seconds")

        if final_outcome not in ("resolved", "pending", "escalated"):
            final_outcome = "pending"

        log_entry = {
            "log_id": record_id,
            "session_id": session_id,
            "customer_id": customer_id,
            "resolution_data": resolution_data,
            "escalation_bundle": escalation_bundle,
            "notifications_sent": notifications_sent,
            "final_outcome": final_outcome,
            "resolution_time_seconds": resolution_time_seconds,
            "timestamp": timestamp,
        }

        log_file_path = os.environ.get("RESOLUTION_LOG_PATH", "resolution_log.jsonl")
        with open(log_file_path, "a", encoding="utf-8") as f:
            json.dump(log_entry, f)
            f.write("\n")

        success = True

    except Exception as e:
        error = str(e)

    return {
        "success": success,
        "record_id": record_id,
        "error": error,
    }


# Public wrappers for direct invocation (used by tests and escalation_agent)
async def create_human_ticket(context_bundle: dict[str, Any]) -> dict[str, Any]:
    """Open a Zendesk ticket with full conversation context."""
    input_json = json.dumps({"context_bundle": context_bundle})

    class _Ctx:
        def __init__(self, name: str) -> None:
            self.tool_name = name

    return await _create_human_ticket_tool.on_invoke_tool(_Ctx("create_human_ticket"), input_json)


async def log_resolution(session_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
    """Record resolution outcome in the data warehouse."""
    input_json = json.dumps({"session_id": session_id, "outcome": outcome})

    class _Ctx:
        def __init__(self, name: str) -> None:
            self.tool_name = name

    return await _log_resolution_tool.on_invoke_tool(_Ctx("log_resolution"), input_json)
