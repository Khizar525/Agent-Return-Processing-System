"""
CRM Tools
Owner: Member 3

Fetches customer data from the CRM API.

Interface Spec (do not change signatures without Lead approval):
    get_customer_profile(customer_id: str) -> dict
        Returns:
            {
                "success": bool,
                "customer_id": str,
                "name": str,
                "email": str,
                "phone": str,
                "loyalty_tier": str,       # "bronze" | "silver" | "gold" | "platinum"
                "order_history": list[dict],
                "past_returns": list[dict],
                "fraud_flag": bool,
                "fraud_reason": str | None,
                "error": str | None,
            }

Environment variables required:
    CRM_BASE_URL
    CRM_API_KEY
"""

import os
import logging
import time

import httpx
from agents import function_tool

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0


def _format_profile(data: dict) -> dict:
    orders = data.get("orders") or []
    returns = data.get("returns") or []

    return {
        "success": True,
        "customer_id": data.get("id") or "",
        "name": data.get("name") or "",
        "email": data.get("email") or "",
        "phone": data.get("phone") or "",
        "loyalty_tier": data.get("loyalty_tier") or "bronze",
        "order_history": orders[:10],
        "past_returns": returns[:5],
        "fraud_flag": bool(data.get("fraud_flag", False)),
        "fraud_reason": data.get("fraud_reason"),
        "error": None,
    }


def _error_response(message: str) -> dict:
    return {
        "success": False,
        "customer_id": "",
        "name": "",
        "email": "",
        "phone": "",
        "loyalty_tier": "",
        "order_history": [],
        "past_returns": [],
        "fraud_flag": False,
        "fraud_reason": None,
        "error": message,
    }


@function_tool
async def get_customer_profile(customer_id: str) -> dict:
    """Fetch full customer profile including order history and fraud flags."""
    start = time.monotonic()
    logger.info("tool_call", extra={"tool": "get_customer_profile", "customer_id": customer_id})

    if not customer_id or not customer_id.strip():
        logger.warning(
            "tool_validation_error",
            extra={"tool": "get_customer_profile", "reason": "empty_customer_id"},
        )
        return _error_response("customer_id must not be empty")

    base_url = os.environ.get("CRM_BASE_URL")
    api_key = os.environ.get("CRM_API_KEY")

    if not base_url:
        return _error_response("CRM_BASE_URL environment variable is not set")
    if not api_key:
        return _error_response("CRM_API_KEY environment variable is not set")

    safe_base = base_url.rstrip("/")
    url = f"{safe_base}/customers/{customer_id.strip()}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(url, headers=headers)

        if response.status_code == 404:
            duration = int((time.monotonic() - start) * 1000)
            logger.info(
                "tool_result",
                extra={
                    "tool": "get_customer_profile",
                    "duration_ms": duration,
                    "success": False,
                    "error": "not_found",
                },
            )
            return _error_response(f"Customer not found: {customer_id}")

        response.raise_for_status()

        data = response.json()
        result = _format_profile(data)

        duration = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_result",
            extra={"tool": "get_customer_profile", "duration_ms": duration, "success": True},
        )
        return result

    except httpx.TimeoutException:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_timeout", extra={"tool": "get_customer_profile", "duration_ms": duration}
        )
        return _error_response("CRM API timed out")

    except httpx.HTTPStatusError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_http_error",
            extra={
                "tool": "get_customer_profile",
                "duration_ms": duration,
                "status_code": e.response.status_code,
            },
        )
        return _error_response(f"CRM API returned HTTP {e.response.status_code}")

    except httpx.RequestError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_connection_error", extra={"tool": "get_customer_profile", "duration_ms": duration}
        )
        return _error_response(f"Could not reach CRM API: {str(e)}")

    except (KeyError, TypeError, ValueError) as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_parse_error", extra={"tool": "get_customer_profile", "duration_ms": duration}
        )
        return _error_response(f"Invalid CRM response format: {str(e)}")

    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_unexpected_error", extra={"tool": "get_customer_profile", "duration_ms": duration}
        )
        return _error_response(f"Unexpected CRM API error: {str(e)}")
