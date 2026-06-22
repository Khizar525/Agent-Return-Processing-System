"""
Notification Tools
Owner: Member 4

Sends customer-facing messages via SendGrid (email) or Twilio (SMS).

Interface Spec (do not change signatures without Lead approval):

    send_notification(customer_id: str, channel: str, subject: str, body: str) -> dict
        Args:
            customer_id: Unique customer identifier
            channel: "email" or "sms"
            subject: email subject line (ignored for SMS)
            body: message body — must pass band_guardrail first
        Returns:
            {
                "success": bool,
                "message_id": str,
                "channel": str,
                "delivered_at": str,   # ISO-8601
                "error": str | None,
            }

Environment variables required:
    SENDGRID_API_KEY, FROM_EMAIL, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
    CUSTOMER_EMAIL_MAP, CUSTOMER_PHONE_MAP (for testing - JSON format)
"""

import os
import datetime
import json
from agents import function_tool

# Try to import SendGrid and Twilio, but handle gracefully if not installed
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


def _get_customer_contact_info(customer_id: str, channel: str) -> tuple[str, str]:
    """
    Get customer contact information based on customer_id and channel.
    For testing, uses environment variables or fallback values.

    Returns:
        tuple of (contact_info, from_address)
        For email: (email_address, from_email)
        For SMS: (phone_number, from_phone_number)
    """
    # For email
    if channel == "email":
        # Try to get from environment variable mapping
        email_map_str = os.environ.get('CUSTOMER_EMAIL_MAP', '{}')
        try:
            email_map = json.loads(email_map_str)
            if customer_id in email_map:
                to_email = email_map[customer_id]
            else:
                # Fallback to environment variable or default
                to_email = os.environ.get('FROM_EMAIL', 'test@example.com')
        except json.JSONDecodeError:
            to_email = os.environ.get('FROM_EMAIL', 'test@example.com')

        from_email = os.environ.get('FROM_EMAIL', 'noreply@example.com')
        return to_email, from_email

    # For SMS
    elif channel == "sms":
        # Try to get from environment variable mapping
        phone_map_str = os.environ.get('CUSTOMER_PHONE_MAP', '{}')
        try:
            phone_map = json.loads(phone_map_str)
            if customer_id in phone_map:
                to_phone = phone_map[customer_id]
            else:
                # Fallback to environment variable or default
                to_phone = os.environ.get('TWILIO_FROM_NUMBER', '+1234567890')
        except json.JSONDecodeError:
            to_phone = os.environ.get('TWILIO_FROM_NUMBER', '+1234567890')

        from_phone = os.environ.get('TWILIO_FROM_NUMBER', '+1234567890')
        return to_phone, from_phone

    else:
        raise ValueError(f"Invalid channel: {channel}. Must be 'email' or 'sms'")


class _MockToolContext:
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        self.tool_call_id = "test"


async def send_notification_impl(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email or SMS notification to the customer."""
    # Initialize return values
    message_id = None
    delivered_at = None
    error = None
    success = False

    # Validate channel
    if channel not in ["email", "sms"]:
        error = f"Invalid channel: {channel}. Must be 'email' or 'sms'"
        return {
            "success": False,
            "message_id": message_id,
            "channel": channel,
            "delivered_at": delivered_at,
            "error": error,
        }

    try:
        # Get customer contact information
        contact_info, from_address = _get_customer_contact_info(customer_id, channel)

        # Handle email notifications
        if channel == "email":
            if not SENDGRID_AVAILABLE:
                error = "SendGrid library not installed"
                # Fallback to SMS if Twilio is available
                if TWILIO_AVAILABLE:
                    # Recursively call with SMS channel
                    return await send_notification_impl(
                        customer_id=customer_id,
                        channel="sms",
                        subject="",  # Subject ignored for SMS
                        body=body
                    )
                else:
                    return {
                        "success": False,
                        "message_id": message_id,
                        "channel": channel,
                        "delivered_at": delivered_at,
                        "error": error,
                    }
            else:
                try:
                    # Get environment variables
                    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')

                    if not sendgrid_api_key:
                        error = "SENDGRID_API_KEY environment variable not set"
                        raise ValueError(error)

                    # Create SendGrid client
                    sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)

                    # Create email
                    mail = Mail(
                        from_email=from_address,
                        to_emails=contact_info,
                        subject=subject,
                        plain_text_content=body
                    )

                    # Send email
                    response = sg.send(mail)

                    # Check if successful
                    if 200 <= response.status_code < 300:
                        success = True
                        message_id = response.headers.get('X-Message-Id', '')
                        delivered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    else:
                        error = f"SendGrid API returned status code {response.status_code}"
                        raise Exception(error)

                except Exception as e:
                    error = str(e)
                    # Fallback to SMS if Twilio is available
                    if TWILIO_AVAILABLE:
                        # Recursively call with SMS channel
                        return await send_notification_impl(
                            customer_id=customer_id,
                            channel="sms",
                            subject="",  # Subject ignored for SMS
                            body=body
                        )
                    else:
                        return {
                            "success": False,
                            "message_id": message_id,
                            "channel": channel,
                            "delivered_at": delivered_at,
                            "error": error,
                        }

        # Handle SMS notifications
        elif channel == "sms":
            if not TWILIO_AVAILABLE:
                error = "Twilio library not installed"
                return {
                    "success": False,
                    "message_id": message_id,
                    "channel": channel,
                    "delivered_at": delivered_at,
                    "error": error,
                }

            try:
                # Get environment variables
                twilio_account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
                twilio_auth_token = os.environ.get('TWILIO_AUTH_TOKEN')

                if not twilio_account_sid:
                    error = "TWILIO_ACCOUNT_SID environment variable not set"
                    raise ValueError(error)
                if not twilio_auth_token:
                    error = "TWILIO_AUTH_TOKEN environment variable not set"
                    raise ValueError(error)

                # Create Twilio client
                client = Client(twilio_account_sid, twilio_auth_token)

                # Send SMS
                message = client.messages.create(
                    body=body,
                    from_=from_address,  # This is the from_phone we got earlier
                    to=contact_info
                )

                # Check if successful
                if message.sid:
                    success = True
                    message_id = message.sid
                    delivered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                else:
                    error = "Twilio returned empty message SID"
                    raise Exception(error)

            except Exception as e:
                error = str(e)

    except Exception as e:
        error = str(e)

    # Return result
    return {
        "success": success,
        "message_id": message_id,
        "channel": channel,
        "delivered_at": delivered_at,
        "error": error,
    }


@function_tool(strict_mode=False, name_override="send_notification")
async def _send_notification_tool(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict:
    """Internal function tool for sending notifications."""
    return await send_notification_impl(customer_id, channel, subject, body)


async def send_notification(
    customer_id: str,
    channel: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email or SMS notification to the customer."""
    ctx = _MockToolContext(tool_name="send_notification")
    input_json = json.dumps({
        "customer_id": customer_id,
        "channel": channel,
        "subject": subject,
        "body": body
    })
    return await _send_notification_tool.on_invoke_tool(ctx, input_json)