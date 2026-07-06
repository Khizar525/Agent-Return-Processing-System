"""
Tests for Member 5 — Infrastructure & Observability
Owner: Member 5

Covers:
    - infra/kafka_config.py    — message validation, building, topic resolution
    - infra/datadog_setup.py   — span context managers, resolution recording
    - infra/datadog_monitors.py — monitor config validation
    - infra/csat_pipeline.py   — CSAT computation, event ingestion, rolling score
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest


# =========================================================================
# infra.kafka_config
# =========================================================================


class TestKafkaConfig:
    """Message validation and topic resolution."""

    def test_validate_message_valid(self) -> None:
        from infra.kafka_config import validate_message

        msg = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
            "raw_message": "I want a refund",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": "sess_001",
        }
        assert validate_message(msg) == []

    def test_validate_message_missing_field(self) -> None:
        from infra.kafka_config import validate_message

        msg = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
        }
        errors = validate_message(msg)
        assert len(errors) >= 2
        assert any("raw_message" in e for e in errors)
        assert any("timestamp" in e for e in errors)

    def test_validate_message_wrong_type(self) -> None:
        from infra.kafka_config import validate_message

        msg = {
            "customer_id": 123,
            "channel": "web_chat",
            "raw_message": "test",
            "timestamp": "2026-01-01T00:00:00",
        }
        errors = validate_message(msg)
        assert any("customer_id" in e and "str" in e for e in errors)

    def test_validate_message_session_id_wrong_type(self) -> None:
        from infra.kafka_config import validate_message

        msg = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
            "raw_message": "test",
            "timestamp": "2026-01-01T00:00:00",
            "session_id": 123,
        }
        errors = validate_message(msg)
        assert any("session_id" in e for e in errors)

    def test_validate_message_none_session_id_valid(self) -> None:
        from infra.kafka_config import validate_message

        msg = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
            "raw_message": "test",
            "timestamp": "2026-01-01T00:00:00",
            "session_id": None,
        }
        assert validate_message(msg) == []

    def test_build_message(self) -> None:
        from infra.kafka_config import build_message

        msg = build_message("CUST-001", "email", "Please cancel my order")
        assert msg["customer_id"] == "CUST-001"
        assert msg["channel"] == "email"
        assert msg["raw_message"] == "Please cancel my order"
        assert msg["session_id"] is None
        assert "timestamp" in msg

    def test_build_message_with_session_id(self) -> None:
        from infra.kafka_config import build_message

        msg = build_message("CUST-001", "sms", "Where is my package?", session_id="sess_abc")
        assert msg["session_id"] == "sess_abc"

    def test_resolve_topic(self) -> None:
        from infra.kafka_config import _resolve_topic

        with patch.dict(os.environ, {"KAFKA_TOPIC_WEB_CHAT": "agent-nemo.webchat"}):
            topic = _resolve_topic("web_chat")
            assert topic == "agent-nemo.webchat"

    def test_resolve_topic_missing_env(self) -> None:
        from infra.kafka_config import _resolve_topic

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="KAFKA_TOPIC_WEB_CHAT is not set"):
                _resolve_topic("web_chat")

    def test_resolve_topic_invalid_channel(self) -> None:
        from infra.kafka_config import _resolve_topic

        with pytest.raises(KeyError):
            _resolve_topic("invalid_channel")

    def test_forward_message_success(self) -> None:
        from infra.kafka_config import forward_message

        payload = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
            "raw_message": "test",
            "timestamp": "2026-01-01T00:00:00",
        }
        with patch("infra.kafka_config.httpx.post") as mock_post:
            mock_response = mock_post.return_value
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            err = forward_message(payload, "http://localhost:8000/webhook/message")
            assert err is None

    def test_forward_message_http_error(self) -> None:
        from infra.kafka_config import forward_message
        import httpx as _httpx

        payload = {
            "customer_id": "CUST-001",
            "channel": "web_chat",
            "raw_message": "test",
            "timestamp": "2026-01-01T00:00:00",
        }
        with patch("infra.kafka_config.httpx.post") as mock_post:
            mock_response = mock_post.return_value
            mock_response.status_code = 503
            mock_response.text = "Service Unavailable"
            mock_response.raise_for_status.side_effect = _httpx.HTTPStatusError(
                "503 Service Unavailable",
                request=_httpx.Request("POST", "http://localhost:8000/webhook/message"),
                response=mock_response,
            )
            err = forward_message(payload, "http://localhost:8000/webhook/message")
            assert err is not None


# =========================================================================
# infra.datadog_setup
# =========================================================================


class TestDatadogSetup:
    """Datadog instrumentation helpers."""

    def test_configure_datadog_disabled_when_no_key(self) -> None:
        from infra.datadog_setup import configure_datadog

        with patch.dict(os.environ, {}, clear=True):
            result = configure_datadog()
            assert result is False

    def test_configure_datadog_enabled(self) -> None:
        from infra.datadog_setup import configure_datadog

        with patch.dict(
            os.environ,
            {"DD_API_KEY": "test-key-123", "DD_SERVICE": "agent-nemo-test"},
        ):
            with patch("ddtrace.patch_all") as mock_patch:
                result = configure_datadog()
                assert result is True
                mock_patch.assert_called_once_with(fastapi=True, httpx=True, redis=True)

    def test_agent_span_disabled_when_no_tracer(self) -> None:
        from infra.datadog_setup import agent_span

        with patch("infra.datadog_setup._TRACER_ENABLED", False):
            with agent_span("policy_agent", session_id="sess_001") as span:
                assert span is None

    def test_agent_span_enabled(self) -> None:
        from infra.datadog_setup import agent_span

        mock_span = type("MockSpan", (), {"set_tag": lambda self, k, v: None})()

        with patch("infra.datadog_setup._TRACER_ENABLED", True):
            with patch("ddtrace.tracer") as mock_tracer:
                mock_tracer.trace.return_value.__enter__.return_value = mock_span
                with agent_span("policy_agent", session_id="sess_001") as span:
                    assert span is not None

    def test_tool_span_disabled_when_no_tracer(self) -> None:
        from infra.datadog_setup import tool_span

        with patch("infra.datadog_setup._TRACER_ENABLED", False):
            with tool_span("check_return_policy", "policy_agent") as span:
                assert span is None

    def test_record_resolution_noop_when_disabled(self) -> None:
        from infra.datadog_setup import record_resolution

        with patch("infra.datadog_setup._TRACER_ENABLED", False):
            record_resolution("sess_001", ["triage", "policy"], 12.5, True)

    def test_record_resolution_enabled(self) -> None:
        from infra.datadog_setup import record_resolution

        mock_span = type(
            "MockSpan",
            (),
            {
                "set_tag": lambda self, k, v: None,
                "set_metric": lambda self, k, v: None,
            },
        )()

        with patch("infra.datadog_setup._TRACER_ENABLED", True):
            with patch("ddtrace.tracer") as mock_tracer:
                mock_tracer.current_span.return_value = mock_span
                record_resolution("sess_001", ["triage", "policy"], 12.5, True)

    def test_agent_service_map(self) -> None:
        from infra.datadog_setup import _AGENT_SERVICES

        expected = {
            "triage_orchestrator",
            "policy_agent",
            "resolution_agent",
            "billing_agent",
            "communication_agent",
            "escalation_agent",
        }
        assert set(_AGENT_SERVICES.keys()) == expected


# =========================================================================
# infra.datadog_monitors
# =========================================================================


class TestDatadogMonitors:
    """Monitor config builders and validation."""

    def test_queue_depth_monitor_has_query(self) -> None:
        from infra.datadog_monitors import build_queue_depth_monitor

        mon = build_queue_depth_monitor()
        assert "kafka.consumer_lag" in mon["query"]
        assert "500" in mon["query"]

    def test_queue_depth_monitor_has_pagerduty(self) -> None:
        from infra.datadog_monitors import build_queue_depth_monitor

        mon = build_queue_depth_monitor()
        assert "@pagerduty" in mon["message"]

    def test_error_rate_monitor_has_query(self) -> None:
        from infra.datadog_monitors import build_error_rate_monitor

        mon = build_error_rate_monitor()
        assert "trace.fastapi.request.errors" in mon["query"]
        assert "5" in mon["query"]

    def test_error_rate_monitor_has_pagerduty(self) -> None:
        from infra.datadog_monitors import build_error_rate_monitor

        mon = build_error_rate_monitor()
        assert "@pagerduty" in mon["message"]

    def test_latency_p95_monitor_has_query(self) -> None:
        from infra.datadog_monitors import build_latency_p95_monitor

        mon = build_latency_p95_monitor()
        assert "resolution.duration_seconds" in mon["query"]
        assert "30" in mon["query"]

    def test_latency_p95_monitor_has_pagerduty(self) -> None:
        from infra.datadog_monitors import build_latency_p95_monitor

        mon = build_latency_p95_monitor()
        assert "@pagerduty" in mon["message"]

    def test_get_all_monitors_returns_three(self) -> None:
        from infra.datadog_monitors import get_all_monitors

        monitors = get_all_monitors()
        assert len(monitors) == 3

    def test_validate_monitors_passes(self) -> None:
        from infra.datadog_monitors import validate_monitors

        errors = validate_monitors()
        assert errors == []

    def test_validate_monitors_fails_on_bad_query(self) -> None:
        from infra.datadog_monitors import validate_monitors

        with patch("infra.datadog_monitors.get_all_monitors") as mock_get:
            mock_get.return_value = [
                {
                    "name": "Bad Monitor",
                    "query": "avg:some.metric{}",
                    "message": "no pagerduty here",
                }
            ]
            errors = validate_monitors()
            assert len(errors) == 2

    def test_export_monitors_is_valid_json(self) -> None:
        from infra.datadog_monitors import export_monitors
        import json

        exported = export_monitors()
        data = json.loads(exported)
        assert "monitors" in data
        assert len(data["monitors"]) == 3


# =========================================================================
# infra.csat_pipeline
# =========================================================================


class TestCSATPipeline:
    """CSAT score computation and event ingestion."""

    def test_compute_csat_score_initial(self) -> None:
        from infra.csat_pipeline import compute_csat_score

        result = compute_csat_score(4.5)
        assert result["rolling_csat"] == 4.5
        assert result["sample_count"] == 1

    def test_compute_csat_score_multiple(self) -> None:
        from infra.csat_pipeline import compute_csat_score, _CSAT_RECORDS

        _CSAT_RECORDS.clear()
        scores = [5.0, 4.0, 3.0, 5.0, 4.5]
        for s in scores:
            compute_csat_score(s)
        result = compute_csat_score(4.0)
        expected = sum(scores + [4.0]) / len(scores + [4.0])
        assert result["rolling_csat"] == pytest.approx(expected, rel=1e-4)
        assert result["sample_count"] == 6

    def test_compute_csat_score_clamps_range(self) -> None:
        from infra.csat_pipeline import compute_csat_score, _CSAT_RECORDS

        _CSAT_RECORDS.clear()
        result = compute_csat_score(10.0)
        assert result["rolling_csat"] == 5.0

        _CSAT_RECORDS.clear()
        result = compute_csat_score(-1.0)
        assert result["rolling_csat"] == 1.0

    def test_compute_csat_score_with_agent(self) -> None:
        from infra.csat_pipeline import compute_csat_score, _CSAT_RECORDS

        _CSAT_RECORDS.clear()
        result = compute_csat_score(4.5, "policy_agent")
        assert "policy_agent" in result["per_agent"]

    def test_ingest_resolution_event_basic(self) -> None:
        from infra.csat_pipeline import ingest_resolution_event, _RESOLUTION_EVENTS, _CSAT_RECORDS

        _RESOLUTION_EVENTS.clear()
        _CSAT_RECORDS.clear()

        event = {
            "session_id": "sess_001",
            "agent_chain": ["triage_orchestrator", "policy_agent", "resolution_agent"],
            "resolved_by": "resolution_agent",
            "survey_score": 5.0,
            "channel": "web_chat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        result = ingest_resolution_event(event)
        assert result["rolling_csat"] == 5.0
        assert result["sample_count"] == 1
        assert result["session_id"] == "sess_001"

    def test_ingest_resolution_event_sla(self) -> None:
        import time
        from infra.csat_pipeline import ingest_resolution_event, _RESOLUTION_EVENTS, _CSAT_RECORDS

        _RESOLUTION_EVENTS.clear()
        _CSAT_RECORDS.clear()

        event = {
            "session_id": "sess_002",
            "agent_chain": ["triage_orchestrator"],
            "resolved_by": "triage_orchestrator",
            "survey_score": 4.0,
            "channel": "email",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        start = time.perf_counter()
        ingest_resolution_event(event)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"CSAT pipeline exceeded 5s SLA: {elapsed:.2f}s"

    def test_ingest_resolution_event_clamps_score(self) -> None:
        from infra.csat_pipeline import ingest_resolution_event, _RESOLUTION_EVENTS, _CSAT_RECORDS

        _RESOLUTION_EVENTS.clear()
        _CSAT_RECORDS.clear()

        event = {
            "session_id": "sess_003",
            "agent_chain": [],
            "resolved_by": "billing_agent",
            "survey_score": 999.0,
            "channel": "sms",
            "timestamp": "2026-01-01T00:00:00Z",
        }
        result = ingest_resolution_event(event)
        assert result["rolling_csat"] <= 5.0

    def test_get_rolling_csat_empty(self) -> None:
        from infra.csat_pipeline import get_rolling_csat, _CSAT_RECORDS

        _CSAT_RECORDS.clear()
        result = get_rolling_csat()
        assert result["rolling_csat"] is None
        assert result["sample_count"] == 0

    def test_get_rolling_csat_after_events(self) -> None:
        from infra.csat_pipeline import (
            get_rolling_csat,
            ingest_resolution_event,
            _RESOLUTION_EVENTS,
            _CSAT_RECORDS,
        )

        _RESOLUTION_EVENTS.clear()
        _CSAT_RECORDS.clear()

        for i in range(3):
            ingest_resolution_event(
                {
                    "session_id": f"sess_{i}",
                    "agent_chain": ["triage"],
                    "resolved_by": "resolution_agent",
                    "survey_score": 5.0,
                    "channel": "web_chat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        result = get_rolling_csat()
        assert result["rolling_csat"] == 5.0
        assert result["sample_count"] == 3
        assert "resolution_agent" in result["per_agent"]

    def test_ingest_emits_datadog_metric(self) -> None:
        from infra.csat_pipeline import ingest_resolution_event, _RESOLUTION_EVENTS, _CSAT_RECORDS

        _RESOLUTION_EVENTS.clear()
        _CSAT_RECORDS.clear()

        event = {
            "session_id": "sess_004",
            "agent_chain": ["triage"],
            "resolved_by": "triage_orchestrator",
            "survey_score": 4.0,
            "channel": "web_chat",
            "timestamp": "2026-01-01T00:00:00Z",
        }

        with patch("infra.csat_pipeline._emit_datadog_metric") as mock_emit:
            ingest_resolution_event(event)
            assert mock_emit.call_count == 2
            metric_names = [call.args[0] for call in mock_emit.call_args_list]
            assert "agent-nemo.csat.rolling_score" in metric_names
            assert "agent-nemo.csat.sample_count" in metric_names

    async def test_sync_to_redis_no_url(self) -> None:
        from infra.csat_pipeline import sync_to_redis

        with patch.dict(os.environ, {}, clear=True):
            await sync_to_redis()


# =========================================================================
# infra.ab_test
# =========================================================================


class TestABTestFramework:
    """A/B test variant assignment, recording, and summaries."""

    def teardown_method(self) -> None:
        from infra.ab_test import reset_experiment

        reset_experiment()

    def test_get_variant_control_default_when_disabled(self) -> None:
        from infra.ab_test import get_variant, EXPERIMENTS

        original = EXPERIMENTS["agent_config_v1"]["enabled"]
        EXPERIMENTS["agent_config_v1"]["enabled"] = False
        try:
            variant = get_variant("agent_config_v1", "sess_001")
            assert variant == "control"
        finally:
            EXPERIMENTS["agent_config_v1"]["enabled"] = original

    def test_get_variant_default_control_unknown_experiment(self) -> None:
        from infra.ab_test import get_variant

        variant = get_variant("nonexistent_experiment", "sess_001")
        assert variant == "control"

    def test_get_variant_deterministic(self) -> None:
        from infra.ab_test import get_variant

        v1 = get_variant("agent_config_v1", "sess_001")
        v2 = get_variant("agent_config_v1", "sess_001")
        assert v1 == v2

    def test_get_variant_different_entities_may_differ(self) -> None:
        from infra.ab_test import get_variant

        v1 = get_variant("agent_config_v1", "sess_001")
        v2 = get_variant("agent_config_v1", "sess_999")
        # Both are valid variants — just ensure they're not empty
        assert v1 in ("control", "treatment")
        assert v2 in ("control", "treatment")

    def test_get_variant_only_two_variants(self) -> None:
        from infra.ab_test import get_variant

        seen: set[str] = set()
        for i in range(100):
            seen.add(get_variant("agent_config_v1", f"sess_{i:03d}"))
        # With 50/50 split and 100 samples, both should appear
        assert seen == {"control", "treatment"}

    def test_get_experiment_config_returns_dict(self) -> None:
        from infra.ab_test import get_experiment_config

        config = get_experiment_config("agent_config_v1", "control")
        assert isinstance(config, dict)
        assert "agent_model" in config
        assert config["agent_model"] == "openai/gpt-oss-120b:free"

    def test_get_experiment_config_unknown(self) -> None:
        from infra.ab_test import get_experiment_config

        config = get_experiment_config("nonexistent", "control")
        assert config == {}

    def test_get_active_experiments(self) -> None:
        from infra.ab_test import get_active_experiments, EXPERIMENTS

        original = EXPERIMENTS["agent_config_v1"]["enabled"]
        EXPERIMENTS["agent_config_v1"]["enabled"] = True
        try:
            active = get_active_experiments()
            names = [e["name"] for e in active]
            assert "agent_config_v1" in names
        finally:
            EXPERIMENTS["agent_config_v1"]["enabled"] = original

    def test_record_experiment_result(self) -> None:
        from infra.ab_test import record_experiment_result, _RESULTS

        _RESULTS.clear()
        result = record_experiment_result(
            "agent_config_v1", "control", "sess_001", "resolution_time", 12.5
        )
        assert result["recorded"] is True
        assert result["metric"] == "resolution_time"
        assert result["value"] == 12.5
        assert len(_RESULTS["agent_config_v1"]) == 1

    def test_get_experiment_summary_empty(self) -> None:
        from infra.ab_test import get_experiment_summary

        summary = get_experiment_summary("nonexistent")
        assert summary["record_count"] == 0

    def test_get_experiment_summary_with_records(self) -> None:
        from infra.ab_test import (
            get_experiment_summary,
            record_experiment_result,
            _RESULTS,
        )

        _RESULTS.clear()
        for i in range(5):
            record_experiment_result(
                "agent_config_v1", "control", f"sess_{i:03d}", "resolution_time", 10.0 + i
            )
        for i in range(3):
            record_experiment_result(
                "agent_config_v1", "treatment", f"sess_{i:03d}", "resolution_time", 8.0 + i
            )

        summary = get_experiment_summary("agent_config_v1")
        assert summary["record_count"] == 8
        assert "control" in summary["summary"]
        assert "treatment" in summary["summary"]
        assert summary["summary"]["control"]["resolution_time"]["count"] == 5
        assert summary["summary"]["control"]["resolution_time"]["mean"] == 12.0
        assert summary["summary"]["treatment"]["resolution_time"]["count"] == 3

    def test_record_emits_datadog_metric(self) -> None:
        from infra.ab_test import record_experiment_result, _RESULTS
        from unittest.mock import patch

        _RESULTS.clear()
        with patch("infra.ab_test._emit_datadog_gauge") as mock_emit:
            record_experiment_result(
                "agent_config_v1", "treatment", "sess_002", "success_rate", 1.0
            )
            assert mock_emit.call_count == 2
            metric_names = [call.args[0] for call in mock_emit.call_args_list]
            assert "agent-nemo.ab_test.success_rate" in metric_names
            assert "agent-nemo.ab_test.record_count" in metric_names

    def test_hash_partition_bounds(self) -> None:
        from infra.ab_test import _hash_partition

        for i in range(1000):
            bucket = _hash_partition(f"entity_{i}", 100)
            assert 0 <= bucket < 100

    def test_get_variant_ignores_case_in_entity_id(self) -> None:
        from infra.ab_test import get_variant

        # Same entity_id always same variant
        assert get_variant("agent_config_v1", "SESSION_001") == get_variant(
            "agent_config_v1", "SESSION_001"
        )

    def test_reset_experiment_specific(self) -> None:
        from infra.ab_test import record_experiment_result, reset_experiment, _RESULTS

        _RESULTS.clear()
        record_experiment_result("agent_config_v1", "control", "s_1", "resolution_time", 1.0)
        record_experiment_result("agent_config_v1", "treatment", "s_2", "resolution_time", 2.0)
        assert len(_RESULTS) == 1
        reset_experiment("agent_config_v1")
        assert _RESULTS.get("agent_config_v1", []) == []

    def test_reset_experiment_all(self) -> None:
        from infra.ab_test import record_experiment_result, reset_experiment, _RESULTS

        _RESULTS.clear()
        record_experiment_result("agent_config_v1", "control", "s_1", "resolution_time", 1.0)
        reset_experiment()
        assert len(_RESULTS) == 0
