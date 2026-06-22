"""
Datadog APM Instrumentation
Owner: Member 5

Instruments the FastAPI app and all agent tool calls with Datadog APM.
Configures the service map to show all 6 agents as separate services.

Setup:
    Call configure_datadog() at application startup (in main.py).

Instrumentation layers:
    1. ddtrace patch_all — FastAPI, httpx, redis
    2. Custom trace processor — intercepts agent handoffs and tool calls
    3. Agent service naming — each agent appears as a separate service in the map

Span tags applied:
    - agent.name        — which agent processed this span
    - agent.handoff     — handoff source → target
    - tool.name         — tool being invoked
    - session_id        — customer session identifier
    - channel           — inbound channel (web_chat, email, etc.)

Environment variables required:
    DD_API_KEY
    DD_APP_KEY
    DD_SERVICE   (default: "agent01-customer-support")
    DD_ENV       (default: "production")
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger("datadog_setup")

_AGENT_SERVICES: dict[str, str] = {
    "triage_orchestrator": "agent01-triage",
    "policy_agent": "agent01-policy",
    "resolution_agent": "agent01-resolution",
    "billing_agent": "agent01-billing",
    "communication_agent": "agent01-communication",
    "escalation_agent": "agent01-escalation",
}

_TRACER_ENABLED = False


def configure_datadog() -> bool:
    """Initialize Datadog APM instrumentation.

    Call once at application startup (FastAPI lifespan event).
    Returns True if instrumentation was applied, False if disabled
    (e.g. DD_API_KEY not set or running in tests).

    Effects:
        - Patches FastAPI, httpx, redis for distributed tracing
        - Enables Datadog profiling
        - Configures the tracer service name
    """
    global _TRACER_ENABLED

    api_key = os.environ.get("DD_API_KEY")
    if not api_key:
        logger.info("DD_API_KEY not set — Datadog tracing disabled")
        return False

    try:
        from ddtrace import config as ddconfig
        from ddtrace import patch_all

        service = os.environ.get("DD_SERVICE", "agent01-customer-support")
        env = os.environ.get("DD_ENV", "production")
        version = os.environ.get("DD_VERSION", "0.1.0")

        ddconfig.service = service
        ddconfig.env = env
        ddconfig.version = version
        ddconfig.logs_injection = True

        patch_all(fastapi=True, httpx=True, redis=True)

        logger.info(
            "Datadog APM configured — service=%s, env=%s, version=%s",
            service, env, version,
        )
        _TRACER_ENABLED = True
        return True
    except ImportError:
        logger.warning("ddtrace package not installed — Datadog tracing unavailable")
        return False
    except Exception:
        logger.exception("Failed to configure Datadog APM")
        return False


@contextmanager
def agent_span(
    agent_name: str,
    span_type: str = "agent_handoff",
    **tags: Any,
) -> Generator[Any, None, None]:
    """Create a Datadog span for an agent handoff or tool call.

    The span is tagged with the agent's service name for the service map.

    Args:
        agent_name: Logical agent name (key in _AGENT_SERVICES).
        span_type:  Span type category (agent_handoff, tool_call, intent_classify).
        **tags:     Additional span tags.

    Usage:
        with agent_span("policy_agent", session_id="sess_001"):
            result = await policy_agent.run(...)
    """
    if not _TRACER_ENABLED:
        yield None
        return

    from ddtrace.trace import tracer as _tracer

    service = _AGENT_SERVICES.get(agent_name, "agent01-unknown")
    span_name = f"{span_type}.{agent_name}"

    with _tracer.trace(
        span_name,
        service=service,
        resource=span_name,
    ) as span:
        span.set_tag("agent.name", agent_name)
        span.set_tag("agent.service", service)
        for key, value in tags.items():
            span.set_tag(key, str(value) if value is not None else "null")
        yield span


@contextmanager
def tool_span(tool_name: str, agent_name: str, **tags: Any) -> Generator[Any, None, None]:
    """Create a Datadog span for a tool invocation.

    Tracks tool call latency and result status.

    Args:
        tool_name:  Tool function name (e.g. check_return_policy).
        agent_name: The agent that invoked this tool.
        **tags:     Additional span tags.
    """
    if not _TRACER_ENABLED:
        yield None
        return

    from ddtrace.trace import tracer as _tracer

    service = _AGENT_SERVICES.get(agent_name, "agent01-unknown")
    span_name = f"tool_call.{tool_name}"

    with _tracer.trace(
        span_name,
        service=service,
        resource=span_name,
    ) as span:
        span.set_tag("tool.name", tool_name)
        span.set_tag("agent.name", agent_name)
        span.set_tag("agent.service", service)
        for key, value in tags.items():
            span.set_tag(key, str(value) if value is not None else "null")
        yield span


def record_resolution(
    session_id: str,
    agent_chain: list[str],
    duration_seconds: float,
    success: bool,
) -> None:
    """Record ticket resolution metrics to Datadog.

    Tags the resolution with the full agent chain and sets a custom metric
    for P95 latency tracking.

    Args:
        session_id:     Customer session identifier.
        agent_chain:    Ordered list of agents that handled this ticket.
        duration_seconds: Wall-clock resolution time in seconds.
        success:        Whether the resolution completed without error.
    """
    if not _TRACER_ENABLED:
        return

    try:
        from ddtrace.trace import tracer as _tracer

        span = _tracer.current_span()
        if span is None:
            return

        span.set_tag("session_id", session_id)
        span.set_tag("agent_chain", " → ".join(agent_chain))
        span.set_tag("agent_chain.count", str(len(agent_chain)))
        span.set_metric("resolution.duration_seconds", duration_seconds)
        span.set_tag("resolution.success", str(success))

        chain_tags = ",".join(
            _AGENT_SERVICES.get(a, a) for a in agent_chain
        )
        span.set_tag("agent_chain.services", chain_tags)

        logger.info(
            "Resolution recorded — session=%s, chain=%s, duration=%.2fs, success=%s",
            session_id, agent_chain, duration_seconds, success,
        )
    except Exception:
        logger.exception("Failed to record resolution metric")
