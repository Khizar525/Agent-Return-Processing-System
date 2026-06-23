"""
Escalation Agent
Owner: Member 4

Handles edge cases that cannot be resolved autonomously:
    - Sentiment Monitor score > 0.8 (customer distress)
    - High-value orders (> $500 refund cap)
    - Legal threats or explicit escalation demands
    - Repeat fraud flags on account

Responsibilities:
    1. Compile full context bundle (customer_id, order history,
       agent_chain, all tool results, timestamps)
    2. Open ticket in Zendesk via create_human_ticket
    3. Log resolution outcome via log_resolution

Model: deepseek-v4-flash-free (mandated by ADR-001 for all agents)

Dependencies:
    - tools/helpdesk_tools.py  (create_human_ticket, log_resolution) — Member 4 (you)
"""

from typing import Dict, Any, Optional
from agents import Agent, Runner
from pydantic import BaseModel, Field
from tools.helpdesk_tools import (
    _create_human_ticket_tool as create_human_ticket_tool,
    _log_resolution_tool as log_resolution_tool,
)


class EscalationSummary(BaseModel):
    """Structured output from the Escalation Agent."""

    success: bool = Field(description="Whether the escalation process was successfully completed.")
    ticket_id: str | None = Field(
        default=None, description="The Zendesk ticket ID, if successfully created."
    )
    ticket_url: str | None = Field(
        default=None, description="The Zendesk ticket URL, if successfully created."
    )
    priority: str | None = Field(
        default=None, description="The ticket priority: 'low' | 'normal' | 'high' | 'urgent'"
    )
    context_bundle: Dict[str, Any] | None = Field(
        default=None, description="The compiled context bundle used for the escalation."
    )
    escalation_reason: str | None = Field(
        default=None, description="The determined reason for escalation."
    )
    error: str | None = Field(default=None, description="Error message if execution failed.")
    llm_used: Optional[str] = Field(
        default=None, description="Which LLM was actually used (cloud/local)"
    )


# Escalation Agent definition
escalation_agent = Agent(
    name="EscalationAgent",
    instructions=(
        "You are the Escalation Agent, an autonomous decision-making agent responsible for handling edge cases "
        "that require human intervention.\n\n"
        "Your guidelines are:\n"
        "1. When receiving customer context, first determine if escalation is warranted based on:\n"
        "   - Sentiment Monitor score > 0.8 (indicating customer distress)\n"
        "   - High-value orders (> $500 refund cap)\n"
        "   - Legal threats or explicit escalation demands\n"
        "   - Repeat fraud flags on account\n"
        "2. If escalation is warranted:\n"
        "   a. Compile a full context bundle including:\n"
        "      - customer_id, session_id, agent_chain, intent\n"
        "      - policy_decision, resolution_action (if available)\n"
        "      - escalation_reason (determined from the above criteria)\n"
        "      - order_history, timestamps, raw_conversation\n"
        "   b. Use the compile_context_bundle logic to structure this information properly\n"
        "   c. Open a ticket in Zendesk using the create_human_ticket tool with the compiled context bundle\n"
        "   d. Log the resolution outcome using the log_resolution tool\n"
        "   e. Return success with the ticket details and context bundle\n"
        "3. If escalation is not warranted, return success with appropriate reasoning\n"
        "4. Always handle tool errors gracefully - if a tool returns an error, do not crash but return the error in your structured output\n"
        "5. Be thorough - include every detail the human agent will need in the context bundle\n\n"
        "Escalation reasons and their priorities:\n"
        "- Sentiment Monitor score > 0.8: high_sentiment (priority: high)\n"
        "- High-value orders (> $500): high_value_order (priority: high)\n"
        "- Legal threats or explicit escalation demands: legal_threats (priority: high)\n"
        "- Repeat fraud flags on account: repeat_fraud (priority: urgent)\n"
    ),
    model="deepseek-v4-flash-free",
    tools=[create_human_ticket_tool, log_resolution_tool],
    output_type=EscalationSummary,
)


# Legacy function for direct use (not part of the Agent framework)
# This maintains backward compatibility and can be used for testing
async def handle_escalation(
    customer_id: str,
    session_id: str,
    agent_chain: list[str],
    intent: str,
    policy_decision: dict | None,
    resolution_action: str | None,
    escalation_reason: str,
    order_history: list[dict],
    timestamps: dict,
    raw_conversation: list[dict],
) -> dict:
    """
    Handle escalation cases that require human intervention.

    Args:
        customer_id: Unique customer identifier
        session_id: Session identifier
        agent_chain: List of agents involved in the case so far
        intent: Customer intent
        policy_decision: Policy decision if available
        resolution_action: Resolution action if available
        escalation_reason: Reason for escalation
        order_history: Customer order history
        timestamps: Timestamps of events
        raw_conversation: Raw conversation history

    Returns:
        {
            "success": bool,
            "ticket_id": str | None,
            "ticket_url": str | None,
            "priority": str | None,
            "context_bundle": dict | None,
            "escalation_reason": str | None,
            "error": str | None,
        }
    """
    # Use the escalation agent via Runner
    context = {
        "customer_id": customer_id,
        "session_id": session_id,
        "agent_chain": agent_chain,
        "intent": intent,
        "policy_decision": policy_decision,
        "resolution_action": resolution_action,
        "escalation_reason": escalation_reason,
        "order_history": order_history,
        "timestamps": timestamps,
        "raw_conversation": raw_conversation,
    }

    result = await Runner.run(
        escalation_agent,
        "Handle the escalation case based on the provided context.",
        context=context,
    )

    # Extract the structured output
    output = result.final_output_as(EscalationSummary)

    # Prepare return value in legacy format
    return {
        "success": output.success,
        "ticket_id": output.ticket_id,
        "ticket_url": output.ticket_url,
        "priority": output.priority,
        "context_bundle": output.context_bundle,
        "escalation_reason": output.escalation_reason,
        "error": output.error,
    }


# Enhanced function that uses hybrid LLM for escalation handling
# Note: The actual LLM selection is handled by the Agent framework based on the model setting
async def handle_escalation_with_hybrid_llm(
    customer_id: str,
    session_id: str,
    agent_chain: list[str],
    intent: str,
    policy_decision: dict | None,
    resolution_action: str | None,
    escalation_reason: str,
    order_history: list[dict],
    timestamps: dict,
    raw_conversation: list[dict],
    force_local: bool = False,
) -> dict:
    """
    Handle escalation cases using hybrid LLM orchestration.

    Args:
        customer_id: Unique customer identifier
        session_id: Session identifier
        agent_chain: List of agents involved in the case so far
        intent: Customer intent
        policy_decision: Policy decision if available
        resolution_action: Resolution action if available
        escalation_reason: Reason for escalation
        order_history: Customer order history
        timestamps: Timestamps of events
        raw_conversation: Raw conversation history
        force_local: If True, forces usage of local model (for privacy-sensitive operations)

    Returns:
        {
            "success": bool,
            "ticket_id": str | None,
            "ticket_url": str | None,
            "priority": str | None,
            "context_bundle": dict | None,
            "escalation_reason": str | None,
            "error": str | None,
            "llm_used": str,  # Which LLM was actually used (cloud/local)
        }
    """
    # Use the escalation agent via Runner
    context = {
        "customer_id": customer_id,
        "session_id": session_id,
        "agent_chain": agent_chain,
        "intent": intent,
        "policy_decision": policy_decision,
        "resolution_action": resolution_action,
        "escalation_reason": escalation_reason,
        "order_history": order_history,
        "timestamps": timestamps,
        "raw_conversation": raw_conversation,
        "force_local": force_local,
    }

    result = await Runner.run(
        escalation_agent,
        "Handle the escalation case using hybrid LLM orchestration based on the provided context.",
        context=context,
    )

    # Extract the structured output
    output = result.final_output_as(EscalationSummary)

    # Prepare return value
    return {
        "success": output.success,
        "ticket_id": output.ticket_id,
        "ticket_url": output.ticket_url,
        "priority": output.priority,
        "context_bundle": output.context_bundle,
        "escalation_reason": output.escalation_reason,
        "error": output.error,
        "llm_used": output.llm_used or "unknown",
    }
