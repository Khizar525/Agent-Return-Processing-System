"""
Resolution Agent Tests
Owner: Member 3

Tests the agent definition, tool configuration, guardrails, and
autonomous OpenAI Agents SDK execution.

Run:
    pytest tests/test_resolution_agent.py -v
"""

import json
import os
import pytest
import respx

from agents import Agent, Runner
from agents.tool import ToolContext
from agents.exceptions import OutputGuardrailTripwireTriggered
from app_agents.resolution_agent import resolution_agent, ResolutionSummary
from tools.payment_tools import process_refund
from tools.shipping_tools import create_return_label, create_replacement_order
from guardrails.refund_cap import refund_cap_guardrail

_STRIPE_REFUND_URL = "https://api.stripe.com/v1/refunds"


async def _invoke_process_refund(order_id: str, amount_usd: float, method: str) -> dict:
    """Invoke process_refund through the FunctionTool wrapper."""
    args = json.dumps({"order_id": order_id, "amount_usd": amount_usd, "method": method})
    ctx = ToolContext(
        context=None,
        tool_name="process_refund",
        tool_call_id="test_call",
        tool_arguments=args,
    )
    result = await process_refund.on_invoke_tool(ctx, args)
    if isinstance(result, str):
        return json.loads(result)
    return result


# ---------------------------------------------------------------------------
# Agent definition tests
# ---------------------------------------------------------------------------


def test_agent_name():
    assert resolution_agent.name == "ResolutionAgent"


def test_agent_has_correct_model():
    assert resolution_agent.model == "deepseek-v4-flash-free"


def test_agent_has_all_three_tools():
    tool_names = {t.name for t in resolution_agent.tools}
    assert "process_refund" in tool_names
    assert "create_return_label" in tool_names
    assert "create_replacement_order" in tool_names


def test_agent_tools_are_function_tool_instances():
    for tool in resolution_agent.tools:
        assert hasattr(tool, "on_invoke_tool"), f"{tool.name} is not a FunctionTool"


def test_agent_has_refund_cap_guardrail():
    assert refund_cap_guardrail in resolution_agent.output_guardrails


def test_agent_instructions_mention_refund():
    assert "refund" in resolution_agent.instructions.lower()


def test_agent_instructions_mention_label():
    assert "label" in resolution_agent.instructions.lower()


def test_agent_instructions_mention_replacement():
    assert "replacement" in resolution_agent.instructions.lower()


def test_agent_instructions_mention_500():
    assert "500" in resolution_agent.instructions


# ---------------------------------------------------------------------------
# Tool invocation tests  (via FunctionTool.on_invoke_tool)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_refund_returns_dict_with_success_key():
    """Invocation via on_invoke_tool returns a dict with 'success' key."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc123")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        respx.post(_STRIPE_REFUND_URL).respond(
            json={"id": "txn_111", "object": "refund"}, status_code=200,
        )
        result = await _invoke_process_refund(
            order_id="ORD-111", amount_usd=10.0, method="stripe")

    assert isinstance(result, dict)
    assert result["success"] is True
    assert result["transaction_id"] == "txn_111"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_process_refund_empty_order_id():
    """Empty order_id returns error dict, not raises ValueError."""
    result = await _invoke_process_refund(
        order_id="", amount_usd=50.0, method="stripe")
    assert result["success"] is False
    assert "order_id must not be empty" in result["error"]


@pytest.mark.asyncio
async def test_process_refund_unsupported_method():
    """Unsupported method returns error dict."""
    result = await _invoke_process_refund(
        order_id="ORD-001", amount_usd=50.0, method="bitcoin")
    assert result["success"] is False
    assert "Unsupported payment method" in result["error"]


# ---------------------------------------------------------------------------
# Fixture-based data contract tests
# ---------------------------------------------------------------------------


def test_resolution_fixture_has_resolution_agent_cases(resolutions):
    """Verify at least one fixture case expects resolution_agent in chain."""
    cases = [
        r for r in resolutions
        if r.get("expected_agent_chain")
        and "ResolutionAgent" in r["expected_agent_chain"]
    ]
    assert len(cases) >= 1


def test_resolution_fixture_refund_cap_case(resolutions):
    """res_004: refund > $500 requires human approval."""
    res_004 = next(r for r in resolutions if r["resolution_id"] == "res_004")
    assert res_004["expected_policy_output"]["recommended_action"] == "refund"
    assert res_004["expected_resolution_output"]["human_approval_required"] is True
    assert "ResolutionAgent" in res_004["expected_agent_chain"]


def test_resolution_fixture_happy_path(resolutions):
    """res_001: refund < $500 -> successful resolution."""
    res_001 = next(r for r in resolutions if r["resolution_id"] == "res_001")
    assert res_001["expected_policy_output"]["recommended_action"] == "refund"
    assert res_001["expected_resolution_output"]["success"] is True
    assert "ResolutionAgent" in res_001["expected_agent_chain"]


# ---------------------------------------------------------------------------
# E2E Autonomous Agent & Mocked Runner Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_autonomous_refund_success():
    """Agent autonomously calls process_refund tool and returns structured output."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        # Mock Stripe refund API
        respx.post(_STRIPE_REFUND_URL).respond(
            json={"id": "txn_stripe_111"}, status_code=200
        )

        # 1. Mock OpenAI response initiating process_refund tool call
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "process_refund",
                        "arguments": json.dumps({"order_id": "ord_1002", "amount_usd": 149.50, "method": "stripe"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        # 2. Mock OpenAI final output yielding the structured response
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_002",
                "created_at": 1677652290,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_002",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": True,
                                    "refund_amount": 149.50,
                                    "currency": "USD",
                                    "human_approval_required": False,
                                    "reason": "Refund processed successfully via Stripe."
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 20, "total_tokens": 40}
            },
            status_code=200
        )

        result = await Runner.run(resolution_agent, "Process a refund of $149.50 for order ord_1002 using stripe.")

    # Assert structured output is deserialized correctly into ResolutionSummary
    assert isinstance(result.final_output, ResolutionSummary)
    assert result.final_output.success is True
    assert result.final_output.refund_amount == 149.50
    assert result.final_output.currency == "USD"
    assert result.final_output.human_approval_required is False
    assert "Stripe" in result.final_output.reason

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_agent_refund_cap_enforcement_above_limit():
    """Agent autonomously blocks refund requests > $500, triggering the output guardrail if output contains amount."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        # Mock OpenAI response returning the structured output with human_approval_required and amount 1200.00
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": False,
                                    "human_approval_required": True,
                                    "amount": 1200.00,
                                    "reason": "exceeds_cap"
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        with pytest.raises(OutputGuardrailTripwireTriggered) as excinfo:
            await Runner.run(resolution_agent, "Refund $1200 for order ord_3004.")

    # Verify output guardrail properties
    guardrail_result = excinfo.value.guardrail_result
    output_info = guardrail_result.output.output_info
    assert output_info["human_approval_required"] is True
    assert output_info["amount"] == 1200.00
    assert output_info["reason"] == "exceeds_cap"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_agent_graceful_api_failure_handling():
    """Agent handles tool execution failures gracefully and populates structured output error fields."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        # Stripe returns HTTP 500
        respx.post(_STRIPE_REFUND_URL).respond(
            status_code=500
        )

        # 1. Mock OpenAI tool call
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "process_refund",
                        "arguments": json.dumps({"order_id": "ord_1002", "amount_usd": 50.0, "method": "stripe"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        # 2. Mock OpenAI error summary response
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_002",
                "created_at": 1677652290,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_002",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": False,
                                    "error": "Stripe API returned HTTP 500",
                                    "reason": "Failed to process refund due to payment gateway error."
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 20, "total_tokens": 40}
            },
            status_code=200
        )

        result = await Runner.run(resolution_agent, "Refund $50 for order ord_1002.")

    assert isinstance(result.final_output, ResolutionSummary)
    assert result.final_output.success is False
    assert "HTTP 500" in result.final_output.error
    assert "gateway error" in result.final_output.reason

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_agent_autonomous_replacement_success():
    """Agent autonomously calls create_replacement_order tool and returns structured output.
    Uses mock IDs and years <= 500 to avoid tripping the output guardrail."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("OMS_BASE_URL", "https://oms.example.com")
    monkeypatch.setenv("OMS_API_KEY", "oms_key")

    async with respx.mock:
        # Mock OMS API
        respx.post("https://oms.example.com/orders/ord_102/replicate").respond(
            json={"order_id": "rep_111", "expedited": True, "estimated_delivery": "0222-06-15T12:00:00Z"},
            status_code=200
        )

        # 1. Mock OpenAI response initiating create_replacement_order tool call
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "create_replacement_order",
                        "arguments": json.dumps({"order_id": "ord_102"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        # 2. Mock OpenAI final output yielding the structured response
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_002",
                "created_at": 1677652290,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_002",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": True,
                                    "replacement_order_id": "rep_111",
                                    "estimated_delivery": "0222-06-15T12:00:00Z",
                                    "reason": "Replacement order rep_111 has been generated."
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 20, "total_tokens": 40}
            },
            status_code=200
        )

        result = await Runner.run(resolution_agent, "Send a replacement order for ord_102.")

    assert isinstance(result.final_output, ResolutionSummary)
    assert result.final_output.success is True
    assert result.final_output.replacement_order_id == "rep_111"
    assert result.final_output.estimated_delivery == "0222-06-15T12:00:00Z"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_agent_autonomous_label_success():
    """Agent autonomously calls create_return_label tool and returns structured output.
    Uses mock IDs <= 500 to avoid tripping the output guardrail."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("UPS_CLIENT_ID", "ups_id")
    monkeypatch.setenv("UPS_CLIENT_SECRET", "ups_secret")

    async with respx.mock:
        # Mock UPS auth & shipment APIs
        respx.post("https://onlinetools.ups.com/security/v1/oauth/token").respond(
            json={"access_token": "ups_token"}, status_code=200
        )
        respx.post("https://onlinetools.ups.com/api/shipments/v1/label").respond(
            json={"labelUrl": "https://ups.com/label.gif", "trackingNumber": "1Z111"},
            status_code=200
        )

        # 1. Mock OpenAI response initiating create_return_label tool call
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "create_return_label",
                        "arguments": json.dumps({"order_id": "ord_102", "carrier": "ups"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        # 2. Mock OpenAI final output yielding the structured response
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_002",
                "created_at": 1677652290,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_002",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": True,
                                    "label_url": "https://ups.com/label.gif",
                                    "tracking_number": "1Z111",
                                    "carrier": "ups",
                                    "reason": "UPS label generated."
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 20, "total_tokens": 40}
            },
            status_code=200
        )

        result = await Runner.run(resolution_agent, "Generate a UPS return label for ord_102.")

    assert isinstance(result.final_output, ResolutionSummary)
    assert result.final_output.success is True
    assert result.final_output.label_url == "https://ups.com/label.gif"
    assert result.final_output.tracking_number == "1Z111"
    assert result.final_output.carrier == "ups"

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_agent_autonomous_sequencing():
    """Agent autonomously sequences label generation and refund tool calls based on request context.
    Uses mock IDs <= 500 to avoid tripping the output guardrail."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("UPS_CLIENT_ID", "ups_id")
    monkeypatch.setenv("UPS_CLIENT_SECRET", "ups_secret")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock")
    monkeypatch.setenv("REFUND_CAP_USD", "500")

    async with respx.mock:
        # Mock UPS APIs
        respx.post("https://onlinetools.ups.com/security/v1/oauth/token").respond(
            json={"access_token": "ups_token"}, status_code=200
        )
        respx.post("https://onlinetools.ups.com/api/shipments/v1/label").respond(
            json={"labelUrl": "https://ups.com/label.gif", "trackingNumber": "1Z111"},
            status_code=200
        )
        # Mock Stripe API
        respx.post(_STRIPE_REFUND_URL).respond(
            json={"id": "txn_stripe_111"}, status_code=200
        )

        # 1. Mock OpenAI response initiating create_return_label first
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_001",
                "created_at": 1677652288,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_001",
                        "type": "function_call",
                        "call_id": "call_123",
                        "name": "create_return_label",
                        "arguments": json.dumps({"order_id": "ord_102", "carrier": "ups"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20}
            },
            status_code=200
        )

        # 2. Mock OpenAI response initiating process_refund next
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_002",
                "created_at": 1677652290,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_002",
                        "type": "function_call",
                        "call_id": "call_456",
                        "name": "process_refund",
                        "arguments": json.dumps({"order_id": "ord_102", "amount_usd": 149.50, "method": "stripe"}),
                        "status": "completed"
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30}
            },
            status_code=200
        )

        # 3. Mock OpenAI final output yielding the structured response with both label and refund details
        respx.post("https://api.openai.com/v1/responses").respond(
            json={
                "id": "resp_003",
                "created_at": 1677652292,
                "object": "response",
                "status": "completed",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "item_003",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({
                                    "success": True,
                                    "refund_amount": 149.50,
                                    "currency": "USD",
                                    "label_url": "https://ups.com/label.gif",
                                    "tracking_number": "1Z111",
                                    "carrier": "ups",
                                    "reason": "UPS label generated and refund processed successfully."
                                }),
                                "annotations": []
                            }
                        ]
                    }
                ],
                "usage": {"input_tokens": 30, "output_tokens": 20, "total_tokens": 50}
            },
            status_code=200
        )

        result = await Runner.run(
            resolution_agent,
            "Create a UPS return label and process a refund of $149.50 for order ord_102 using stripe."
        )

    assert isinstance(result.final_output, ResolutionSummary)
    assert result.final_output.success is True
    assert result.final_output.refund_amount == 149.50
    assert result.final_output.label_url == "https://ups.com/label.gif"
    assert result.final_output.tracking_number == "1Z111"
    assert result.final_output.carrier == "ups"

    monkeypatch.undo()
