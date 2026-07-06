"""
Datadog Monitors Configuration
Owner: Member 5

Defines 3 PagerDuty-bound alert monitors for the Agent Nemo system.
Each monitor fires within 60 seconds of threshold breach.

Monitors:
    1. Queue Depth > 500        — Kafka consumer lag across all topics
    2. Error Rate > 5%          — FastAPI webhook error ratio
    3. P95 Latency > 30 seconds — Ticket resolution duration

Usage:
    python -m infra.datadog_monitors create    # Create monitors via Datadog API
    python -m infra.datadog_monitors validate  # Validate monitor configs (dry run)
    python -m infra.datadog_monitors export    # Print JSON configs to stdout

Environment variables required:
    DD_API_KEY
    DD_APP_KEY
    DD_SITE           (default: "datadoghq.com")
    PAGERDUTY_SERVICE  (optional — service name in Datadog)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

logger = logging.getLogger("datadog_monitors")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)


def build_queue_depth_monitor() -> dict[str, Any]:
    """Alert 1: Kafka queue depth exceeds 500 messages.

    Evaluates the max consumer lag across all 4 topics.
    Fires to PagerDuty within 60 seconds (1 evaluation window).
    """
    return {
        "name": "Agent Nemo — Queue Depth > 500",
        "type": "query alert",
        "query": (
            "max(last_1m):max:kafka.consumer_lag{topic:agent-nemo.{webchat,email,whatsapp,sms}} > 500"
        ),
        "message": (
            "{{#is_alert}}"
            "Kafka queue depth is {{value}} — threshold is 500.\n"
            "Topic: {{topic.name}}\n"
            "@pagerduty-agent-nemo"
            "{{/is_alert}}"
            "{{#is_recovery}}"
            "Queue depth recovered to {{value}}.\n"
            "@pagerduty-agent-nemo"
            "{{/is_recovery}}"
        ),
        "tags": [
            "service:agent-nemo-customer-support",
            "alert:queue_depth",
            "severity:critical",
            "team:infra-observability",
        ],
        "options": {
            "thresholds": {"critical": 500.0},
            "notify_no_data": True,
            "no_data_timeframe": 5,
            "evaluation_delay": 30,
            "new_host_delay": 300,
            "renotify_interval": 60,
            "escalation_message": "Queue depth still above 500 — investigate consumer pods",
            "silenced": {},
        },
        "priority": 1,
    }


def build_error_rate_monitor() -> dict[str, Any]:
    """Alert 2: Error rate exceeds 5% of all webhook requests.

    Uses trace-based error ratio from ddtrace.
    Fires to PagerDuty within 60 seconds.
    """
    return {
        "name": "Agent Nemo — Error Rate > 5%",
        "type": "query alert",
        "query": (
            "sum(last_1m):"
            "trace.fastapi.request.errors{service:agent-nemo-customer-support}.as_count()"
            " / "
            "trace.fastapi.request.hits{service:agent-nemo-customer-support}.as_count()"
            " * 100 > 5"
        ),
        "message": (
            "{{#is_alert}}"
            "Error rate is {{value}}% — threshold is 5%.\n"
            "{{error_count}} errors in the last minute.\n"
            "@pagerduty-agent-nemo"
            "{{/is_alert}}"
            "{{#is_recovery}}"
            "Error rate recovered to {{value}}%.\n"
            "@pagerduty-agent-nemo"
            "{{/is_recovery}}"
        ),
        "tags": [
            "service:agent-nemo-customer-support",
            "alert:error_rate",
            "severity:critical",
            "team:infra-observability",
        ],
        "options": {
            "thresholds": {"critical": 5.0},
            "notify_no_data": True,
            "no_data_timeframe": 5,
            "evaluation_delay": 30,
            "new_host_delay": 300,
            "renotify_interval": 60,
            "escalation_message": "Error rate still above 5% — check agent logs and LLM provider",
            "silenced": {},
        },
        "priority": 1,
    }


def build_latency_p95_monitor() -> dict[str, Any]:
    """Alert 3: P95 resolution latency exceeds 30 seconds.

    Based on the custom metric emitted by record_resolution() in datadog_setup.py.
    Fires to PagerDuty within 60 seconds.
    """
    return {
        "name": "Agent Nemo — P95 Resolution Latency > 30s",
        "type": "query alert",
        "query": (
            "p95(last_1m):avg:trace.agent.resolution.duration_seconds{service:agent-nemo-customer-support}"
            " > 30"
        ),
        "message": (
            "{{#is_alert}}"
            "P95 resolution latency is {{value}}s — threshold is 30s.\n"
            "Agent chain: {{agent_chain.services}}\n"
            "@pagerduty-agent-nemo"
            "{{/is_alert}}"
            "{{#is_recovery}}"
            "P95 latency recovered to {{value}}s.\n"
            "@pagerduty-agent-nemo"
            "{{/is_recovery}}"
        ),
        "tags": [
            "service:agent-nemo-customer-support",
            "alert:latency_p95",
            "severity:high",
            "team:infra-observability",
        ],
        "options": {
            "thresholds": {"critical": 30.0},
            "notify_no_data": True,
            "no_data_timeframe": 5,
            "evaluation_delay": 30,
            "new_host_delay": 300,
            "renotify_interval": 60,
            "escalation_message": "P95 latency still above 30s — check LLM provider and agent handoff performance",
            "silenced": {},
        },
        "priority": 2,
    }


def get_all_monitors() -> list[dict[str, Any]]:
    """Return all monitor definitions."""
    return [
        build_queue_depth_monitor(),
        build_error_rate_monitor(),
        build_latency_p95_monitor(),
    ]


def validate_monitors() -> list[str]:
    """Validate monitor configs — returns list of error messages (empty = OK)."""
    errors: list[str] = []
    for mon in get_all_monitors():
        name = mon["name"]
        if not mon.get("query"):
            errors.append(f"Monitor '{name}' has no query")
        if ">" not in mon.get("query", ""):
            errors.append(f"Monitor '{name}' query missing threshold operator")
        if "@pagerduty" not in mon.get("message", ""):
            errors.append(f"Monitor '{name}' missing PagerDuty notification")
    return errors


def export_monitors() -> str:
    """Export all monitor definitions as pretty-printed JSON."""
    return json.dumps({"monitors": get_all_monitors()}, indent=2)


def create_monitors(api_key: str, app_key: str, site: str) -> list[dict[str, Any]]:
    """Create monitors in Datadog via API.

    Returns list of created monitor responses.
    """
    import httpx

    headers = {
        "DD-API-KEY": api_key,
        "DD-APPLICATION-KEY": app_key,
        "Content-Type": "application/json",
    }
    base_url = f"https://api.{site}/api/v1"
    created: list[dict[str, Any]] = []

    for monitor in get_all_monitors():
        try:
            resp = httpx.post(
                f"{base_url}/monitor",
                headers=headers,
                json=monitor,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            created.append(data)
            logger.info(
                "Monitor created — id=%s, name='%s'",
                data.get("id"),
                monitor["name"],
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Failed to create monitor '%s': %s — %s",
                monitor["name"],
                exc.response.status_code,
                exc.response.text,
            )
        except httpx.RequestError as exc:
            logger.error(
                "Request failed for monitor '%s': %s",
                monitor["name"],
                exc,
            )
    return created


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Datadog monitor management")
    parser.add_argument(
        "action",
        choices=["create", "validate", "export"],
        help="Action to perform",
    )
    args = parser.parse_args()

    if args.action == "validate":
        errors = validate_monitors()
        if errors:
            logger.error("Validation errors:\n  - %s", "\n  - ".join(errors))
            sys.exit(1)
        logger.info("All %d monitors validated OK", len(get_all_monitors()))
        return

    if args.action == "export":
        print(export_monitors())
        return

    if args.action == "create":
        api_key = os.environ.get("DD_API_KEY")
        app_key = os.environ.get("DD_APP_KEY")
        if not api_key or not app_key:
            logger.critical("DD_API_KEY and DD_APP_KEY must be set")
            sys.exit(1)
        site = os.environ.get("DD_SITE", "datadoghq.com")
        created = create_monitors(api_key, app_key, site)
        logger.info("Created %d/%d monitors", len(created), len(get_all_monitors()))


if __name__ == "__main__":
    main()
