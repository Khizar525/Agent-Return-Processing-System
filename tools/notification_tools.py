"""
Notification Tools
Owner: Member 4

Sends customer-facing messages via SendGrid (email) or Twilio (SMS).

Interface Spec (do not change signatures without Lead approval):

    send_notification(customer_id: str, channel: str, subject: str, body: str) -> dict
        Args:
            customer_id: used to look up email/phone from CRM
            channel:     "email" | "sms"
            subject:     email subject line (ignored for SMS)
            body:        message body — must pass brand_voice guardrail first
        Returns:
            {
                "success": bool,
                "message_id": str,
                "channel": str,
                "delivered_at": str,   # ISO-8601
                "error": str | None,
            }

Environment variables required:
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
"""

from typing import Any
from agents import function_tool  # type: ignore[attr-defined]


# TODO (Member 4): implement send_notification below
@function_tool  # type: ignore[untyped-decorator]
async def send_notification(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send an email or SMS notification to the customer."""
    raise NotImplementedError("Member 4: implement send_notification")
