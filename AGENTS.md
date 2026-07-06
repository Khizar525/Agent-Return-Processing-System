# AGENTS.md

**Project:** Agent Nemo — Customer Support & Returns Orchestrator
**Status:** Production-ready — all components implemented and tested
**Branch:** `develop` (integration) | `main` (protected, production)
**Last updated:** 2026-06-24

---

## Commands

```bash
pip install -r requirements.txt         # deps
pip install -e ".[dev]"                # + dev deps (pytest, ruff, mypy)
uvicorn main:app --reload               # dev server
pytest tests/ -v                        # all tests
pytest tests/ --cov -v                  # all tests + coverage
pytest tests/test_policy_agent.py -v -x # single test file
ruff check .                            # lint (line-length=100)
ruff format --check .                   # format check
mypy .                                  # typecheck (strict mode, py311)
```

Run `ruff check . --fix; pytest tests/ -v` before PR.

---

## Architecture

- **Pattern:** Manager + Handoff Hybrid (see `docs/ADR-001.md`)
  - *Tool calls* (tracking, FAQ) keep context with the Triage Orchestrator
  - *Handoffs* (Policy, Billing, Escalation) give full specialist ownership
- **Entry:** `main.py` → FastAPI `POST /webhook/message` → `triage_orchestrator.handle_customer_message()`
- **Model:** `openai/gpt-oss-120b:free` via OpenRouter for all agents (cost-optimized, free tier)

### Triage Orchestrator — Production Architecture

The triage orchestrator uses a **keyword-first, deterministic tool dispatch** pattern:

1. **Keyword classification** (primary): Fast, deterministic, zero-cost intent detection
2. **LLM classification** (enrichment): Optional — provides better reasoning quality when available
3. **Tool dispatch** (deterministic): Code maps intent → tool call (not LLM-dependent)

This avoids the SDK limitation where `Runner.run()` consumes tool call results internally and never exposes them to the caller.

```
Message → Keyword Classifier → Intent
                ↓ (optional enrichment)
         LLM Classifier → Intent + Reasoning
                ↓
         _dispatch_table(intent) → Tool Execution → Result
```

### Routing Table

| Intent | Route | Type | Tool Executed |
|--------|-------|------|---------------|
| `return_request` | `check_return_policy` | Tool call | Yes — eligibility check |
| `order_status` | `tracking_lookup` | Tool call | Yes — tracking status |
| `billing_dispute` | BillingAgent | Handoff | No — specialist ownership |
| `general_inquiry` | `faq_lookup` | Tool call | Yes — FAQ search |
| `edge_case_escalate` | EscalationAgent | Handoff | No — human escalation |

### LLM Provider

- **Provider:** OpenRouter (free tier)
- **Model:** `openai/gpt-oss-120b:free`
- **Rate limits:** 30 RPM, 1K RPD
- **Compatibility patches:** MultiProvider `unknown_prefix_mode="model_id"`, `response_format` stripped when tools present

---

## Agents

All agents live in `app_agents/` and use `Agent(name=..., instructions=..., model=..., tools=[...])`.

| Agent | File | Owner | Model | Tools | Guardrails | Output Type |
|-------|------|-------|-------|-------|------------|-------------|
| **TriageOrchestrator** | `triage_orchestrator.py` | Lead | gpt-oss-120b:free | `get_customer_profile` | PII scrubber (input), Sentiment monitor (input) | `TriageDecision` |
| **PolicyAgent** | `policy_agent.py` | M2 | gpt-oss-120b:free | `check_return_policy`, `get_customer_profile` | — | `PolicyDecision` |
| **ResolutionAgent** | `resolution_agent.py` | M3 | gpt-oss-120b:free | `process_refund`, `create_return_label`, `create_replacement_order` | Refund cap (output) | `ResolutionSummary` |
| **BillingAgent** | `billing_agent.py` | Lead | gpt-oss-120b:free | `process_refund` | Refund cap (output) | `BillingDecision` |
| **CommunicationAgent** | `communication_agent.py` | M4 | gpt-oss-120b:free | `send_notification` | Brand voice (output) | `CommunicationAgentOutput` |
| **EscalationAgent** | `escalation_agent.py` | M4 | gpt-oss-120b:free | `create_human_ticket`, `log_resolution` | — | `EscalationSummary` |

**Note:** The TriageOrchestrator agent is a **classifier only** — it does NOT execute tools. Tools are executed deterministically in `handle_customer_message()` via `_dispatch_tool()`.

---

## Tools

All tools live in `tools/` and use `@function_tool` (openai-agents), `async def`, return dict with `"success": bool, "error": str | None`.

**Raw functions** (for direct calls) are exported as `RAW_<TOOL_NAME>` from each tool module.

| Tool | File | Owner | Signature | Returns |
|------|------|-------|-----------|---------|
| `check_return_policy` | `policy_tools.py` | M2 | `(order_id, customer_id)` | `eligible`, `reason`, `recommended_action`, `return_window_days`, `days_since_purchase`, `item_category`, `exclusion_reason`, `fraud_signal`, `error` |
| `get_customer_profile` | `crm_tools.py` | M3 | `(customer_id)` | `customer_id`, `name`, `email`, `phone`, `loyalty_tier`, `order_history`, `past_returns`, `fraud_flag`, `fraud_reason`, `error` |
| `process_refund` | `payment_tools.py` | M3 | `(order_id, amount_usd, method)` | `success`, `transaction_id`, `refund_amount`, `currency`, `estimated_days`, `error` |
| `create_return_label` | `shipping_tools.py` | M3 | `(order_id, carrier)` | `success`, `label_url`, `tracking_number`, `carrier`, `expires_at`, `error` |
| `create_replacement_order` | `shipping_tools.py` | M3 | `(order_id)` | `success`, `replacement_order_id`, `expedited`, `estimated_delivery`, `error` |
| `send_notification` | `notification_tools.py` | M4 | `(customer_id, channel, subject, body)` | `success`, `message_id`, `channel`, `delivered_at`, `error` |
| `create_human_ticket` | `helpdesk_tools.py` | M4 | `(context_bundle)` | `success`, `ticket_id`, `ticket_url`, `priority`, `error` |
| `log_resolution` | `helpdesk_tools.py` | M4 | `(session_id, outcome)` | `success`, `record_id`, `error` |
| `tracking_lookup` | `tracking_tools.py` | Lead | `(order_id)` | `success`, `found`, `status`, `carrier`, `tracking_number`, `estimated_delivery`, `last_update`, `error` |
| `faq_lookup` | `tracking_tools.py` | Lead | `(query)` | `success`, `matched_keyword`, `answer`, `confidence`, `error` |

---

## Guardrails

All guardrails live in `guardrails/` and use `@input_guardrail` or `@output_guardrail`.

| Guardrail | File | Owner | Type | Wired To | Behaviour |
|-----------|------|-------|------|----------|-----------|
| **PII Scrubber** | `pii_scrubber.py` | M2 | Input | TriageOrchestrator | Replaces credit cards, SSNs, bank accounts with `[REDACTED]` |
| **Sentiment Monitor** | `sentiment_monitor.py` | M2 | Input | TriageOrchestrator | Scores 0.0–1.0; legal keywords (0.4) + ALL CAPS (0.3) → triggers at >= 0.8 |
| **Refund Cap** | `refund_cap.py` | Lead | Output | ResolutionAgent, BillingAgent | Blocks refunds > $500; requires human approval |
| **Brand Voice** | `brand_voice.py` | M4 | Output | CommunicationAgent | Replaces prohibited language; enforces 150-word limit |

### Sentiment Scoring Weights

| Signal | Weight | Example |
|--------|--------|---------|
| ALL CAPS (>10 chars) | +0.3 | "I WILL SUE YOU" |
| Legal keywords | +0.4 | sue, lawyer, attorney, court, legal, litigation |
| Distress keywords | +0.2 | crying, desperate, ruined, outrageous, unacceptable, furious |
| Profanity | +0.2 | fuck, shit, crap, damn, bastard, asshole |
| Multiple exclamations | +0.1–0.2 | "!!!" → +0.1, "!!??" → +0.2 |

**Threshold:** `>= 0.8` triggers escalation. Float precision handled via `round(score, 10)`.

---

## Database

| File | Owner | Purpose |
|------|-------|---------|
| `repository.py` | M2 | Abstract `Repository` ABC with 3 backends: `PostgresBackend`, `FileBackend`, `MemoryBackend` |
| `models.py` | M2 | SQLAlchemy 2.0 ORM: `CustomerModel`, `OrderModel`, `FraudDbMatchModel` |
| `config.py` | Lead | `DATABASE_URL`, `DB_ECHO`, `USE_FILE_BACKEND`, `FILE_DB_PATH` |
| `schema.sql` | M2 | DDL for Postgres |
| `seed.sql` | M2 | Seed data for Postgres |

---

## Infrastructure

| File | Owner | Purpose |
|------|-------|---------|
| `redis_config.py` | Lead | Session store: `get_session`, `save_session`, `archive_session` (TTL: 24h active, 90d archive) |
| `kafka_config.py` | M5 | Consumer per channel (web_chat, email, whatsapp, sms) |
| `datadog_setup.py` | M5 | APM instrumentation: `configure_datadog()`, `agent_span()`, `tool_span()`, `record_resolution()` |
| `datadog_monitors.py` | M5 | 3 PagerDuty-bound monitors: queue depth, error rate, P95 latency |
| `csat_pipeline.py` | M5 | Rolling CSAT score computation with Datadog metric emission |
| `ab_test.py` | M5 | A/B test framework: variant assignment via hash partitioning, result recording, Datadog metric emission, experiment summaries |
| `k8s/` | M5 | Kubernetes manifests: deployment, service, HPA, configmap, secret |

---

## Frontend

| File | Purpose |
|------|---------|
| `frontend/index.html` | State-of-the-art presentation frontend — single HTML file, zero dependencies |

**Features:**
- Dark glassmorphism theme with animated gradient background
- Live chat interface wired to backend API (`POST /webhook/message`)
- Interactive architecture visualization with agent flow diagram
- 6 pre-built scenario runner cards
- 4 interactive guardrail demos (PII, sentiment, refund cap, brand voice)
- Routing pipeline panel with real-time step visualization

**Run:** `python -m http.server 3000` from `frontend/` directory. Backend must be running on port 8000.

---

## Tests

| File | Owner | Tests | Coverage |
|------|-------|-------|----------|
| `test_policy_agent.py` | M2 | 106 | Policy tool, guardrails, agent config, contracts |
| `test_resolution_agent.py` | M3 | 21 | Resolution agent, tool invocation, E2E with mocks |
| `test_billing_agent.py` | Lead | 18 | Billing agent, schema, refund cap enforcement |
| `test_comm_escalation.py` | M4 | 14 | Notifications, brand voice, escalation, helpdesk |
| `test_database.py` | Lead | 37 | DTOs, MemoryBackend, FileBackend, factory |
| `test_infra_observability.py` | M5 | 41 | Kafka, Datadog, monitors, CSAT pipeline |
| `test_tools.py` | M3 | 44 | CRM, payment, shipping tools with respx mocks |
| `test_integration.py` | Lead | 40 | Fixture integrity, policy tool, tracking, FAQ, session, intent mapping, pipeline skeletons |
| `test_tracking_tools.py` | Lead | 32 | Tracking lookup, FAQ lookup, contracts, edge cases |

**Run all:** `pytest tests/ -v` (353 passed, 0 skipped)

---

## Code Conventions

- Every file: module docstring with owner, purpose, output schema.
- All tools: `@function_tool` (openai-agents), `async def`, return dict with `"success": bool, "error": str | None`.
- All agents: `Agent(name=..., instructions=..., model=..., tools=[...])` from `agents` package.
- Type hints: Python 3.11+ (`str | None`). Ruff line-length=100. mypy strict.
- Commit convention: Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`).

---

## Branch & Team

- `main` (protected) ← `develop` ← `feature/*`
- All PRs target `develop`. `main` requires Lead review + CI status check.
- `CODEOWNERS` auto-assigns Lead reviewer on all PRs.

| Member | Branch | Scope | Status |
|--------|--------|-------|--------|
| **Lead** | `feature/triage-orchestrator`, `feature/session-management` | Triage, session mgmt, architecture, CI/CD, repo hygiene | ✅ Done |
| **M2** | `feature/policy-agent` | Policy agent, 3 guardrails, database | ✅ Done (PR #5 merged) |
| **M3** | `feature/resolution-agent` | Resolution agent, 3 tools (crm, payment, shipping) | ✅ Done (PR #3 merged) |
| **M4** | `feature/communication-escalation` | Communication + Escalation agents, 2 tools, brand voice | ✅ Done (PR #7 merged) |
| **M5** | `feature/infra-observability` | Kafka, K8s, Datadog, CSAT pipeline | ✅ Done (PR #4 merged) |

---

## Tool Interface Contract

All tools in `docs/tool_interface_spec.md` — authoritative. Do not change signatures without Lead approval.

Error contract (all tools):
```python
{ "success": False, "error": "<human-readable message>" }
```

---

## SDD Workflow

Specs go in `specs/<feature>/spec.md`, plans in `specs/<feature>/plan.md`.
Use `.specify/templates/spec-template.md` to write specs.

---

## Test Fixtures

`tests/fixtures/` contains synthetic JSON: `customers.json`, `orders.json`, `fraud_signals.json`, `messages.json`, `resolutions.json`.
