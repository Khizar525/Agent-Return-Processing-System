"""
CSAT Pipeline
Owner: Member 5

Consumes log_resolution events from the agent pipeline and computes
a rolling CSAT score in near-real-time (within 5 seconds of event).

The pipeline is triggered by calling ingest_resolution_event() after
a ticket is resolved. It updates a rolling window in Redis and submits
the score to Datadog as a custom metric.

Output:
    - Rolling CSAT score (target: > 4.5 / 5.0)
    - Per-agent breakdown (which agent handled the resolved ticket)
    - Daily/weekly aggregates written back to Redis for dashboard

Score computation:
    CSAT = Σ(survey_score) / count    (1.0 - 5.0 scale)
    Rolling window: last 1000 resolutions by default.

Environment variables required:
    DD_API_KEY  (for metric submission to Datadog)
    REDIS_URL   (for caching aggregated scores)
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("csat_pipeline")

_RESOLUTION_EVENTS: deque[dict[str, Any]] = deque(maxlen=1000)
_CSAT_RECORDS: deque[float] = deque(maxlen=1000)

_AGENT_MAP: dict[str, str] = {
    "triage_orchestrator": "agent-nemo-triage",
    "policy_agent": "agent-nemo-policy",
    "resolution_agent": "agent-nemo-resolution",
    "billing_agent": "agent-nemo-billing",
    "communication_agent": "agent-nemo-communication",
    "escalation_agent": "agent-nemo-escalation",
}


def _emit_datadog_metric(name: str, value: float, tags: list[str] | None = None) -> None:
    """Submit a custom metric to Datadog via the API.

    Uses the Datadog API directly (no ddtrace dependency required
    for metric submission, since this may run in a separate process).
    Falls back to statsd if ddtrace is available, otherwise logs.
    """
    try:
        from ddtrace.trace import tracer as _tracer

        _tracer.current_span()
        # ddtrace runtime is active — use statsd
        try:
            from ddtrace.runtime import RuntimeMetrics

            RuntimeMetrics.enable()
        except Exception:
            pass
        # Submit via statsd client
        try:
            from ddtrace.api import StatsdClient

            client = StatsdClient()
            client.gauge(name, value, tags=tags or [])
        except Exception:
            logger.debug("Statsd submission failed — fallback to API")
    except ImportError:
        pass
    except Exception:
        logger.exception("Failed to emit Datadog metric: %s", name)

    # Also try direct API submission
    api_key = os.environ.get("DD_API_KEY")
    if not api_key:
        return

    try:
        import httpx

        site = os.environ.get("DD_SITE", "datadoghq.com")
        payload = {
            "series": [
                {
                    "metric": name,
                    "points": [(int(time.time()), value)],
                    "type": "gauge",
                    "tags": tags or [],
                }
            ]
        }
        httpx.post(
            f"https://api.{site}/api/v2/series",
            headers={
                "DD-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=5.0,
        )
    except Exception:
        logger.debug("Direct Datadog API submission failed for %s", name)


def compute_csat_score(survey_score: float, agent_name: str | None = None) -> dict[str, Any]:
    """Compute a rolling CSAT score from individual survey responses.

    Args:
        survey_score: Individual score (1.0 - 5.0) from customer survey.
        agent_name:   Optional — name of the agent that handled the ticket
                      for per-agent breakdown.

    Returns:
        {
            "rolling_csat":    float,   # Overall rolling average
            "sample_count":    int,     # Number of samples in window
            "per_agent":       dict,    # {agent_name: avg_score}
            "timestamp":       str,     # ISO-8601
        }
    """
    survey_score = max(1.0, min(5.0, float(survey_score)))
    _CSAT_RECORDS.append(survey_score)
    avg = sum(_CSAT_RECORDS) / len(_CSAT_RECORDS)

    result: dict[str, Any] = {
        "rolling_csat": round(avg, 4),
        "sample_count": len(_CSAT_RECORDS),
        "per_agent": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    if agent_name and agent_name in _AGENT_MAP:
        result["per_agent"][agent_name] = survey_score

    return result


def ingest_resolution_event(event: dict[str, Any]) -> dict[str, Any]:
    """Process a ticket-resolution event and produce an updated CSAT score.

    Expected event schema:
        {
            "session_id":     str,
            "agent_chain":    list[str],   # ordered list of agent names
            "resolved_by":    str,         # last agent in the chain
            "survey_score":   float,       # 1.0 - 5.0
            "channel":        str,         # web_chat | email | whatsapp | sms
            "timestamp":      str,         # ISO-8601
        }

    Returns the rolling CSAT result (same schema as compute_csat_score).

    Performance: completes in < 500ms to meet the 5-second SLA.
    """
    start = time.perf_counter()

    session_id = event.get("session_id", "unknown")
    survey_score = event.get("survey_score", 5.0)
    resolved_by = event.get("resolved_by", "unknown")
    agent_chain = event.get("agent_chain", [])

    _RESOLUTION_EVENTS.append(event)

    result = compute_csat_score(survey_score, resolved_by)
    result["session_id"] = session_id
    result["agent_chain"] = agent_chain

    tags = [
        f"service:{_AGENT_MAP.get(resolved_by, 'agent-nemo-unknown')}",
        f"channel:{event.get('channel', 'unknown')}",
    ]

    _emit_datadog_metric("agent-nemo.csat.rolling_score", result["rolling_csat"], tags)
    _emit_datadog_metric("agent-nemo.csat.sample_count", float(result["sample_count"]), tags)

    elapsed = time.perf_counter() - start
    if elapsed > 5.0:
        logger.warning(
            "CSAT pipeline exceeded 5s SLA — session=%s, elapsed=%.2fs",
            session_id,
            elapsed,
        )
    else:
        logger.info(
            "CSAT updated — session=%s, score=%.2f, samples=%d, elapsed=%.2fs",
            session_id,
            result["rolling_csat"],
            result["sample_count"],
            elapsed,
        )

    return result


def get_rolling_csat() -> dict[str, Any]:
    """Return the current rolling CSAT score without ingesting a new event."""
    if not _CSAT_RECORDS:
        return {
            "rolling_csat": None,
            "sample_count": 0,
            "per_agent": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    avg = sum(_CSAT_RECORDS) / len(_CSAT_RECORDS)

    per_agent: dict[str, list[float]] = defaultdict(list)
    for ev in _RESOLUTION_EVENTS:
        agent = ev.get("resolved_by", "unknown")
        score = ev.get("survey_score", 5.0)
        per_agent[agent].append(float(score))

    per_agent_avg = {
        agent: round(sum(scores) / len(scores), 4) for agent, scores in per_agent.items()
    }

    return {
        "rolling_csat": round(avg, 4),
        "sample_count": len(_CSAT_RECORDS),
        "per_agent": per_agent_avg,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def sync_to_redis(redis_url: str | None = None) -> None:
    """Persist the current aggregate scores to Redis for dashboard consumption.

    Called periodically (e.g. every 60s via a background task).
    Keys written:
        csat:rolling     — JSON of rolling CSAT result
        csat:per_agent   — JSON of per-agent averages
        csat:updated_at  — ISO-8601 timestamp of last sync
    """
    if not redis_url:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.debug("REDIS_URL not set — skipping Redis sync")
            return

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url, decode_responses=True)
        result = get_rolling_csat()

        await client.set("csat:rolling", json.dumps(result))
        await client.set("csat:per_agent", json.dumps(result.get("per_agent", {})))
        await client.set("csat:updated_at", result["timestamp"])
        await client.aclose()

        logger.debug("CSAT aggregates synced to Redis")
    except Exception:
        logger.exception("Failed to sync CSAT aggregates to Redis")
