"""
Resolution Agent
Owner: Member 3

Deterministic resolution orchestrator — NO LLM involvement in tool execution.

Receives a policy_decision dict and executes approved resolutions via the
Member 3 tool suite (process_refund, create_return_label,
create_replacement_order).

IMPORTANT:
    - Guardrail escalation is handled by deterministic Python, NOT the LLM.
    - process_refund executes BEFORE label generation (sequential, not parallel).
    - create_return_label is NEVER called after refund failure or guardrail.
    - Every code path returns a valid ResolutionOutput.
    - Exceptions are caught per-tool, never allowed to escape.

Resolution paths:
    - reject         → return rejected (no tools called)
    - escalate       → return escalated (no tools called)
    - replacement    → call create_replacement_order
    - refund         → call process_refund → (optional) call create_return_label
    - unknown action → return error
"""

import json
import logging
import time
import uuid

from pydantic import BaseModel

from agents.tool import ToolContext
from tools.payment_tools import process_refund
from tools.shipping_tools import create_return_label, create_replacement_order

logger = logging.getLogger(__name__)

_GUARDRAIL_SIGNAL = "human_approval_required"


class ResolutionOutput(BaseModel):
    resolution_action: str = "unknown"
    reason: str = ""
    transaction_id: str = ""
    refund_amount: float = 0.0
    label_url: str = ""
    tracking_number: str = ""
    carrier: str = ""
    replacement_order_id: str = ""
    estimated_delivery: str = ""
    error: str | None = None
    human_approval_required: bool = False


# ── Tool invocation helpers ──────────────────────────────────────────────


async def _call_tool(tool, tool_name: str, args: dict) -> dict:
    """Normalize a FunctionTool invocation into a standard result dict.

    Handles three return formats from the SDK's on_invoke_tool:
        1. dict          → passed through
        2. JSON string   → parsed to dict
        3. error string  → detected guardrail signal, returned as
                           { success: false, human_approval_required: true, error: ... }
    """
    ctx = ToolContext(
        context=None,
        tool_name=tool_name,
        tool_call_id=uuid.uuid4().hex[:12],
        tool_arguments=json.dumps(args),
    )
    result = await tool.on_invoke_tool(ctx, json.dumps(args))

    if isinstance(result, dict):
        return result

    if isinstance(result, str):
        if _GUARDRAIL_SIGNAL in result:
            return {"success": False, "human_approval_required": True, "error": result}
        try:
            return json.loads(result)
        except (json.JSONDecodeError, ValueError):
            return {"success": False, "error": result}

    return {"success": False, "error": f"Unexpected result type: {type(result).__name__}"}


async def _execute_refund(order_id: str, amount_usd: float, method: str) -> dict:
    try:
        return await _call_tool(
            process_refund, "process_refund",
            {"order_id": order_id, "amount_usd": amount_usd, "method": method},
        )
    except Exception as exc:
        logger.error("execute_refund.error", extra={"error": str(exc)})
        return {"success": False, "error": f"Refund execution failed: {exc}"}


async def _execute_label(order_id: str, carrier: str) -> dict:
    try:
        return await _call_tool(
            create_return_label, "create_return_label",
            {"order_id": order_id, "carrier": carrier},
        )
    except Exception as exc:
        logger.error("execute_label.error", extra={"error": str(exc)})
        return {"success": False, "error": f"Label generation failed: {exc}"}


async def _execute_replacement(order_id: str) -> dict:
    try:
        return await _call_tool(
            create_replacement_order, "create_replacement_order",
            {"order_id": order_id},
        )
    except Exception as exc:
        logger.error("execute_replacement.error", extra={"error": str(exc)})
        return {"success": False, "error": f"Replacement order failed: {exc}"}


# ── Resolution Orchestrator ──────────────────────────────────────────────


async def resolve_return(
    policy_decision: dict,
    *,
    order_id: str = "",
    amount_usd: float = 0.0,
    payment_method: str = "stripe",
    carrier: str = "fedex",
    label_needed: bool = False,
    customer_id: str = "",
    session_id: str = "",
) -> ResolutionOutput:
    """Deterministic resolution orchestrator — no LLM involvement.

    Args:
        policy_decision: Output from the Policy Agent.
        order_id:        The order to resolve.
        amount_usd:      Refund amount (used when action is "refund").
        payment_method:  "stripe" | "paypal".
        carrier:         "fedex" | "ups".
        label_needed:    Whether to also generate a return label after refund.
        customer_id:     For logging / context propagation.
        session_id:      For logging / context propagation.

    Returns:
        ResolutionOutput — guaranteed on every code path.
    """
    start = time.monotonic()
    action = policy_decision.get("recommended_action", "unknown")
    eligible = policy_decision.get("eligible", False)

    logger.info("resolve_return.start", extra={
        "action": action, "eligible": eligible,
        "order_id": order_id, "customer_id": customer_id,
        "session_id": session_id,
    })

    # ── Top-level safety net ─────────────────────────────────────────
    try:

        # ── Guard: invalid policy decision ───────────────────────────
        if policy_decision.get("error"):
            return _emit("error", start,
                         reason=policy_decision["error"])

        # ── Guard: not eligible (policy rejected) ────────────────────
        if not eligible:
            return _emit("rejected", start,
                         reason=policy_decision.get("reason") or "Return is not eligible")

        # ── reject ──────────────────────────────────────────────────
        if action == "reject":
            return _emit("rejected", start,
                         reason=policy_decision.get("reason") or "Return was rejected by policy")

        # ── escalate ────────────────────────────────────────────────
        if action == "escalate":
            return _emit("escalated", start,
                         reason=policy_decision.get("reason") or "Case requires human escalation")

        # ── replacement ─────────────────────────────────────────────
        if action == "replacement":
            repl_result = await _execute_replacement(order_id)
            if repl_result.get("success"):
                return _emit("replacement_created", start,
                             replacement_order_id=repl_result.get("replacement_order_id", ""),
                             estimated_delivery=repl_result.get("estimated_delivery", ""),
                             reason="Replacement order has been created.")
            return _emit("replacement_failed", start,
                         error=repl_result.get("error", "Unknown replacement error"),
                         reason="Failed to create replacement order.")

        # ── refund (with optional label) ────────────────────────────
        if action == "refund":
            refund_result = await _execute_refund(order_id, amount_usd, payment_method)

            # GUARDRAIL DETECTION — deterministic Python, NOT LLM
            if refund_result.get("human_approval_required"):
                return _emit("escalated", start,
                             human_approval_required=True,
                             refund_amount=amount_usd,
                             reason=f"Refund of ${amount_usd:.2f} exceeds the refund cap. "
                                    f"Human approval required.")

            if not refund_result.get("success"):
                return _emit("refund_failed", start,
                             refund_amount=amount_usd,
                             error=refund_result.get("error", "Unknown refund error"),
                             reason="Refund could not be processed.")

            tx_id = refund_result.get("transaction_id", "")

            # Label generation — ONLY if refund succeeded (sequential gate)
            if label_needed:
                label_result = await _execute_label(order_id, carrier)
                if label_result.get("success"):
                    return _emit("refund_completed", start,
                                 transaction_id=tx_id,
                                 refund_amount=amount_usd,
                                 label_url=label_result.get("label_url", ""),
                                 tracking_number=label_result.get("tracking_number", ""),
                                 carrier=label_result.get("carrier", carrier),
                                 reason=f"Refund of ${amount_usd:.2f} processed "
                                        f"and return label generated.")

                # Label failure does NOT undo the refund
                return _emit("refund_completed", start,
                             transaction_id=tx_id,
                             refund_amount=amount_usd,
                             error=label_result.get("error", "Label generation failed"),
                             reason=f"Refund of ${amount_usd:.2f} processed "
                                    f"but label generation failed.")

            return _emit("refund_completed", start,
                         transaction_id=tx_id,
                         refund_amount=amount_usd,
                         reason=f"Refund of ${amount_usd:.2f} processed successfully.")

        # ── unknown action ───────────────────────────────────────────
        return _emit("error", start,
                     reason=f"Unknown recommended_action: '{action}'")

    except Exception as exc:
        logger.error("resolve_return.unexpected_error", extra={
            "error": str(exc), "customer_id": customer_id,
            "session_id": session_id,
        })
        return _emit("error", start,
                     reason=f"Resolution orchestrator error: {exc}")


def _emit(action: str, start: float, **kwargs) -> ResolutionOutput:
    """Construct a ResolutionOutput, log completion, and return it."""
    output = ResolutionOutput(resolution_action=action, **kwargs)
    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info("resolve_return.complete", extra={
        "resolution_action": output.resolution_action,
        "duration_ms": duration_ms,
        "human_approval_required": output.human_approval_required,
        "success": output.error is None,
    })
    return output
