"""
Notification Tools
Owner: Member 4 (implemented), Lead (post-merge cleanup)

Sends customer-facing messages via SendGrid (email) or Twilio (SMS).

Interface Spec (do not change signatures without Lead approval):

    send_notification(customer_id: str, channel: str, subject: str, body: str) -> dict
        Args:
            customer_id: Unique customer identifier
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
    SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
    CUSTOMER_EMAIL_MAP, CUSTOMER_PHONE_MAP (JSON format, for testing)
"""

from __future__ import annotations

import json
import os
import datetime
from typing import Any

from agents import function_tool

try:
    import sendgrid
    from sendgrid.helpers.mail import Mail

    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

try:
    from twilio.rest import Client

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False


def _get_customer_contact(customer_id: str, channel: str) -> tuple[str, str]:
    """Return (to_address, from_address) for the given channel."""
    if channel == "email":
        email_map = json.loads(os.environ.get("CUSTOMER_EMAIL_MAP", "{}"))
        to_email = email_map.get(customer_id, os.environ.get("SENDGRID_FROM_EMAIL", "test@example.com"))
        from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@example.com")
        return to_email, from_email

    if channel == "sms":
        phone_map = json.loads(os.environ.get("CUSTOMER_PHONE_MAP", "{}"))
        to_phone = phone_map.get(customer_id, os.environ.get("TWILIO_FROM_NUMBER", "+1234567890"))
        from_phone = os.environ.get("TWILIO_FROM_NUMBER", "+1234567890")
        return to_phone, from_phone

    raise ValueError(f"Invalid channel: {channel}. Must be 'email' or 'sms'")


async def _send_email(to_email: str, from_email: str, subject: str, body: str) -> dict[str, Any]:
    """Send email via SendGrid. Returns standardized result dict."""
    try:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            return {"success": False, "message_id": "", "error": "SENDGRID_API_KEY not set"}

        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        mail = Mail(from_email=from_email, to_emails=to_email, subject=subject, plain_text_content=body)
        response = sg.send(mail)

        if 200 <= response.status_code < 300:
            message_id = response.headers.get("X-Message-Id", "")
            delivered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return {"success": True, "message_id": message_id, "delivered_at": delivered_at, "error": None}

        return {"success": False, "message_id": "", "error": f"SendGrid returned {response.status_code}"}
    except Exception as e:
        return {"success": False, "message_id": "", "error": str(e)}


async def _send_sms(to_phone: str, from_phone: str, body: str) -> dict[str, Any]:
    """Send SMS via Twilio. Returns standardized result dict."""
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        if not account_sid or not auth_token:
            return {"success": False, "message_id": "", "error": "Twilio credentials not set"}

        client = Client(account_sid, auth_token)
        message = client.messages.create(body=body, from_=from_phone, to=to_phone)

        if message.sid:
            delivered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return {"success": True, "message_id": message.sid, "delivered_at": delivered_at, "error": None}

        return {"success": False, "message_id": "", "error": "Twilio returned empty SID"}
    except Exception as e:
        return {"success": False, "message_id": "", "error": str(e)}


async def send_notification_impl(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send an email or SMS notification with email→SMS fallback."""
    if channel not in ("email", "sms"):
        return {"success": False, "message_id": "", "channel": channel,
                "delivered_at": None, "error": f"Invalid channel: {channel}"}

    if channel == "email":
        if not SENDGRID_AVAILABLE:
            # Fallback to SMS
            if TWILIO_AVAILABLE:
                to_phone, from_phone = _get_customer_contact(customer_id, "sms")
                result = await _send_sms(to_phone, from_phone, body)
                result["channel"] = "sms"
                return result
            return {"success": False, "message_id": "", "channel": channel,
                    "delivered_at": None, "error": "SendGrid not installed"}

        to_email, from_email = _get_customer_contact(customer_id, "email")
        result = await _send_email(to_email, from_email, subject, body)
        if not result["success"] and TWILIO_AVAILABLE:
            # Fallback to SMS on failure
            to_phone, from_phone = _get_customer_contact(customer_id, "sms")
            sms_result = await _send_sms(to_phone, from_phone, body)
            sms_result["channel"] = "sms"
            return sms_result
        result["channel"] = "email"
        return result

    # channel == "sms"
    if not TWILIO_AVAILABLE:
        return {"success": False, "message_id": "", "channel": channel,
                "delivered_at": None, "error": "Twilio not installed"}

    to_phone, from_phone = _get_customer_contact(customer_id, "sms")
    result = await _send_sms(to_phone, from_phone, body)
    result["channel"] = "sms"
    return result


@function_tool(strict_mode=False, name_override="send_notification")
async def _send_notification_tool(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict:
    """Internal function tool for sending notifications."""
    try:
        result = await send_notification_impl(customer_id, channel, subject, body)
    except Exception as e:
        return {"success": False, "message_id": "", "channel": channel,
                "delivered_at": None, "error": str(e)}
    # Ensure all expected keys are present
    result.setdefault("message_id", "")
    result.setdefault("channel", channel)
    result.setdefault("delivered_at", None)
    result.setdefault("error", None)
    return result


async def send_notification(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Send an email or SMS notification to the customer (public wrapper)."""
    input_json = json.dumps({
        "customer_id": customer_id,
        "channel": channel,
        "subject": subject,
        "body": body,
    })

    class _Ctx:
        def __init__(self, name: str) -> None:
            self.tool_name = name

    return await _send_notification_tool.on_invoke_tool(_Ctx("send_notification"), input_json)
