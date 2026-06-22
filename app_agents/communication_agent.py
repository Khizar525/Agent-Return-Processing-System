"""
Communication Agent
Owner: Member 4

Drafts and sends customer-facing messages (email, SMS, chat) after a
resolution has been confirmed by the Resolution Agent.

Requirements:
    - Brand voice guardrail applied to every output (see guardrails/brand_voice.py)
    - Messages must be <= 150 words
    - Tone: professional, empathetic, concise
    - Must include: resolution summary, next steps, reference/ticket number

Dependencies:
    - tools/notification_tools.py  (send_notification)  — Member 4 (you)
    - guardrails/brand_voice.py                         — Member 4 (you)
"""

from typing import Optional
from agents import Agent, Runner
from pydantic import BaseModel, Field
from tools.notification_tools import _send_notification_tool as send_notification_tool
from guardrails.brand_voice import brand_voice_guardrail


class CommunicationAgentOutput(BaseModel):
    """Structured output from the Communication Agent."""
    ticket_number: str = Field(description="Reference/ticket number for the communication")
    resolution_summary: str = Field(description="Summary of the resolution provided to the customer")
    next_steps: str = Field(description="Next steps the customer needs to take")
    message_sent: str = Field(description="The actual message that was sent to the customer")
    channel_used: str = Field(description="The channel used to send the message (email or sms)")
    llm_used: Optional[str] = Field(default=None, description="Which LLM was used (cloud/local)")


# Communication Agent definition
communication_agent = Agent(
    name="CommunicationAgent",
    instructions=(
        "You are a customer support communication agent. Your role is to draft and send "
        "professional, empathetic messages to customers after their issue has been resolved.\n\n"
        "When drafting messages:\n"
        "1. Start with a greeting using the customer's first name if known\n"
        "2. Clearly state the resolution summary\n"
        "3. Provide any next steps the customer needs to take\n"
        "4. Include any reference or ticket numbers\n"
        "5. Keep the tone professional, empathetic, and concise\n"
        "6. Ensure the message is under 150 words\n"
        "7. The brand voice guardrail will automatically check and refine your output\n\n"
        "You will receive customer information and resolution data to include in your message."
    ),
    model="deepseek-v4-flash-free",  # Per ADR-001
    tools=[send_notification_tool],
    output_guardrails=[brand_voice_guardrail],
    output_type=CommunicationAgentOutput,
)


# Legacy function for direct use (not part of the Agent framework)
# This maintains backward compatibility and can be used for testing
async def draft_and_send(
    customer_id: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    resolution_data: dict,
) -> dict:
    """
    Draft and send a customer message based on resolution data.

    Args:
        customer_id: Unique customer identifier
        customer_name: Customer's full name
        customer_email: Customer's email address
        customer_phone: Customer's phone number
        resolution_data: Information about how the customer issue was resolved

    Returns:
        {
            "ticket_number": str,
            "resolution_summary": str,
            "next_steps": str,
            "message_sent": str,
            "channel_used": str,
        }
    """
    # Use the communication agent via Runner
    context = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "resolution_data": resolution_data,
    }

    result = await Runner.run(communication_agent,
                             "Draft and send a customer message based on the provided resolution data.",
                             context=context)

    # Extract the structured output
    output = result.final_output_as(CommunicationAgentOutput)

    # Prepare return value in legacy format
    return {
        "ticket_number": output.ticket_number,
        "resolution_summary": output.resolution_summary,
        "next_steps": output.next_steps,
        "message_sent": output.message_sent,
        "channel_used": output.channel_used,
    }


# Enhanced function that uses hybrid LLM for message generation
# Note: The actual LLM selection is handled by the Agent framework based on the model setting
async def draft_and_send_with_hybrid_llm(
    customer_id: str,
    customer_name: str,
    customer_email: str,
    customer_phone: str,
    resolution_data: dict,
    force_local: bool = False,
) -> dict:
    """
    Draft and send a customer message using hybrid LLM orchestration.

    Args:
        customer_id: Unique customer identifier
        customer_name: Customer's full name
        customer_email: Customer's email address
        customer_phone: Customer's phone number
        resolution_data: Information about how the customer issue was resolved
        force_local: If True, forces usage of local model (for privacy-sensitive operations)

    Returns:
        {
            "ticket_number": str,
            "resolution_summary": str,
            "next_steps": str,
            "message_sent": str,
            "channel_used": str,
            "llm_used": str,  # Which LLM was actually used (cloud/local)
        }
    """
    # Use the communication agent via Runner
    context = {
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "resolution_data": resolution_data,
        "force_local": force_local,
    }

    result = await Runner.run(communication_agent,
                             "Draft and send a customer message using hybrid LLM orchestration based on the provided resolution data.",
                             context=context)

    # Extract the structured output
    output = result.final_output_as(CommunicationAgentOutput)

    # Prepare return value
    return {
        "ticket_number": output.ticket_number,
        "resolution_summary": output.resolution_summary,
        "next_steps": output.next_steps,
        "message_sent": output.message_sent,
        "channel_used": output.channel_used,
        "llm_used": output.llm_used or "unknown"
    }