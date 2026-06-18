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

import os
import json
from typing import Dict, Any, Optional
from agents import Agent
from tools.notification_tools import send_notification
from guardrails.brand_voice import brand_voice_guardrail

# Try to import requests for HTTP calls to LLM APIs
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class HybridCommunicationAgent:
    """
    Communication Agent with hybrid LLM orchestration:
    - Primary: Cloud model (llama-3-70b-super-free via OpenCode Zen)
    - Fallback: Local model (phi4-mini:3.8b via Ollama)
    """

    def __init__(self):
        # Configuration from environment variables
        self.opencode_zen_url = os.environ.get('OPENCODE_ZEN_URL', 'https://opencode.zendesk.com/api/v1/generate')
        self.ollama_url = os.environ.get('OLLAMA_URL', 'http://localhost:11434/api/generate')
        self.cloud_model = os.environ.get('CLOUD_MODEL', 'llama-3-70b-super-free')
        self.local_model = os.environ.get('LOCAL_MODEL', 'phi4-mini:3.8b')

        # Privacy-sensitive keywords that force local model usage
        self.privacy_sensitive_keywords = {
            'ssn', 'social security', 'credit card', 'cvv', 'password',
            'pin', 'account number', 'routing number', 'medical', 'health',
            'prescription', 'therapy', 'counseling', 'legal case', 'lawsuit'
        }

        # Request timeout settings
        self.request_timeout = int(os.environ.get('LLM_REQUEST_TIMEOUT', '30'))

        # Track last used model for potential telemetry
        self.last_used_model = None

    def _is_privacy_sensitive(self, text: str) -> bool:
        """Check if text contains privacy-sensitive information that requires local model."""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.privacy_sensitive_keywords)

    def _call_cloud_model(self, prompt: str) -> Optional[str]:
        """Call the cloud model via OpenCode Zen API."""
        if not REQUESTS_AVAILABLE:
            return None

        try:
            payload = {
                "model": self.cloud_model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 500
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.environ.get('OPENCODE_ZEN_API_KEY', '')}"
            }

            response = requests.post(
                self.opencode_zen_url,
                json=payload,
                headers=headers,
                timeout=self.request_timeout
            )

            if response.status_code == 200:
                result = response.json()
                self.last_used_model = self.cloud_model
                return result.get('response', '')
            else:
                return None

        except Exception:
            return None

    def _call_local_model(self, prompt: str) -> Optional[str]:
        """Call the local model via Ollama API."""
        if not REQUESTS_AVAILABLE:
            return None

        try:
            payload = {
                "model": self.local_model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7,
                "max_tokens": 500
            }

            response = requests.post(
                self.ollama_url,
                json=payload,
                timeout=self.request_timeout
            )

            if response.status_code == 200:
                result = response.json()
                self.last_used_model = self.local_model
                return result.get('response', '')
            else:
                return None

        except Exception:
            return None

    def _generate_response_with_fallback(self, prompt: str, force_local: bool = False) -> str:
        """
        Generate response using hybrid LLM approach:
        - Try cloud model first (unless force_local is True)
        - Fallback to local model on any exception
        - Return fallback message if both fail
        """
        # If privacy-sensitive or forced local, use local model only
        if force_local or self._is_privacy_sensitive(prompt):
            response = self._call_local_model(prompt)
            if response:
                return response
            # If local model fails, we still return what we got (might be empty)
            return response or "I apologize, but I'm unable to process your request at the moment. Please try again later."

        # Otherwise, try cloud model first, then fallback to local
        response = self._call_cloud_model(prompt)
        if response:
            return response

        # Cloud model failed, try local model as fallback
        response = self._call_local_model(prompt)
        if response:
            return response

        # Both models failed
        return "I apologize, but I'm unable to process your request at the moment. Please try again later."


# Initialize the hybrid agent
hybrid_agent = HybridCommunicationAgent()


# Legacy Agent wrapper for backward compatibility with existing Agent framework
# This maintains the interface expected by the rest of the system
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
    model="hybrid",  # Indicates hybrid usage
    tools=[send_notification],
    output_guardrails=[brand_voice_guardrail],
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
    # Extract first name for personalization
    first_name = customer_name.split()[0] if customer_name else "valued customer"

    # Extract resolution information
    resolution_type = resolution_data.get("resolution_type", "resolved")
    description = resolution_data.get("description", "Your issue has been addressed.")
    amount = resolution_data.get("amount")
    currency = resolution_data.get("currency", "USD")

    # Build resolution summary
    if amount and amount > 0:
        resolution_summary = f"We have processed a {resolution_type} of {currency} {amount:.2f} for you. {description}"
    else:
        resolution_summary = f"We have {resolution_type} your issue. {description}"

    # Build next steps
    next_steps = "Please check your email for confirmation. If you have any further questions, don't hesitate to reach out."

    # Reference/ticket number (in a real implementation, this would come from a database or prior step)
    reference_number = f"REF-{customer_id[-6:] if len(customer_id) >= 6 else customer_id}"

    # Draft the message
    message_body = f"""Hello {first_name},

{resolution_summary}

{next_steps}

Reference: {reference_number}

Thank you for choosing our service."""

    # Determine notification channel based on available contact info
    # Priority: email if available, otherwise SMS
    if customer_email and "@" in customer_email:
        notification_type = "email"
        recipient = customer_email
        subject = f"Update on your case {reference_number}"
    elif customer_phone:
        notification_type = "sms"
        recipient = customer_phone
        subject = ""  # Not used for SMS
    else:
        # Fallback - shouldn't happen in valid scenarios
        notification_type = "email"
        recipient = "no-reply@example.com"
        subject = "Notification Failed - Missing Contact Info"

    # Send the notification
    notification_result = await send_notification(
        notification_type=notification_type,
        recipient=recipient,
        subject=subject,
        body=message_body
    )

    # Prepare return value
    return {
        "ticket_number": reference_number,
        "resolution_summary": resolution_summary,
        "next_steps": next_steps,
        "message_sent": message_body,
        "channel_used": notification_result.get("channel", notification_type),
    }


# Enhanced function that uses hybrid LLM for message generation
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
    # Extract first name for personalization
    first_name = customer_name.split()[0] if customer_name else "valued customer"

    # Extract resolution information
    resolution_type = resolution_data.get("resolution_type", "resolved")
    description = resolution_data.get("description", "Your issue has been addressed.")
    amount = resolution_data.get("amount")
    currency = resolution_data.get("currency", "USD")

    # Build resolution summary
    if amount and amount > 0:
        resolution_summary = f"We have processed a {resolution_type} of {currency} {amount:.2f} for you. {description}"
    else:
        resolution_summary = f"We have {resolution_type} your issue. {description}"

    # Build next steps
    next_steps = "Please check your email for confirmation. If you have any further questions, don't hesitate to reach out."

    # Reference/ticket number
    reference_number = f"REF-{customer_id[-6:] if len(customer_id) >= 6 else customer_id}"

    # Draft the message prompt for LLM
    message_prompt = f"""Draft a professional, empathetic customer service message with the following information:

    Customer: {first_name}
    Resolution: {resolution_summary}
    Next Steps: {next_steps}
    Reference: {reference_number}

    Requirements:
    - Start with a greeting using the customer's first name
    - Clearly state the resolution
    - Provide helpful next steps
    - Include the reference number
    - Keep tone professional and empathetic
    - Keep message under 150 words
    - Format as a proper email/SMS message"""

    # Generate message using hybrid LLM
    generated_message = hybrid_agent._generate_response_with_fallback(message_prompt, force_local)

    # Use the generated message if it's good enough, otherwise fall back to template
    if generated_message and len(generated_message.strip()) > 10:
        # Use LLM-generated message, but ensure it has the reference
        if reference_number not in generated_message:
            # Add reference if missing
            message_body = f"""{generated_message}

Reference: {reference_number}"""
        else:
            message_body = generated_message
    else:
        # Fall back to template message
        message_body = f"""Hello {first_name},

{resolution_summary}

{next_steps}

Reference: {reference_number}

Thank you for choosing our service."""

    # Send the notification
    notification_result = await send_notification(
        notification_type="email" if customer_email and "@" in customer_email else "sms",
        recipient=customer_email if customer_email and "@" in customer_email else customer_phone,
        subject=f"Update on your case {reference_number}" if notification_type == "email" else "",
        body=message_body
    )

    # Prepare return value
    return {
        "ticket_number": reference_number,
        "resolution_summary": resolution_summary,
        "next_steps": next_steps,
        "message_sent": message_body,
        "channel_used": notification_result.get("channel",
                                              "email" if customer_email and "@" in customer_email else "sms"),
        "llm_used": hybrid_agent.last_used_model or "unknown"
    }