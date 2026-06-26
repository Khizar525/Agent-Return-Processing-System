"""
A/B Test Framework — Agent 01 Experimentation Engine
Owner: Member 5

Routes a configurable percentage of tickets to variant agent configurations
and compares resolution outcomes (resolution time, success rate, CSAT score).

Designed to be called from the triage orchestrator before dispatch to decide
which agent config/handoff path to use for a given session.

Usage:
    from infra.ab_test import get_variant, record_experiment_result

    # During triage — assign variant
    variant = get_variant("agent_config_v1", session_id)
    config = get_experiment_config("agent_config_v1", variant)

    # After resolution — record result
    record_experiment_result("agent_config_v1", variant, session_id, "resolution_time", 12.5)

Experiments are configured via a dict (hardcoded for simplicity; can be
moved to Redis/env for dynamic updates in production).

Output:
    - Datadog metrics: agent01.ab_test.variant_distribution,
      agent01.ab_test.resolution_time, agent01.ab_test.success_rate
    - Logged experiment metadata for dashboard consumption
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger("ab_test")

# ---------------------------------------------------------------------------
# Experiment registry — add new experiments here
# ---------------------------------------------------------------------------

ExperimentVariant = Literal["control", "treatment"]

ABTestExperiment = dict[
    str,
    dict[
        str,
        dict[
            str,
            Any,
        ]
    ]
]

EXPERIMENTS: dict[str, dict[str, Any]] = {
    "agent_config_v1": {
        "enabled": True,
        "description": "Test updated policy agent instructions vs baseline",
        "variants": {
            "control": {
                "weight": 50,
                "config": {
                    "agent_model": "openai/gpt-oss-120b:free",
                    "policy_instructions": "baseline",
                    "enable_fraud_check": True,
                },
            },
            "treatment": {
                "weight": 50,
                "config": {
                    "agent_model": "openai/gpt-oss-120b:free",
                    "policy_instructions": "expedited_v1",
                    "enable_fraud_check": False,
                },
            },
        },
        "metrics": ["resolution_time", "success_rate", "csat_score"],
        "started_at": "2026-06-24T00:00:00Z",
    },
}

_RESULTS: dict[str, list[dict[str, Any]]] = defaultdict(list)


# ---------------------------------------------------------------------------
# Deterministic variant assignment via hash partitioning
# ---------------------------------------------------------------------------


def _hash_partition(entity_id: str, total_weight: int) -> int:
    """Return a hash-based integer in [0, total_weight) for consistent routing.

    Uses SHA-256 so the same entity_id always maps to the same bucket
    across restarts, ensuring a customer stays in the same variant.
    """
    digest = hashlib.sha256(entity_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % total_weight


def get_variant(experiment_name: str, entity_id: str) -> str:
    """Assign an entity (session_id or customer_id) to a variant.

    Args:
        experiment_name: Key in the EXPERIMENTS registry.
        entity_id:       Stable identifier — same ID always gets same variant.

    Returns:
        Variant name ("control" or "treatment").
        If the experiment is disabled or unknown, returns "control" as default.

    Example:
        variant = get_variant("agent_config_v1", session_id)
    """
    experiment = EXPERIMENTS.get(experiment_name)
    if not experiment or not experiment.get("enabled", False):
        logger.debug("Experiment '%s' disabled or unknown — defaulting to control", experiment_name)
        return "control"

    variants = experiment["variants"]
    total_weight = sum(v["weight"] for v in variants.values())
    bucket = _hash_partition(entity_id, total_weight)

    cumulative = 0
    for variant_name, variant_config in variants.items():
        cumulative += variant_config["weight"]
        if bucket < cumulative:
            logger.debug(
                "AB test — experiment=%s, entity=%s, variant=%s, bucket=%d/%d",
                experiment_name,
                entity_id,
                variant_name,
                bucket,
                total_weight,
            )
            return variant_name

    return "control"


def get_experiment_config(experiment_name: str, variant: str) -> dict[str, Any]:
    """Retrieve the configuration dict for a given experiment variant.

    Args:
        experiment_name: Key in the EXPERIMENTS registry.
        variant:         Variant name (e.g. "control", "treatment").

    Returns:
        The config dict for the variant, or empty dict if not found.
    """
    experiment = EXPERIMENTS.get(experiment_name, {})
    variants = experiment.get("variants", {})
    return variants.get(variant, {}).get("config", {})


def get_active_experiments() -> list[dict[str, Any]]:
    """Return metadata for all currently enabled experiments.

    Returns:
        List of {name, description, variant_count, metrics, started_at}.
    """
    active: list[dict[str, Any]] = []
    for name, exp in EXPERIMENTS.items():
        if exp.get("enabled", False):
            active.append({
                "name": name,
                "description": exp.get("description", ""),
                "variant_count": len(exp.get("variants", {})),
                "metrics": exp.get("metrics", []),
                "started_at": exp.get("started_at", ""),
            })
    return active


# ---------------------------------------------------------------------------
# Result recording and metric emission
# ---------------------------------------------------------------------------


def _emit_datadog_gauge(name: str, value: float, tags: list[str] | None = None) -> None:
    """Submit a custom gauge metric to Datadog (same pattern as csat_pipeline)."""
    try:
        from ddtrace.trace import tracer as _tracer

        _tracer.current_span()
        try:
            from ddtrace.api import StatsdClient

            client = StatsdClient()
            client.gauge(name, value, tags=tags or [])
        except Exception:
            pass
    except Exception:
        pass

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
        logger.debug("Datadog API submission failed for %s", name)


def record_experiment_result(
    experiment_name: str,
    variant: str,
    session_id: str,
    metric_name: str,
    value: float,
) -> dict[str, Any]:
    """Record a metric result for an A/B test experiment.

    Emits a Datadog gauge and stores the result in memory for dashboard
    queries. Designed to be called after a resolution completes.

    Args:
        experiment_name: Key in the EXPERIMENTS registry.
        variant:         Variant name (e.g. "control", "treatment").
        session_id:      The session this result belongs to.
        metric_name:     One of the experiment's tracked metrics (e.g.
                         "resolution_time", "success_rate", "csat_score").
        value:           Numeric value to record.

    Returns:
        {
            "recorded": True,
            "experiment": experiment_name,
            "variant": variant,
            "metric": metric_name,
            "value": value,
            "session_id": session_id,
            "timestamp": <ISO-8601>,
        }
    """
    record = {
        "experiment": experiment_name,
        "variant": variant,
        "metric": metric_name,
        "value": value,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _RESULTS[experiment_name].append(record)

    tags = [
        f"experiment:{experiment_name}",
        f"variant:{variant}",
        f"metric:{metric_name}",
    ]

    _emit_datadog_gauge(f"agent01.ab_test.{metric_name}", value, tags)
    _emit_datadog_gauge("agent01.ab_test.record_count", 1.0, tags)

    logger.info(
        "AB test result — experiment=%s, variant=%s, metric=%s, value=%.4f, session=%s",
        experiment_name,
        variant,
        metric_name,
        value,
        session_id,
    )

    return {
        "recorded": True,
        "experiment": experiment_name,
        "variant": variant,
        "metric": metric_name,
        "value": value,
        "session_id": session_id,
        "timestamp": record["timestamp"],
    }


def get_experiment_summary(experiment_name: str) -> dict[str, Any]:
    """Return aggregate results for a given experiment.

    Computes mean, count, and min/max per variant for each tracked metric.

    Args:
        experiment_name: Key in the EXPERIMENTS registry.

    Returns:
        {
            "experiment": <name>,
            "summary": {
                "<variant>": {
                    "<metric>": {
                        "mean": float,
                        "count": int,
                        "min": float,
                        "max": float,
                    }
                }
            }
        }
    """
    records = _RESULTS.get(experiment_name, [])
    if not records:
        return {"experiment": experiment_name, "summary": {}, "record_count": 0}

    aggregates: dict[str, dict[str, dict[str, float]]] = {}
    for record in records:
        var = record["variant"]
        metric = record["metric"]
        val = record["value"]

        if var not in aggregates:
            aggregates[var] = {}
        if metric not in aggregates[var]:
            aggregates[var][metric] = {"values": []}
        aggregates[var][metric]["values"].append(val)

    summary: dict[str, dict[str, dict[str, float]]] = {}
    for var, metrics in aggregates.items():
        summary[var] = {}
        for metric_name, data in metrics.items():
            vals = data["values"]
            summary[var][metric_name] = {
                "mean": round(sum(vals) / len(vals), 4),
                "count": len(vals),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
            }

    return {
        "experiment": experiment_name,
        "summary": summary,
        "record_count": len(records),
    }


def reset_experiment(experiment_name: str | None = None) -> None:
    """Clear stored results (useful in tests between scenarios).

    Args:
        experiment_name: Specific experiment to clear, or None to clear all.
    """
    if experiment_name:
        _RESULTS.pop(experiment_name, None)
    else:
        _RESULTS.clear()
