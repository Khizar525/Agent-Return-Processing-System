"""
Datadog APM Instrumentation
Owner: Member 5

Instruments the FastAPI app and all agent tool calls with Datadog APM.
Configures the service map to show all 6 agents as separate services.

Setup:
    Call `configure_datadog()` at application startup (in main.py).

Environment variables required:
    DD_API_KEY
    DD_APP_KEY
    DD_SERVICE   (default: "agent01-customer-support")
    DD_ENV       (default: "production")

Traces to capture per ticket:
    - agent_chain (sequence of agent handoffs)
    - per-tool call latency
    - intent classification time
    - full resolution time

PagerDuty alert thresholds (configure in Datadog monitors):
    1. Queue depth        > 500 messages
    2. Error rate         > 5%
    3. P95 latency        > 30 seconds
"""

# TODO (Member 5): implement configure_datadog() below
