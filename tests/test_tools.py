"""
Tool Integration Unit Tests
Owner: Member 3

Use mock API responses — do not make real API calls in tests.
Use respx to mock httpx requests.

Run:
    pytest tests/test_tools.py -v
"""

import json
import os
import sys
import site

# Ensure site-packages takes priority over the local agents/ package
# so the openai-agents SDK's `agents` module is found first.
site_packages = [p for p in site.getsitepackages() if "site-packages" in p]
for sp in site_packages:
    if sp in sys.path:
        sys.path.remove(sp)
        sys.path.insert(0, sp)

import httpx
import pytest
import respx

from agents.tool import ToolContext
from tools.crm_tools import get_customer_profile
from tools.shipping_tools import (
    create_return_label,
    create_replacement_order,
    _FEDEX_AUTH_URL,
    _FEDEX_SHIP_URL,
    _UPS_AUTH_URL,
    _UPS_SHIP_URL,
)
from tools.payment_tools import process_refund


async def _invoke_tool(customer_id: str) -> dict:
    """Invoke get_customer_profile through the FunctionTool wrapper."""
    args = json.dumps({"customer_id": customer_id})
    ctx = ToolContext(
        context=None,
        tool_name="get_customer_profile",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await get_customer_profile.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        return json.loads(result)
    return result

_CRM_BASE = "https://api.crm.example.com/v1"
_CRM_KEY = "test-api-key-abc123"


# ---------------------------------------------------------------------------
# get_customer_profile tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_customer_profile_returns_expected_schema():
    """A successful CRM response returns the full profile schema with correct values."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    payload = {
        "id": "cust_001",
        "name": "Jane Smith",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "loyalty_tier": "gold",
        "orders": [
            {
                "order_id": "ORD-12345",
                "total": 89.99,
                "payment_method": "stripe",
                "shipping_carrier": "fedex",
                "item_category": "electronics",
                "status": "delivered",
                "purchased_at": "2026-05-01T10:00:00Z",
                "delivered_at": "2026-05-05T14:30:00Z",
            },
        ],
        "returns": [],
        "fraud_flag": False,
    }

    async with respx.mock:
        respx.get(f"{_CRM_BASE}/customers/cust_001").respond(
            json=payload, status_code=200,
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is True
    assert result["customer_id"] == "cust_001"
    assert result["name"] == "Jane Smith"
    assert result["email"] == "jane@example.com"
    assert result["phone"] == "+1234567890"
    assert result["loyalty_tier"] == "gold"
    assert len(result["order_history"]) == 1
    assert result["order_history"][0]["order_id"] == "ORD-12345"
    assert result["order_history"][0]["total"] == 89.99
    assert result["past_returns"] == []
    assert result["fraud_flag"] is False
    assert result["fraud_reason"] is None
    assert result["error"] is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_empty_customer_id():
    """An empty customer_id returns an error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        result = await _invoke_tool(customer_id="")

    assert result["success"] is False
    assert result["error"] == "customer_id must not be empty"
    assert result["customer_id"] == ""
    assert result["order_history"] == []

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_whitespace_customer_id():
    """A whitespace-only customer_id returns an error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        result = await _invoke_tool(customer_id="   ")

    assert result["success"] is False
    assert result["error"] == "customer_id must not be empty"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_handles_unknown_customer():
    """CRM returning 404 produces a descriptive error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        respx.get(f"{_CRM_BASE}/customers/unknown_99").respond(
            status_code=404,
        )

        result = await _invoke_tool(customer_id="unknown_99")

    assert result["success"] is False
    assert result["error"] == "Customer not found: unknown_99"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_crm_timeout():
    """A CRM timeout produces a timed-out error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        route = respx.get(f"{_CRM_BASE}/customers/cust_001")
        route.side_effect = httpx.TimeoutException(
            "Connection timed out after 10s",
            request=httpx.Request("GET", f"{_CRM_BASE}/customers/cust_001"),
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is False
    assert result["error"] == "CRM API timed out"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_connection_failure():
    """A network-level failure produces a connection error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        route = respx.get(f"{_CRM_BASE}/customers/cust_001")
        route.side_effect = httpx.RequestError(
            "Name or service not known",
            request=httpx.Request("GET", f"{_CRM_BASE}/customers/cust_001"),
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is False
    assert "Could not reach CRM API" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_malformed_response():
    """A non-JSON CRM response produces a parse error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        respx.get(f"{_CRM_BASE}/customers/cust_001").respond(
            status_code=200,
            text="Internal Server Error — not JSON",
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is False
    assert "Invalid CRM response format" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_missing_base_url():
    """Missing CRM_BASE_URL produces an env var error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("CRM_BASE_URL", raising=False)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    async with respx.mock:
        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is False
    assert result["error"] == "CRM_BASE_URL environment variable is not set"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_missing_api_key():
    """Missing CRM_API_KEY produces an env var error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.delenv("CRM_API_KEY", raising=False)

    async with respx.mock:
        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is False
    assert result["error"] == "CRM_API_KEY environment variable is not set"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_order_history_limited_to_10():
    """order_history is truncated to the most recent 10 orders."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    orders = [
        {"order_id": f"ORD-{i:05d}", "total": float(i * 10)}
        for i in range(15)
    ]
    payload = {
        "id": "cust_001",
        "name": "Jane",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "loyalty_tier": "bronze",
        "orders": orders,
        "returns": [],
        "fraud_flag": False,
    }

    async with respx.mock:
        respx.get(f"{_CRM_BASE}/customers/cust_001").respond(
            json=payload, status_code=200,
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is True
    assert len(result["order_history"]) == 10
    assert result["order_history"][0]["order_id"] == "ORD-00000"
    assert result["order_history"][9]["order_id"] == "ORD-00009"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_get_customer_profile_past_returns_limited_to_5():
    """past_returns is truncated to the most recent 5 returns."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("CRM_BASE_URL", _CRM_BASE)
    monkeypatch.setenv("CRM_API_KEY", _CRM_KEY)

    returns = [
        {"return_id": f"RET-{i:03d}", "status": "completed"}
        for i in range(8)
    ]
    payload = {
        "id": "cust_001",
        "name": "Jane",
        "email": "jane@example.com",
        "phone": "+1234567890",
        "loyalty_tier": "silver",
        "orders": [],
        "returns": returns,
        "fraud_flag": True,
        "fraud_reason": "suspicious_activity",
    }

    async with respx.mock:
        respx.get(f"{_CRM_BASE}/customers/cust_001").respond(
            json=payload, status_code=200,
        )

        result = await _invoke_tool(customer_id="cust_001")

    assert result["success"] is True
    assert len(result["past_returns"]) == 5
    assert result["fraud_flag"] is True
    assert result["fraud_reason"] == "suspicious_activity"

    monkeypatch.undo()


# ---------------------------------------------------------------------------
# process_refund tests
# ---------------------------------------------------------------------------

_STRIPE_REFUND_URL = "https://api.stripe.com/v1/refunds"


async def _invoke_process_refund(order_id: str, amount_usd: float, method: str) -> dict:
    """Invoke process_refund through the FunctionTool wrapper.

    Returns a dict on success. On error, the SDK may return a non-JSON
    error string (for schema validation or raised ValueError) — convert
    those to a raised ValueError so tests can assert the guardrail.
    """
    args = json.dumps({"order_id": order_id, "amount_usd": amount_usd, "method": method})
    ctx = ToolContext(
        context=None,
        tool_name="process_refund",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await process_refund.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError):
            raise ValueError(result)
    return result


@pytest.mark.asyncio
async def test_process_refund_stripe_success():
    """Stripe refund returns transaction_id with full schema."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post(_STRIPE_REFUND_URL).respond(
            json={"id": "re_stripe_12345"}, status_code=200,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is True
    assert result["transaction_id"] == "re_stripe_12345"
    assert result["refund_amount"] == 50.0
    assert result["currency"] == "USD"
    assert result["estimated_days"] == 5
    assert result["error"] is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_paypal_success():
    """PayPal refund returns transaction_id with full schema."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "paypal_client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "paypal_secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post("https://api.sandbox.paypal.com/v1/oauth2/token").respond(
            json={"access_token": "paypal_token_abc"}, status_code=200,
        )
        respx.post(
            "https://api.sandbox.paypal.com/v2/payments/captures/ORD-001/refund"
        ).respond(
            json={"id": "re_paypal_67890"}, status_code=200,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=25.0, method="paypal")

    assert result["success"] is True
    assert result["transaction_id"] == "re_paypal_67890"
    assert result["refund_amount"] == 25.0
    assert result["currency"] == "USD"
    assert result["estimated_days"] == 5
    assert result["error"] is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_unsupported_method():
    """An unsupported payment method returns an error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="bitcoin")

    assert result["success"] is False
    assert "Unsupported payment method" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_empty_order_id():
    """An empty order_id returns an error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert result["error"] == "order_id must not be empty"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_invalid_amount():
    """A non-numeric amount_usd returns a validation error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        with pytest.raises(ValueError):
            await _invoke_process_refund(
                order_id="ORD-001", amount_usd="not-a-number", method="stripe")

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_negative_amount():
    """A negative amount_usd returns a validation error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=-50.0, method="stripe")

    assert result["success"] is False
    assert result["error"] == "amount_usd must be greater than 0"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_missing_stripe_key():
    """Missing STRIPE_SECRET_KEY returns an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert result["error"] == "STRIPE_SECRET_KEY environment variable is not set"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_missing_paypal_credentials():
    """Missing PayPal credentials returns an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "500")
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="paypal")

    assert result["success"] is False
    assert "PAYPAL_CLIENT_ID" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_stripe_timeout():
    """Stripe API timeout produces a timeout error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        route = respx.post(_STRIPE_REFUND_URL)
        route.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request("POST", _STRIPE_REFUND_URL),
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert "Stripe refund API timed out" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_paypal_timeout():
    """PayPal API timeout produces a timeout error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "paypal_client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "paypal_secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        token_route = respx.post("https://api.sandbox.paypal.com/v1/oauth2/token")
        token_route.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request(
                "POST", "https://api.sandbox.paypal.com/v1/oauth2/token"),
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=25.0, method="paypal")

    assert result["success"] is False
    assert "Paypal refund API timed out" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_stripe_malformed_response():
    """Non-JSON Stripe response returns an error response (was ValueError)."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post(_STRIPE_REFUND_URL).respond(
            text="not-json", status_code=200,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert "Invalid Stripe response format" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_paypal_malformed_response():
    """Non-JSON PayPal refund response returns an error response (was ValueError)."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "paypal_client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "paypal_secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post("https://api.sandbox.paypal.com/v1/oauth2/token").respond(
            json={"access_token": "paypal_token_abc"}, status_code=200,
        )
        respx.post(
            "https://api.sandbox.paypal.com/v2/payments/captures/ORD-001/refund"
        ).respond(
            text="not-json", status_code=200,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=25.0, method="paypal")

    assert result["success"] is False
    assert "Invalid PayPal refund response format" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_stripe_404():
    """Stripe returning 404 produces a payment intent not found error."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post(_STRIPE_REFUND_URL).respond(
            status_code=404,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert result["error"] == "Payment intent not found: ORD-001"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_paypal_404():
    """PayPal returning 404 produces a capture not found error."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "paypal_client")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "paypal_secret")
    monkeypatch.setenv("PAYPAL_BASE_URL", "https://api.sandbox.paypal.com")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post("https://api.sandbox.paypal.com/v1/oauth2/token").respond(
            json={"access_token": "paypal_token_abc"}, status_code=200,
        )
        respx.post(
            "https://api.sandbox.paypal.com/v2/payments/captures/ORD-001/refund"
        ).respond(
            status_code=404,
        )
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=25.0, method="paypal")

    assert result["success"] is False
    assert result["error"] == "Capture not found: ORD-001"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_malformed_refund_cap():
    """Malformed REFUND_CAP_USD returns an env error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "abc")

    async with respx.mock:
        result = await _invoke_process_refund(
            order_id="ORD-001", amount_usd=50.0, method="stripe")

    assert result["success"] is False
    assert result["error"] == (
        "REFUND_CAP_USD environment variable must be a valid number")

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_blocks_above_cap():
    """Amount exceeding REFUND_CAP_USD raises ValueError without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("REFUND_CAP_USD", "100")

    async with respx.mock:
        with pytest.raises(ValueError, match="human_approval_required"):
            await _invoke_process_refund(
                order_id="ORD-001", amount_usd=200.0, method="stripe")

    monkeypatch.undo()


# ---------------------------------------------------------------------------
# create_return_label tests
# ---------------------------------------------------------------------------


async def _invoke_create_return_label(order_id: str, carrier: str) -> dict:
    """Invoke create_return_label through the FunctionTool wrapper."""
    args = json.dumps({"order_id": order_id, "carrier": carrier})
    ctx = ToolContext(
        context=None,
        tool_name="create_return_label",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await create_return_label.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        return json.loads(result)
    return result


async def _invoke_create_replacement_order(order_id: str) -> dict:
    """Invoke create_replacement_order through the FunctionTool wrapper."""
    args = json.dumps({"order_id": order_id})
    ctx = ToolContext(
        context=None,
        tool_name="create_replacement_order",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await create_replacement_order.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        return json.loads(result)
    return result


@pytest.mark.asyncio
async def test_create_return_label_fedex_success():
    """FedEx label generation returns label URL, tracking number, and carrier."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FEDEX_API_KEY", "fedex_key")
    monkeypatch.setenv("FEDEX_API_SECRET", "fedex_secret")
    monkeypatch.setenv("FEDEX_ACCOUNT_NUMBER", "123456789")

    async with respx.mock:
        respx.post(_FEDEX_AUTH_URL).respond(
            json={"access_token": "test_fedex_token"}, status_code=200)
        respx.post(_FEDEX_SHIP_URL).respond(
            json={
                "output": {
                    "transactionShipments": [
                        {
                            "shipmentDocuments": [
                                {"url": "https://fedex.com/label/abc.pdf"}
                            ],
                            "masterTrackingNumber": "FDX1234567890",
                        }
                    ]
                }
            },
            status_code=200,
        )

        result = await _invoke_create_return_label(order_id="ORD-001", carrier="fedex")

    assert result["success"] is True
    assert result["label_url"] == "https://fedex.com/label/abc.pdf"
    assert result["tracking_number"] == "FDX1234567890"
    assert result["carrier"] == "fedex"
    assert result["error"] is None
    assert "expires_at" in result
    assert result["expires_at"] != ""

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_ups_success():
    """UPS label generation returns label URL, tracking number, and carrier."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("UPS_CLIENT_ID", "ups_client")
    monkeypatch.setenv("UPS_CLIENT_SECRET", "ups_secret")

    async with respx.mock:
        respx.post(_UPS_AUTH_URL).respond(
            json={"access_token": "test_ups_token"}, status_code=200)
        respx.post(_UPS_SHIP_URL).respond(
            json={
                "labelUrl": "https://ups.com/label/xyz.gif",
                "trackingNumber": "1Z999AA10123456784",
            },
            status_code=200,
        )

        result = await _invoke_create_return_label(order_id="ORD-002", carrier="ups")

    assert result["success"] is True
    assert result["label_url"] == "https://ups.com/label/xyz.gif"
    assert result["tracking_number"] == "1Z999AA10123456784"
    assert result["carrier"] == "ups"
    assert result["error"] is None
    assert "expires_at" in result
    assert result["expires_at"] != ""

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_invalid_carrier():
    """An unsupported carrier returns an error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FEDEX_API_KEY", "fedex_key")
    monkeypatch.setenv("FEDEX_API_SECRET", "fedex_secret")
    monkeypatch.setenv("FEDEX_ACCOUNT_NUMBER", "123456789")

    async with respx.mock:
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="dhl")

    assert result["success"] is False
    assert "Unsupported carrier" in result["error"]
    assert result["carrier"] == "dhl"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_empty_order_id():
    """An empty order_id returns an error without making any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FEDEX_API_KEY", "fedex_key")
    monkeypatch.setenv("FEDEX_API_SECRET", "fedex_secret")
    monkeypatch.setenv("FEDEX_ACCOUNT_NUMBER", "123456789")

    async with respx.mock:
        result = await _invoke_create_return_label(order_id="", carrier="fedex")

    assert result["success"] is False
    assert result["error"] == "order_id must not be empty"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_missing_fedex_env():
    """Missing FedEx env vars produce an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("FEDEX_API_KEY", raising=False)
    monkeypatch.delenv("FEDEX_API_SECRET", raising=False)
    monkeypatch.delenv("FEDEX_ACCOUNT_NUMBER", raising=False)

    async with respx.mock:
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="fedex")

    assert result["success"] is False
    assert "FEDEX_API_KEY" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_missing_ups_env():
    """Missing UPS env vars produce an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("UPS_CLIENT_ID", raising=False)
    monkeypatch.delenv("UPS_CLIENT_SECRET", raising=False)

    async with respx.mock:
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="ups")

    assert result["success"] is False
    assert "UPS_CLIENT_ID" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_fedex_timeout():
    """FedEx API timeout produces a timeout error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FEDEX_API_KEY", "fedex_key")
    monkeypatch.setenv("FEDEX_API_SECRET", "fedex_secret")
    monkeypatch.setenv("FEDEX_ACCOUNT_NUMBER", "123456789")

    async with respx.mock:
        auth_route = respx.post(_FEDEX_AUTH_URL)
        auth_route.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request("POST", _FEDEX_AUTH_URL),
        )
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="fedex")

    assert result["success"] is False
    assert result["error"] == "Fedex API timed out"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_ups_timeout():
    """UPS API timeout produces a timeout error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("UPS_CLIENT_ID", "ups_client")
    monkeypatch.setenv("UPS_CLIENT_SECRET", "ups_secret")

    async with respx.mock:
        auth_route = respx.post(_UPS_AUTH_URL)
        auth_route.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request("POST", _UPS_AUTH_URL),
        )
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="ups")

    assert result["success"] is False
    assert result["error"] == "Ups API timed out"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_fedex_malformed_response():
    """Non-JSON FedEx response produces an unexpected error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FEDEX_API_KEY", "fedex_key")
    monkeypatch.setenv("FEDEX_API_SECRET", "fedex_secret")
    monkeypatch.setenv("FEDEX_ACCOUNT_NUMBER", "123456789")

    async with respx.mock:
        respx.post(_FEDEX_AUTH_URL).respond(
            json={"access_token": "test_fedex_token"}, status_code=200)
        respx.post(_FEDEX_SHIP_URL).respond(
            text="not-json", status_code=200)

        result = await _invoke_create_return_label(order_id="ORD-001", carrier="fedex")

    assert result["success"] is False
    assert "Unexpected Fedex" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_return_label_ups_malformed_response():
    """UPS response missing keys produces a parse error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("UPS_CLIENT_ID", "ups_client")
    monkeypatch.setenv("UPS_CLIENT_SECRET", "ups_secret")

    async with respx.mock:
        respx.post(_UPS_AUTH_URL).respond(
            json={"access_token": "test_ups_token"}, status_code=200)
        respx.post(_UPS_SHIP_URL).respond(
            json={"labelUrl": "https://ups.com/label/xyz.gif"},
            status_code=200,
        )
        result = await _invoke_create_return_label(order_id="ORD-001", carrier="ups")

    assert result["success"] is False
    assert "Invalid Ups response format" in result["error"]

    monkeypatch.undo()


# ---------------------------------------------------------------------------
# create_replacement_order tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_replacement_order_success():
    """A successful OMS call returns the replacement order with expedited flag."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        respx.post("https://oms.example.com/orders/ORD-001/replicate").respond(
            json={
                "order_id": "REP-001",
                "expedited": True,
                "estimated_delivery": "2026-05-30T00:00:00Z",
            },
            status_code=200,
        )
        result = await _invoke_create_replacement_order(order_id="ORD-001")

    assert result["success"] is True
    assert result["replacement_order_id"] == "REP-001"
    assert result["expedited"] is True
    assert result["estimated_delivery"] == "2026-05-30T00:00:00Z"
    assert result["error"] is None

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_empty_order_id():
    """An empty order_id returns an error without any API call."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        result = await _invoke_create_replacement_order(order_id="")

    assert result["success"] is False
    assert result["error"] == "order_id must not be empty"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_missing_base_url():
    """Missing OMS_BASE_URL returns an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.delenv("OMS_BASE_URL", raising=False)
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        result = await _invoke_create_replacement_order(order_id="ORD-001")

    assert result["success"] is False
    assert result["error"] == "OMS_BASE_URL environment variable is not set"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_missing_api_key():
    """Missing OMS_API_KEY returns an env var error without API calls."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.delenv("OMS_API_KEY", raising=False)

    async with respx.mock:
        result = await _invoke_create_replacement_order(order_id="ORD-001")

    assert result["success"] is False
    assert result["error"] == "OMS_API_KEY environment variable is not set"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_404():
    """OMS returning 404 produces an Order not found error."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        respx.post("https://oms.example.com/orders/ORD-999/replicate").respond(
            status_code=404,
        )
        result = await _invoke_create_replacement_order(order_id="ORD-999")

    assert result["success"] is False
    assert "Order not found" in result["error"]

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_timeout():
    """OMS API timeout produces a timeout error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        route = respx.post("https://oms.example.com/orders/ORD-001/replicate")
        route.side_effect = httpx.TimeoutException(
            "Timed out",
            request=httpx.Request("POST", "https://oms.example.com/orders/ORD-001/replicate"),
        )
        result = await _invoke_create_replacement_order(order_id="ORD-001")

    assert result["success"] is False
    assert result["error"] == "OMS API timed out"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_replacement_order_malformed_response():
    """Non-JSON OMS response produces an unexpected error response."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key_456")

    async with respx.mock:
        respx.post("https://oms.example.com/orders/ORD-001/replicate").respond(
            text="not-json", status_code=200,
        )
        result = await _invoke_create_replacement_order(order_id="ORD-001")

    assert result["success"] is False
    assert "Unexpected OMS API error" in result["error"]

    monkeypatch.undo()
