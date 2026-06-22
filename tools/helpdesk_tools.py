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

import json
import os
import uuid
import datetime
from agents import function_tool
from typing import List, Union, Dict, Any

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# Internal FunctionTool instances (not to be called directly)
@function_tool(strict_mode=False, name_override="create_human_ticket")
async def _create_human_ticket_tool(
    context_bundle: dict
) -> dict:
    """Open a Zendesk ticket with full conversation context."""
    # Initialize return values
    ticket_id = None
    ticket_url = None
    priority = "normal"
    error = None
    success = False

    # Check if requests library is available
    if not REQUESTS_AVAILABLE:
        error = "requests library not installed"
        return {
            "success": False,
            "ticket_id": ticket_id,
            "ticket_url": ticket_url,
            "priority": priority,
            "error": error,
        }

    try:
        # Get environment variables
        zendesk_subdomain = os.environ.get('ZENDESK_SUBDOMAIN')
        zendesk_email = os.environ.get('ZENDESK_EMAIL')
        zendesk_api_token = os.environ.get('ZENDESK_API_TOKEN')

        if not zendesk_subdomain:
            error = "ZENDESK_SUBDOMAIN environment variable not set"
            raise ValueError(error)
        if not zendesk_email:
            error = "ZENDESK_EMAIL environment variable not set"
            raise ValueError(error)
        if not zendesk_api_token:
            error = "ZENDESK_API_TOKEN environment variable not set"
            raise ValueError(error)

        # Construct Zendesk API URL
        url = f"https://{zendesk_subdomain}.zendesk.com/api/v2/tickets.json"

        # Set up authentication (email/token format)
        # The email needs to be in the format: "email/token"
        auth_email = f"{zendesk_email}/token"

        # Prepare ticket data from context_bundle
        # Extract relevant information
        customer_id = context_bundle["customer_id"]
        session_id = context_bundle["session_id"]
        agent_chain = context_bundle["agent_chain"]
        intent = context_bundle["intent"]
        policy_decision = context_bundle.get("policy_decision")
        resolution_action = context_bundle.get("resolution_action")
        escalation_reason = context_bundle["escalation_reason"]
        order_history = context_bundle["order_history"]
        timestamps = context_bundle["timestamps"]
        raw_conversation = context_bundle["raw_conversation"]

        # Determine priority based on context (simple heuristic)
        # In a real implementation, this would be more sophisticated
        priority = "normal"  # default
        if escalation_reason in ["legal_threats", "high_value_order"]:
            priority = "high"
        elif escalation_reason == "repeat_fraud":
            priority = "urgent"

        # Create ticket payload
        ticket_data = {
            "ticket": {
                "subject": f"Customer Support Escalation: {intent}",
                "comment": {
                    "body": f"""Customer Support Escalation Ticket

Customer ID: {customer_id}
Session ID: {session_id}
Intent: {intent}
Escalation Reason: {escalation_reason}

Agent Chain: {', '.join(agent_chain) if agent_chain else 'None'}

Policy Decision: {json.dumps(policy_decision) if policy_decision else 'None'}
Resolution Action: {resolution_action or 'None'}

Order History: {json.dumps(order_history, indent=2) if order_history else 'None'}

Timestamps: {json.dumps(timestamps, indent=2) if timestamps else 'None'}

Raw Conversation:
{json.dumps(raw_conversation, indent=2) if raw_conversation else 'None'}

---
This ticket was automatically created by the Agent01 Customer Support System.
""",
                },
                "priority": priority,
                "tags": ["automated", "escalation", "agent01"],
            }
        }

        # Make the API request
        response = requests.post(
            url,
            json=ticket_data,
            auth=(auth_email, zendesk_api_token),
            headers={"Content-Type": "application/json"}
        )

        # Check if successful
        if response.status_code == 201:
            ticket_data = response.json()
            ticket = ticket_data.get("ticket", {})
            ticket_id = str(ticket.get("id", ""))
            ticket_url = ticket.get("url", "")
            success = True
        else:
            error = f"Zendesk API returned status code {response.status_code}: {response.text}"

    except Exception as e:
        error = str(e)

    # Return result
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
    outcome: dict
) -> dict:
    """Record resolution outcome in the data warehouse."""
    # Initialize return values
    record_id = None
    error = None
    success = False

    try:
        # Generate a unique ID for this log entry
        record_id = str(uuid.uuid4())

        # Get current timestamp
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Extract information from outcome dict
        # The outcome dict should contain resolution information
        customer_id = outcome.get("customer_id", "unknown")
        resolution_data = outcome.get("resolution_data", {})
        escalation_bundle = outcome.get("escalation_bundle")
        notifications_sent = outcome.get("notifications_sent", [])
        final_outcome = outcome.get("final_outcome", "pending")
        resolution_time_seconds = outcome.get("resolution_time_seconds")

        # Validate final_outcome
        valid_outcomes = ["resolved", "pending", "escalated"]
        if final_outcome not in valid_outcomes:
            final_outcome = "pending"  # default to pending if invalid

        # Create the log entry following ResolutionLogEntry structure from data-model.md
        log_entry = {
            "log_id": record_id,
            "customer_id": customer_id,
            "resolution_data": resolution_data,
            "escalation_bundle": escalation_bundle,
            "notifications_sent": notifications_sent,
            "final_outcome": final_outcome,
            "resolution_time_seconds": resolution_time_seconds,
            "timestamp": timestamp
        }

        # Write to resolution_log.jsonl file (append one JSON line per entry)
        log_file_path = "resolution_log.jsonl"

        with open(log_file_path, "a", encoding="utf-8") as f:
            json.dump(log_entry, f)
            f.write("\n")

        success = True

    except Exception as e:
        error = str(e)

    # Return result
    return {
        "success": success,
        "record_id": record_id,
        "error": error,
    }


# A mock ToolContext class for direct tool invocation
class _MockToolContext:
    def __init__(self, tool_name: str):
        self.tool_name = tool_name


# Public wrapper functions that can be called directly (for testing, etc.)
async def create_human_ticket(context_bundle: dict) -> dict:
    """Open a Zendesk ticket with full conversation context (public wrapper)."""
    # Create a mock tool context
    ctx = _MockToolContext(tool_name="create_human_ticket")
    # Convert the input to JSON string: wrap the context_bundle in an object with key "context_bundle"
    input_json = json.dumps({"context_bundle": context_bundle})
    # Invoke the internal tool
    return await _create_human_ticket_tool.on_invoke_tool(ctx, input_json)


async def log_resolution(session_id: str, outcome: dict) -> dict:
    """Record resolution outcome in the data warehouse (public wrapper)."""
    # Create a mock tool context
    ctx = _MockToolContext(tool_name="log_resolution")
    # Convert the input to JSON string
    input_json = json.dumps({"session_id": session_id, "outcome": outcome})
    # Invoke the internal tool
    return await _log_resolution_tool.on_invoke_tool(ctx, input_json)