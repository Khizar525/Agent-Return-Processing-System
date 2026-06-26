"""
Payment Tools
Owner: Member 3

Processes refunds via Stripe or PayPal.

Interface Spec (do not change signatures without Lead approval):
    process_refund(order_id: str, amount_usd: float, method: str) -> dict
        Args:
            order_id:   the original order identifier
            amount_usd: refund amount in USD (must be <= REFUND_CAP_USD from .env)
            method:     "stripe" | "paypal"
        Returns:
            {
                "success": bool,
                "transaction_id": str,
                "refund_amount": float,
                "currency": str,
                "estimated_days": int,
                "error": str | None,
            }

IMPORTANT: This tool enforces an execution safety boundary (defense-in-depth).
           If amount_usd > REFUND_CAP_USD, it raises a ValueError with
           message "human_approval_required" to prevent execution.

Environment variables required:
    STRIPE_SECRET_KEY
    PAYPAL_CLIENT_ID
    PAYPAL_CLIENT_SECRET
    PAYPAL_BASE_URL
"""

import json
import os
import logging
import time
import math

import httpx
from agents import function_tool

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15.0
_STRIPE_REFUND_URL = "https://api.stripe.com/v1/refunds"

_REFUND_DAYS_ESTIMATE = 5


def _success_response(transaction_id: str, amount: float) -> dict:
    return {
        "success": True,
        "transaction_id": transaction_id,
        "refund_amount": amount,
        "currency": "USD",
        "estimated_days": _REFUND_DAYS_ESTIMATE,
        "error": None,
    }


def _error_response(message: str) -> dict:
    return {
        "success": False,
        "transaction_id": "",
        "refund_amount": 0.0,
        "currency": "USD",
        "estimated_days": 0,
        "error": message,
    }


async def _refund_stripe(order_id: str, amount_usd: float) -> dict:
    secret_key = os.environ.get("STRIPE_SECRET_KEY")
    if not secret_key:
        return _error_response("STRIPE_SECRET_KEY environment variable is not set")

    amount_cents = int(round(amount_usd * 100))
    idempotency_key = f"refund_{order_id}_{amount_cents}_{int(time.time())}"

    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Idempotency-Key": idempotency_key,
    }
    body = {"payment_intent": order_id, "amount": str(amount_cents)}

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.post(_STRIPE_REFUND_URL, headers=headers, data=body)

    if response.status_code == 404:
        return _error_response(f"Payment intent not found: {order_id}")

    response.raise_for_status()
    try:
        data = response.json()
        transaction_id = data["id"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _error_response(f"Invalid Stripe response format: {e}")

    return _success_response(transaction_id, amount_usd)


async def _refund_paypal(order_id: str, amount_usd: float) -> dict:
    client_id = os.environ.get("PAYPAL_CLIENT_ID")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET")
    base_url = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    base_url = base_url.rstrip("/")

    if not client_id or not client_secret:
        return _error_response("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET must be set")

    idempotency_key = f"refund_{order_id}_{int(round(amount_usd * 100))}_{int(time.time())}"

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        token_resp = await client.post(
            f"{base_url}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        token_resp.raise_for_status()
        try:
            access_token = token_resp.json()["access_token"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            return _error_response(f"Invalid PayPal token response format: {e}")

        refund_resp = await client.post(
            f"{base_url}/v2/payments/captures/{order_id}/refund",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": idempotency_key,
            },
            json={
                "amount": {
                    "value": f"{amount_usd:.2f}",
                    "currency_code": "USD",
                },
            },
        )

    if refund_resp.status_code == 404:
        return _error_response(f"Capture not found: {order_id}")

    refund_resp.raise_for_status()
    try:
        data = refund_resp.json()
        transaction_id = data["id"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return _error_response(f"Invalid PayPal refund response format: {e}")

    return _success_response(transaction_id, amount_usd)


@function_tool
async def process_refund(order_id: str, amount_usd: float, method: str) -> dict:
    """Issue a refund to the customer's original payment method."""
    start = time.monotonic()
    logger.info(
        "tool_call",
        extra={
            "tool": "process_refund",
            "order_id": order_id,
            "amount_usd": amount_usd,
            "method": method,
        },
    )

    if not order_id or not order_id.strip():
        logger.warning(
            "tool_validation_error", extra={"tool": "process_refund", "reason": "empty_order_id"}
        )
        return _error_response("order_id must not be empty")

    if not isinstance(method, str) or not method.strip():
        return _error_response("method must be a non-empty string")

    normalised_method = method.strip().lower()
    if normalised_method not in ("stripe", "paypal"):
        return _error_response(
            f"Unsupported payment method: '{method}'. Must be 'stripe' or 'paypal'."
        )

    if not isinstance(amount_usd, (int, float)) or not math.isfinite(amount_usd):
        return _error_response("amount_usd must be a finite number")

    if amount_usd <= 0:
        return _error_response("amount_usd must be greater than 0")

    # Safely parse REFUND_CAP_USD, fall back to default if unset
    try:
        refund_cap = float(os.environ.get("REFUND_CAP_USD", "500"))
    except (ValueError, TypeError):
        logger.error(
            "tool_config_error", extra={"tool": "process_refund", "reason": "invalid_refund_cap"}
        )
        return _error_response("REFUND_CAP_USD environment variable must be a valid number")

    # ── Adapter Execution Safety Boundary (Defense in Depth) ───────────
    # The ResolutionAgent is the primary decision-maker and must autonomously
    # block refunds > $500. The refund_cap_guardrail is the primary enforcement
    # layer. This check is a low-level adapter safeguard to prevent execution of
    # unauthorized amounts in case of agent hallucination.
    if amount_usd > refund_cap:
        logger.error(
            "tool_safety_block",
            extra={
                "tool": "process_refund",
                "amount_usd": amount_usd,
                "refund_cap": refund_cap,
                "reason": "Execution blocked by adapter safety boundary.",
            },
        )
        raise ValueError("human_approval_required")

    # ── Execute refund ──────────────────────────────────────────────────
    try:
        if normalised_method == "stripe":
            result = await _refund_stripe(order_id.strip(), amount_usd)
        else:
            result = await _refund_paypal(order_id.strip(), amount_usd)

        duration = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_result",
            extra={
                "tool": "process_refund",
                "duration_ms": duration,
                "success": result["success"],
                "method": normalised_method,
                "transaction_id": result.get("transaction_id", ""),
            },
        )
        return result

    except httpx.TimeoutException:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_timeout",
            extra={"tool": "process_refund", "duration_ms": duration, "method": normalised_method},
        )
        return _error_response(f"{normalised_method.title()} refund API timed out")

    except httpx.HTTPStatusError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_http_error",
            extra={
                "tool": "process_refund",
                "duration_ms": duration,
                "method": normalised_method,
                "status_code": e.response.status_code,
            },
        )
        return _error_response(
            f"{normalised_method.title()} API returned HTTP {e.response.status_code}"
        )

    except httpx.RequestError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_connection_error",
            extra={"tool": "process_refund", "duration_ms": duration, "method": normalised_method},
        )
        return _error_response(f"Could not reach {normalised_method.title()} API: {str(e)}")

    except (KeyError, TypeError) as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_parse_error",
            extra={"tool": "process_refund", "duration_ms": duration, "method": normalised_method},
        )
        return _error_response(f"Invalid {normalised_method.title()} response format: {str(e)}")

    except ValueError as e:
        # Guardrail ValueError (human_approval_required) must propagate
        # unmodified to the SDK runtime. Other ValueErrors are unexpected
        # and treated as tool errors.
        if "human_approval_required" in str(e):
            raise
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_unexpected_error",
            extra={"tool": "process_refund", "duration_ms": duration, "method": normalised_method},
        )
        return _error_response(f"Unexpected {normalised_method.title()} API error: {str(e)}")

    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_unexpected_error",
            extra={"tool": "process_refund", "duration_ms": duration, "method": normalised_method},
        )
        return _error_response(f"Unexpected {normalised_method.title()} API error: {str(e)}")
