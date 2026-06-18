"""
Notification Tools
Owner: Member 4

Sends customer-facing messages via SendGrid (email) or Twilio (SMS).

Interface Spec (do not change signatures without Lead approval):

    send_notification(notification_type: str, recipient: str, subject: str, body: str) -> dict
        Args:
            notification_type: "email" or "sms"
            recipient: email address (for email) or phone number (for sms)
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
"""

import os
import datetime
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


async def send_notification_impl(
    notification_type: str,
    recipient: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email or SMS notification to the recipient."""
    # Initialize return values
    message_id = None
    channel = notification_type
    delivered_at = None
    error = None
    success = False

    # Validate notification_type
    if notification_type not in ["email", "sms"]:
        error = f"Invalid notification_type: {notification_type}. Must be 'email' or 'sms'"
        return {
            "success": False,
            "message_id": message_id,
            "channel": channel,
            "delivered_at": delivered_at,
            "error": error,
        }

    # Handle email notifications
    if notification_type == "email":
        if not SENDGRID_AVAILABLE:
            error = "SendGrid library not installed"
            # Fallback to SMS if Twilio is available
            if TWILIO_AVAILABLE:
                notification_type = "sms"
                channel = "sms"
            else:
                return {
                    "success": False,
                    "message_id": message_id,
                    "channel": channel,
                    "delivered_at": delivered_at,
                    "error": error,
                }
            # If we're falling through to SMS, we'll try to send via Twilio below
        else:
            try:
                # Get environment variables
                sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
                from_email = os.environ.get('SENDGRID_FROM_EMAIL')

                if not sendgrid_api_key:
                    error = "SENDGRID_API_KEY environment variable not set"
                    raise ValueError(error)
                if not from_email:
                    error = "FROM_EMAIL environment variable not set"
                    raise ValueError(error)

                # Create SendGrid client
                sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)

                # Create email
                mail = Mail(
                    from_email=from_email,
                    to_emails=recipient,
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
                    notification_type = "sms"
                    channel = "sms"
                    # Reset variables for SMS attempt
                    message_id = None
                    delivered_at = None
                    error = None
                    success = False
                else:
                    return {
                        "success": False,
                        "message_id": message_id,
                        "channel": channel,
                        "delivered_at": delivered_at,
                        "error": error,
                    }

    # Handle SMS notifications (either primary or fallback from email)
    if notification_type == "sms":
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
            twilio_from_number = os.environ.get('TWILIO_FROM_NUMBER')

            if not twilio_account_sid:
                error = "TWILIO_ACCOUNT_SID environment variable not set"
                raise ValueError(error)
            if not twilio_auth_token:
                error = "TWILIO_AUTH_TOKEN environment variable not set"
                raise ValueError(error)
            if not twilio_from_number:
                error = "TWILIO_FROM_NUMBER environment variable not set"
                raise ValueError(error)

            # Create Twilio client
            client = Client(twilio_account_sid, twilio_auth_token)

            # Send SMS
            message = client.messages.create(
                body=body,
                from_=twilio_from_number,
                to=recipient
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

    # Return result
    return {
        "success": success,
        "message_id": message_id,
        "channel": channel,
        "delivered_at": delivered_at,
        "error": error,
    }


@function_tool
async def send_notification(
    notification_type: str,
    recipient: str,
    subject: str,
    body: str,
) -> dict:
    """Send an email or SMS notification to the recipient."""
    return await send_notification_impl(notification_type, recipient, subject, body)