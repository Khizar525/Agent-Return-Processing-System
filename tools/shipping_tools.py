"""
Shipping Tools
Owner: Member 3

Generates prepaid return labels and creates replacement orders.

Interface Spec (do not change signatures without Lead approval):

    create_return_label(order_id: str, carrier: str) -> dict
        Args:
            order_id: the original order identifier
            carrier:  "fedex" | "ups"
        Returns:
            {
                "success": bool,
                "label_url": str,
                "tracking_number": str,
                "carrier": str,
                "expires_at": str,   # ISO-8601
                "error": str | None,
            }

    create_replacement_order(order_id: str) -> dict
        Args:
            order_id: the original order to clone
        Returns:
            {
                "success": bool,
                "replacement_order_id": str,
                "expedited": bool,
                "estimated_delivery": str,   # ISO-8601
                "error": str | None,
            }

Environment variables required:
    FEDEX_API_KEY, FEDEX_API_SECRET, FEDEX_ACCOUNT_NUMBER
    UPS_CLIENT_ID, UPS_CLIENT_SECRET
    OMS_BASE_URL, OMS_API_KEY
"""

import os
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx
from agents import function_tool

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 15.0

_VALID_CARRIERS = ("fedex", "ups")

_FEDEX_AUTH_URL = "https://api.fedex.com/auth/oauth/v2/token"
_FEDEX_SHIP_URL = "https://api.fedex.com/ship/v1/shipments"

_UPS_AUTH_URL = "https://onlinetools.ups.com/security/v1/oauth/token"
_UPS_SHIP_URL = "https://onlinetools.ups.com/api/shipments/v1/label"

_LABEL_EXPIRY_DAYS = 30


def _label_error_response(carrier: str, message: str) -> dict:
    return {
        "success": False,
        "label_url": "",
        "tracking_number": "",
        "carrier": carrier,
        "expires_at": "",
        "error": message,
    }


def _replacement_error_response(message: str) -> dict:
    return {
        "success": False,
        "replacement_order_id": "",
        "expedited": False,
        "estimated_delivery": "",
        "error": message,
    }


async def _get_fedex_token(client: httpx.AsyncClient) -> str:
    api_key = os.environ.get("FEDEX_API_KEY")
    api_secret = os.environ.get("FEDEX_API_SECRET")

    if not api_key or not api_secret:
        raise ValueError("FEDEX_API_KEY and FEDEX_API_SECRET must be set")

    resp = await client.post(
        _FEDEX_AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": api_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def _create_fedex_label(order_id: str, carrier: str) -> dict:
    api_key = os.environ.get("FEDEX_API_KEY")
    api_secret = os.environ.get("FEDEX_API_SECRET")
    account_number = os.environ.get("FEDEX_ACCOUNT_NUMBER")

    if not api_key or not api_secret or not account_number:
        return _label_error_response(
            carrier, "FEDEX_API_KEY, FEDEX_API_SECRET, and FEDEX_ACCOUNT_NUMBER must be set"
        )

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        token = await _get_fedex_token(client)

        payload = {
            "accountNumber": {"value": account_number},
            "requestedShipment": {
                "shipmentSpecialServiceType": "RETURN_SHIPMENT",
                "origin": {"reference": order_id},
            },
        }

        resp = await client.post(
            _FEDEX_SHIP_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-AccountNumber": account_number,
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        shipments = data["output"]["transactionShipments"]
        label_url = shipments[0]["shipmentDocuments"][0]["url"]
        tracking_number = shipments[0]["masterTrackingNumber"]

    expires_at = (datetime.now(timezone.utc) + timedelta(days=_LABEL_EXPIRY_DAYS)).isoformat()

    return {
        "success": True,
        "label_url": label_url,
        "tracking_number": tracking_number,
        "carrier": carrier,
        "expires_at": expires_at,
        "error": None,
    }


async def _create_ups_label(order_id: str, carrier: str) -> dict:
    client_id = os.environ.get("UPS_CLIENT_ID")
    client_secret = os.environ.get("UPS_CLIENT_SECRET")

    if not client_id or not client_secret:
        return _label_error_response(carrier, "UPS_CLIENT_ID and UPS_CLIENT_SECRET must be set")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        token_resp = await client.post(
            _UPS_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]

        payload = {
            "labelSpecification": {
                "labelStockSize": {"height": "4", "width": "6"},
                "labelFormat": {"code": "GIF"},
            },
            "referenceNumber": {"value": order_id},
        }

        resp = await client.post(
            _UPS_SHIP_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "transId": "return_label",
                "transactionSrc": "agent-nemo",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        label_url = data["labelUrl"]
        tracking_number = data["trackingNumber"]

    expires_at = (datetime.now(timezone.utc) + timedelta(days=_LABEL_EXPIRY_DAYS)).isoformat()

    return {
        "success": True,
        "label_url": label_url,
        "tracking_number": tracking_number,
        "carrier": carrier,
        "expires_at": expires_at,
        "error": None,
    }


@function_tool
async def create_return_label(order_id: str, carrier: str) -> dict:
    """Generate a prepaid return shipping label via FedEx or UPS."""
    start = time.monotonic()
    logger.info(
        "tool_call", extra={"tool": "create_return_label", "order_id": order_id, "carrier": carrier}
    )

    if not order_id or not order_id.strip():
        logger.warning(
            "tool_validation_error",
            extra={"tool": "create_return_label", "reason": "empty_order_id"},
        )
        return _label_error_response(carrier, "order_id must not be empty")

    if not isinstance(carrier, str) or not carrier.strip():
        logger.warning(
            "tool_validation_error",
            extra={
                "tool": "create_return_label",
                "reason": "invalid_carrier_type",
                "provided": type(carrier).__name__,
            },
        )
        return _label_error_response(
            str(carrier) if carrier is not None else "", "carrier must be a non-empty string"
        )

    normalised = carrier.strip().lower()
    if normalised not in _VALID_CARRIERS:
        logger.warning(
            "tool_validation_error",
            extra={"tool": "create_return_label", "reason": "invalid_carrier", "provided": carrier},
        )
        return _label_error_response(
            carrier, f"Unsupported carrier: '{carrier}'. Must be 'fedex' or 'ups'."
        )

    try:
        if normalised == "fedex":
            result = await _create_fedex_label(order_id.strip(), normalised)
        else:
            result = await _create_ups_label(order_id.strip(), normalised)

        duration = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_result",
            extra={
                "tool": "create_return_label",
                "duration_ms": duration,
                "success": result["success"],
                "carrier": normalised,
            },
        )
        return result

    except httpx.TimeoutException:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_timeout",
            extra={"tool": "create_return_label", "duration_ms": duration, "carrier": normalised},
        )
        return _label_error_response(normalised, f"{normalised.title()} API timed out")

    except httpx.HTTPStatusError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_http_error",
            extra={
                "tool": "create_return_label",
                "duration_ms": duration,
                "carrier": normalised,
                "status_code": e.response.status_code,
            },
        )
        return _label_error_response(
            normalised, f"{normalised.title()} API returned HTTP {e.response.status_code}"
        )

    except httpx.RequestError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_connection_error",
            extra={"tool": "create_return_label", "duration_ms": duration, "carrier": normalised},
        )
        return _label_error_response(
            normalised, f"Could not reach {normalised.title()} API: {str(e)}"
        )

    except (KeyError, TypeError) as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_parse_error",
            extra={"tool": "create_return_label", "duration_ms": duration, "carrier": normalised},
        )
        return _label_error_response(
            normalised, f"Invalid {normalised.title()} response format: {str(e)}"
        )

    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_unexpected_error",
            extra={"tool": "create_return_label", "duration_ms": duration, "carrier": normalised},
        )
        return _label_error_response(
            normalised, f"Unexpected {normalised.title()} API error: {str(e)}"
        )


@function_tool
async def create_replacement_order(order_id: str) -> dict:
    """Clone an order and flag it for expedited fulfillment in the OMS."""
    start = time.monotonic()
    logger.info("tool_call", extra={"tool": "create_replacement_order", "order_id": order_id})

    if not order_id or not order_id.strip():
        logger.warning(
            "tool_validation_error",
            extra={"tool": "create_replacement_order", "reason": "empty_order_id"},
        )
        return _replacement_error_response("order_id must not be empty")

    oms_base = os.environ.get("OMS_BASE_URL")
    oms_api_key = os.environ.get("OMS_API_KEY")

    if not oms_base:
        return _replacement_error_response("OMS_BASE_URL environment variable is not set")
    if not oms_api_key:
        return _replacement_error_response("OMS_API_KEY environment variable is not set")

    safe_base = oms_base.rstrip("/")
    url = f"{safe_base}/orders/{order_id.strip()}/replicate"
    headers = {
        "Authorization": f"Bearer {oms_api_key}",
        "Content-Type": "application/json",
    }
    body = {"expedited": True}

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=body)

        if response.status_code == 404:
            duration = int((time.monotonic() - start) * 1000)
            logger.info(
                "tool_result",
                extra={
                    "tool": "create_replacement_order",
                    "duration_ms": duration,
                    "success": False,
                    "error": "not_found",
                },
            )
            return _replacement_error_response(f"Order not found: {order_id}")

        response.raise_for_status()

        data = response.json()

        result = {
            "success": True,
            "replacement_order_id": data.get("order_id") or data.get("replacement_order_id", ""),
            "expedited": bool(data.get("expedited", True)),
            "estimated_delivery": data.get("estimated_delivery", ""),
            "error": None,
        }

        duration = int((time.monotonic() - start) * 1000)
        logger.info(
            "tool_result",
            extra={
                "tool": "create_replacement_order",
                "duration_ms": duration,
                "success": True,
                "replacement_order_id": result["replacement_order_id"],
            },
        )
        return result

    except httpx.TimeoutException:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_timeout", extra={"tool": "create_replacement_order", "duration_ms": duration}
        )
        return _replacement_error_response("OMS API timed out")

    except httpx.HTTPStatusError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_http_error",
            extra={
                "tool": "create_replacement_order",
                "duration_ms": duration,
                "status_code": e.response.status_code,
            },
        )
        return _replacement_error_response(f"OMS API returned HTTP {e.response.status_code}")

    except httpx.RequestError as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_connection_error",
            extra={"tool": "create_replacement_order", "duration_ms": duration},
        )
        return _replacement_error_response(f"Could not reach OMS API: {str(e)}")

    except (KeyError, TypeError) as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_parse_error", extra={"tool": "create_replacement_order", "duration_ms": duration}
        )
        return _replacement_error_response(f"Invalid OMS response format: {str(e)}")

    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        logger.error(
            "tool_unexpected_error",
            extra={"tool": "create_replacement_order", "duration_ms": duration},
        )
        return _replacement_error_response(f"Unexpected OMS API error: {str(e)}")
