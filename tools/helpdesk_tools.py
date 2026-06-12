"""
Helpdesk Tools
Owner: Member 4

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

from typing import Any
from agents import function_tool  # type: ignore[attr-defined]


# TODO (Member 4): implement create_human_ticket below
@function_tool  # type: ignore[untyped-decorator]
async def create_human_ticket(context_bundle: dict[str, Any]) -> dict[str, Any]:
    """Open a Zendesk ticket with full conversation context."""
    raise NotImplementedError("Member 4: implement create_human_ticket")


# TODO (Member 4): implement log_resolution below
@function_tool  # type: ignore[untyped-decorator]
async def log_resolution(session_id: str, outcome: dict[str, Any]) -> dict[str, Any]:
    """Record resolution outcome in the data warehouse."""
    raise NotImplementedError("Member 4: implement log_resolution")
