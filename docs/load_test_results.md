# Load Test Results

**Owner:** Member 5  
**Due:** Week 8  
**Test Date:** TBD (post-deployment)  

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Concurrent tickets | 1,000 |
| Test duration | 10 minutes |
| Ramp-up period | 60 seconds |
| Channels tested | web_chat, email, whatsapp, sms (250 each) |
| Tool | k6 (or Locust as fallback) |
| Environment | Staging Kubernetes cluster (4-node, 4 vCPU / 8 GB each) |
| LLM Model | deepseek-v4-flash-free (as configured in ADR-001) |

## Test Script

The load test script (`tests/load_test.js`) sends messages to the FastAPI webhook endpoint with randomized customer IDs and order IDs across all 4 channels. Each virtual user:
1. POSTs a return-request message to `/webhook/message`
2. Waits for the `ResolutionResponse` (polling up to 60s)
3. Validates response schema (session_id, resolution, agent_chain)
4. Measures end-to-end resolution latency

## Pass/Fail Criteria

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| P95 Full Resolution Time | < 30 seconds | TBD | ⏳ |
| P99 First Response Time | < 5 seconds | TBD | ⏳ |
| Error Rate | < 1% | TBD | ⏳ |
| Throughput | > 100 tickets/min | TBD | ⏳ |
| HPA scale-out triggered | Yes (queue > 100/pod) | TBD | ⏳ |
| No secrets in logs | Zero occurrences | TBD | ⏳ |

## Throughput Analysis

| Time Window | Requests Sent | Success | Errors | Avg Latency |
|-------------|--------------|---------|--------|-------------|
| 0-2 min | TBD | TBD | TBD | TBD |
| 2-4 min | TBD | TBD | TBD | TBD |
| 4-6 min | TBD | TBD | TBD | TBD |
| 6-8 min | TBD | TBD | TBD | TBD |
| 8-10 min | TBD | TBD | TBD | TBD |

## Latency Percentiles (end-to-end resolution)

| Percentile | Target | Actual | Pass/Fail |
|------------|--------|--------|-----------|
| P50 (median) | — | TBD | — |
| P90 | — | TBD | — |
| P95 | < 30s | TBD | ⏳ |
| P99 | < 60s | TBD | — |
| Max | — | TBD | — |

## Kubernetes HPA Scaling Verification

| Metric | Observation |
|--------|------------|
| Initial webhook replicas | 2 (min configured) |
| Initial consumer replicas per channel | 1 per channel (4 total) |
| Max webhook replicas reached | TBD |
| Max consumer replicas (any channel) | TBD |
| HPA trigger threshold | Kafka consumer lag > 100/pod |
| Time to first scale-out event | TBD |
| Time to scale-in after load drops | TBD |
| Scaling behavior | TBD (linear / step) |

### HPA Events (from `kubectl describe hpa`)

```
TBD after load test execution
```

## Bottlenecks Discovered

| Issue | Impact | Fix Applied | Status |
|-------|--------|------------|--------|
| TBD | TBD | TBD | ⏳ |

## Chaos Test: PagerDuty Alert Verification

| Alert Rule | Threshold | Chaos Action | Time to Fire | Status |
|------------|-----------|-------------|-------------|--------|
| Queue Depth > 500 | 500 msgs | Pause consumer pods | < 60s? | ⏳ |
| Error Rate > 5% | 5% | Inject bad responses | < 60s? | ⏳ |
| P95 Latency > 30s | 30s | Add artificial delay | < 60s? | ⏳ |

## Raw Results

Raw k6/Locust output CSV should be attached as `docs/load_test_raw.csv` after execution.

```csv
# Example format:
# timestamp, metric, value, tags
# 2026-06-14T10:00:00Z, http_req_duration, 1250, { channel: "web_chat" }
```

## Conclusion

TBD after load test execution.

## TODO

- [ ] Run k6 load test against staging environment
- [ ] Populate results tables above
- [ ] Attach raw results CSV as `docs/load_test_raw.csv`
- [ ] Document any bottlenecks discovered and fixes applied
- [ ] Verify all 3 PagerDuty alerts fire within 60s threshold
- [ ] Verify HPA scales > 1 pod when queue depth exceeds 100
- [ ] Run `ruff check . --fix && mypy . && pytest tests/ -v` before PR
