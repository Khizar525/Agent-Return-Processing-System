# Tracing Dashboard

**Owner:** Member 5  
**Due:** Week 7  

## Overview

The Datadog tracing dashboard surfaces real-time observability for the Agent 01 multi-agent system. It is configured via the Datadog UI or API using the monitors and metrics defined in `infra/datadog_setup.py`, `infra/datadog_monitors.py`, and `infra/csat_pipeline.py`.

## Dashboard Panels

| Panel | Metric Source | Widget Type | Alert Threshold |
|-------|--------------|-------------|----------------|
| Queue Depth | `kafka.consumer_lag{topic:*}` per channel | Timeseries × 4 (overlay) | > 500 → PagerDuty |
| Error Rate | `trace.fastapi.request.errors` / `trace.fastapi.request.hits` × 100 | Timeseries | > 5% → PagerDuty |
| P95 Latency | `trace.agent.resolution.duration_seconds.p95` | Timeseries | > 30s → PagerDuty |
| CSAT Rolling Score | `agent01.csat.rolling_score` (custom metric) | Timeseries + Gauge | < 4.0 → alert |
| Agent Chain Breakdown | `agent_chain.count` from `record_resolution()` spans | Top List | informational |
| Handoff Count per Intent | Handoff span count grouped by `agent.handoff` tag | Pie Chart | informational |
| Tool Call Latency | `duration` on `tool_call.*` spans | Timeseries (p50/p95/p99) | informational |
| Cost per Ticket | LLM token usage × price (est. via custom metric) | Timeseries | > $0.30 → alert |

## Service Map

All 6 agents appear as separate services in the Datadog APM service map:

| Service Name | Agent | Source Module |
|-------------|-------|---------------|
| `agent01-triage` | Triage Orchestrator | `app_agents/triage_orchestrator.py` |
| `agent01-policy` | Policy Agent | `app_agents/policy_agent.py` |
| `agent01-resolution` | Resolution Agent | `app_agents/resolution_agent.py` |
| `agent01-billing` | Billing Agent | `agents/billing_agent.py` |
| `agent01-communication` | Communication Agent | `app_agents/communication_agent.py` |
| `agent01-escalation` | Escalation Agent | `app_agents/escalation_agent.py` |

Trace propagation flows:
- `agent01-triage` (entry) → handoff to any downstream agent
- Each handoff creates a span tagged with `agent.handoff: source→target`
- Tool calls create child spans tagged with `tool.name`

## Dashboard JSON Export

To export the dashboard configuration from Datadog:

```bash
# List dashboards
curl -s -X GET "https://api.datadoghq.com/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.dashboards[] | select(.title | contains("Agent 01"))'

# Export a specific dashboard by ID
curl -s -X GET "https://api.datadoghq.com/api/v1/dashboard/{DASHBOARD_ID}" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.' > docs/dashboard-export.json

# Import (create or update):
curl -s -X POST "https://api.datadoghq.com/api/v1/dashboard" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  -H "Content-Type: application/json" \
  -d @docs/dashboard-export.json
```

## PagerDuty Monitor URLs

After creating monitors via `python -m infra.datadog_monitors create`, retrieve URLs:

```bash
# List all monitors
curl -s -X GET "https://api.datadoghq.com/api/v1/monitor" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  | jq '.[] | select(.tags[] | contains("alert:")) | {id, name, url: ("https://app.datadoghq.com/monitor/" + (.id|tostring))}'
```

| Monitor | Threshold | Expected URL Pattern |
|---------|-----------|---------------------|
| Queue Depth > 500 | `kafka.consumer_lag > 500` | `https://app.datadoghq.com/monitor/{id}` |
| Error Rate > 5% | `error_ratio * 100 > 5` | `https://app.datadoghq.com/monitor/{id}` |
| P95 Latency > 30s | `resolution.duration_seconds.p95 > 30` | `https://app.datadoghq.com/monitor/{id}` |

## Screenshot Specification

A screenshot of the live dashboard should include:

1. **Header area**: Datadog dashboard title "Agent 01 — Production Observability"
2. **Top row**: 4 graph widgets showing Kafka consumer lag per channel (web_chat, email, whatsapp, sms) with the 500-threshold line visible
3. **Second row**: Error rate % as a stacked timeseries, P95 latency as a single line with 30s threshold
4. **Third row**: CSAT rolling score gauge at 4.5 target, agent chain breakdown as a top-list
5. **Bottom row**: Tool call latency p50/p95/p99, handoff count pie chart
6. **Right sidebar**: Active PagerDuty alerts (should be 0 under normal conditions)

## Confirmation Checklist

- [x] `ddtrace` is configured at application startup via `infra/datadog_setup.py`
- [x] All 6 agents are instrumented with separate `agent.*.name` and `agent.*.service` span tags
- [x] 3 PagerDuty monitors defined in `infra/datadog_monitors.py`
- [x] CSAT rolling metric submitted via `infra/csat_pipeline.py`
- [x] Datadog API `DD_API_KEY` and `DD_APP_KEY` set via environment variables (never hardcoded)
- [ ] Screenshot attached (post-deployment)
- [ ] Dashboard JSON exported to `docs/dashboard-export.json` (post-deployment)
- [ ] PagerDuty monitor URLs verified (post-deployment)
