# Tracing Dashboard

**Owner:** Member 5  
**Due:** Week 7  

## What to document here

After the Datadog tracing dashboard is live, add:

1. A screenshot of the service map (all 6 agents visible as separate services)
2. Export of the dashboard JSON config (so it can be re-imported if lost)
3. The Datadog monitor URLs for the 3 PagerDuty alert thresholds

## Required dashboard panels

| Panel | Metric | Alert Threshold |
|-------|--------|----------------|
| Queue Depth | `kafka_consumer_lag` per topic | > 500 → PagerDuty |
| Error Rate | `trace.fastapi.request.errors` | > 5% → PagerDuty |
| P95 Latency | `trace.agent.resolution.duration.p95` | > 30s → PagerDuty |
| CSAT Rolling Score | custom metric from `csat_pipeline.py` | < 4.0 → alert |
| Agent Chain Breakdown | handoff count per intent type | informational |
| Cost per Ticket | LLM token usage × price | > $0.30 → alert |

## TODO (Member 5)

- [ ] Add dashboard screenshot
- [ ] Add dashboard JSON export
- [ ] Add PagerDuty monitor URLs
- [ ] Confirm all 6 agents appear in service map
