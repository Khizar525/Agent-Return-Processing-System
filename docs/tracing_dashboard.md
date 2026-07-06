# Tracing Dashboard — Agent Nemo Customer Support & Returns Orchestrator

**Member 5 — Infrastructure & Observability**  
**Branch:** `feature/infra-observability`  
**Last Updated:** 2026-06-23  

---

## Overview

The Agent Nemo tracing dashboard provides end-to-end visibility into every customer ticket as it flows through the multi-agent pipeline. Built on **Datadog APM** with **OpenAI Agents SDK** built-in tracing, the dashboard surfaces agent chains, handoff counts, tool call latency, and CSAT scores in real time.

---

## Dashboard Panels

### Panel 1 — Agent Chain per Ticket

**Widget type:** Trace Flame Graph  
**Service:** `agent-nemo-customer-support`  
**Query:** `service:agent-nemo-customer-support resource_name:handle_customer_message`

**What it shows:**
- Full trace of every inbound ticket from webhook receipt to final resolution
- Each span represents one agent or tool call in the pipeline
- Color-coded by agent: Triage (blue) → Policy (green) → Resolution (teal) → Communication (purple) → Escalation (red)
- Span duration shown in milliseconds
- Errors highlighted in red

**Key spans tracked:**

| Span Name | Description |
|---|---|
| `triage.handle_customer_message` | Entry point — intent classification |
| `policy.check_return_eligibility` | Policy agent — return window, fraud check |
| `resolution.process_refund` | Resolution agent — refund or replacement |
| `communication.send_response` | Communication agent — email/SMS/chat |
| `escalation.handoff_to_human` | Escalation agent — human queue handoff |
| `guardrail.pii_scrubber` | PII redaction guardrail |
| `guardrail.sentiment_monitor` | Sentiment scoring guardrail |
| `guardrail.refund_cap` | Refund cap enforcement guardrail |

---

### Panel 2 — Handoff Count per Ticket

**Widget type:** Distribution Histogram  
**Metric:** `trace.agent-nemo.handoff.count`  
**Group by:** `ticket_id`, `channel`

**What it shows:**
- Number of agent-to-agent handoffs per ticket
- Target: ≤ 2 handoffs for Tier 1 tickets (80% of volume)
- Escalation tickets: 3–4 handoffs expected
- Spike in handoffs = signal for policy agent tuning

**Thresholds:**

| Handoff Count | Classification | Action |
|---|---|---|
| 1 | Direct resolution | ✅ Optimal |
| 2 | Standard flow | ✅ Normal |
| 3 | Complex ticket | ⚠️ Monitor |
| 4+ | Escalation path | 🔴 Review |

---

### Panel 3 — Tool Call Latency

**Widget type:** Timeseries Line Chart  
**Metric:** `trace.agent-nemo.tool.duration`  
**Percentiles:** P50, P95, P99  
**Group by:** `tool_name`

**Tools monitored:**

| Tool | P50 Target | P95 Target | P99 Alert |
|---|---|---|---|
| `check_return_policy` | < 50ms | < 200ms | > 500ms |
| `process_refund` | < 100ms | < 500ms | > 1000ms |
| `send_email_notification` | < 200ms | < 800ms | > 2000ms |
| `send_sms_notification` | < 150ms | < 600ms | > 1500ms |
| `get_customer_profile` | < 30ms | < 100ms | > 300ms |
| `get_order_details` | < 30ms | < 100ms | > 300ms |
| `check_fraud_signals` | < 50ms | < 200ms | > 500ms |

---

### Panel 4 — End-to-End Resolution Time

**Widget type:** Timeseries + SLA Burn Rate  
**Metric:** `trace.agent-nemo.ticket.duration`  
**SLA target:** P95 < 30 seconds

**Breakdown by channel:**

| Channel | P50 | P95 Target | SLA |
|---|---|---|---|
| web_chat | 8s | < 30s | ✅ |
| email | 12s | < 30s | ✅ |
| whatsapp | 10s | < 30s | ✅ |
| sms | 9s | < 30s | ✅ |

---

### Panel 5 — CSAT Score (Rolling)

**Widget type:** Gauge + Timeseries  
**Source:** `infra/csat_pipeline.py` consuming `log_resolution` events  
**Target:** > 4.5 / 5.0

**CSAT pipeline flow:**
```
Ticket resolved → log_resolution event fired → 
csat_pipeline.py consumes event → 
rolling score computed within 5 seconds → 
score published to Datadog metric: agent-nemo.csat.score
```

**Score bands:**

| Score | Status |
|---|---|
| 4.5 – 5.0 | ✅ Target met |
| 4.0 – 4.4 | ⚠️ Monitor |
| < 4.0 | 🔴 Alert — PagerDuty fires |

---

### Panel 6 — Error Rate & Throughput

**Widget type:** Dual-axis Timeseries  
**Metrics:**
- `trace.agent-nemo.errors` (error rate %)
- `trace.agent-nemo.requests` (requests/minute)

**Alert thresholds (PagerDuty):**

| Metric | Warning | Critical |
|---|---|---|
| Error rate | > 2% | > 5% |
| Queue depth | > 300 msgs | > 500 msgs |
| P95 latency | > 20s | > 30s |

---

## Dashboard Configuration Export

```json
{
  "title": "Agent Nemo — Observability Dashboard",
  "description": "End-to-end tracing for the Customer Support & Returns Orchestrator",
  "widgets": [
    {
      "id": "agent_chain",
      "type": "trace_service_map",
      "query": "service:agent-nemo-customer-support",
      "title": "Agent Chain per Ticket"
    },
    {
      "id": "handoff_count",
      "type": "distribution",
      "metric": "trace.agent-nemo.handoff.count",
      "group_by": ["ticket_id", "channel"],
      "title": "Handoff Count per Ticket"
    },
    {
      "id": "tool_latency",
      "type": "timeseries",
      "metric": "trace.agent-nemo.tool.duration",
      "percentiles": ["p50", "p95", "p99"],
      "group_by": ["tool_name"],
      "title": "Tool Call Latency"
    },
    {
      "id": "resolution_time",
      "type": "timeseries",
      "metric": "trace.agent-nemo.ticket.duration",
      "sla_threshold": 30000,
      "title": "End-to-End Resolution Time"
    },
    {
      "id": "csat_score",
      "type": "gauge",
      "metric": "agent-nemo.csat.score",
      "min": 0,
      "max": 5,
      "target": 4.5,
      "title": "Rolling CSAT Score"
    },
    {
      "id": "error_rate",
      "type": "timeseries",
      "metric": "trace.agent-nemo.errors",
      "alert_threshold": 0.05,
      "title": "Error Rate & Throughput"
    }
  ],
  "time_range": "last_1h",
  "refresh_interval": "30s",
  "tags": ["service:agent-nemo", "env:production", "team:smit-agent-nemo"]
}
```

---

## Datadog Service Map

The service map shows all 6 agents as separate services with trace propagation:

```
[Kafka Consumer] → [FastAPI Webhook]
                         │
                   [Triage Agent]
                    /     |     \
          [Policy]  [Tools]  [Billing]
              │
          [Resolution] ←── [refund_cap guardrail]
              │
          [Communication] ←── [brand_voice guardrail]
              │
          [Escalation]
```

Each arrow represents a traced handoff with full context propagation via `dd-trace` headers.

---

## Setup Instructions

### 1. Start Datadog Agent locally
```bash
docker run -d --name datadog-agent \
  -e DD_API_KEY=$DD_API_KEY \
  -e DD_SITE=datadoghq.com \
  -p 8126:8126 \
  datadog/agent:latest
```

### 2. Run the instrumented app
```bash
ddtrace-run uvicorn main:app --reload
```

### 3. Open the dashboard
```
https://app.datadoghq.com/apm/services/agent-nemo-customer-support
```

---

*Confidential — Team Internal | Agent Nemo | 2026*
