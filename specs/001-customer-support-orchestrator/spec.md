# Feature Specification: 001 — Customer Support & Returns Orchestrator

**Feature Branch**: `main`
**Created**: 2026-05-15
**Status**: Production-ready
**Owner**: Project Lead (Khizar)
**Last Updated**: 2026-06-24

---

## 1. Overview

An AI-powered customer support orchestrator that handles returns, order tracking, billing disputes, and general inquiries through a multi-agent system with guardrails, deterministic tool dispatch, and natural language responses.

### 1.1 Goals

- Automate 80%+ of customer support returns processing
- Provide instant, accurate responses to customer inquiries
- Enforce business rules via guardrails (PII protection, sentiment monitoring, refund caps, brand voice)
- Maintain full audit trail of all customer interactions
- Achieve $0.00 cost-per-ticket via free-tier LLM inference

### 1.2 Success Metrics

| Metric | Target |
|--------|--------|
| Intent Classification Accuracy | ≥ 95% |
| False Positive Rate (escalation) | ≤ 5% |
| Response Latency (P95) | < 3s |
| CSAT Score | ≥ 4.2/5.0 |
| Cost Per Ticket | $0.00 (free tier) |

---

## 2. Architecture

### 2.1 Pattern: Manager + Handoff Hybrid

See `docs/ADR-001.md` for full decision rationale.

- **Tool calls** (tracking, FAQ, return eligibility) keep context with the Triage Orchestrator
- **Handoffs** (Policy, Billing, Escalation) give full specialist ownership

### 2.2 System Flow

```
Customer Message
    ↓
FastAPI POST /webhook/message
    ↓
Triage Orchestrator
    ├── Keyword Classification (primary, deterministic, zero-cost)
    ├── LLM Classification (enrichment, optional)
    └── _dispatch_table(intent)
            ├── Tool Execution (deterministic code)
            └── Agent Handoff (specialist ownership)
    ↓
Natural Language Response
    ↓
Guardrails Check
    └── Response to Customer
```

### 2.3 Entry Point

**File**: `main.py`

```python
POST /webhook/message
├── Request: {"message": str, "session_id": str (optional)}
└── Response: {
    "response": str,           # Natural language reply
    "intent": str,             # Classified intent
    "guardrails": dict,        # Activated guardrails
    "technical": dict,         # Raw tool results
    "session_id": str          # Session identifier
}
```

---

## 3. Intents & Routing

| Intent | Trigger Keywords | Route | Type | Tool Executed |
|--------|-----------------|-------|------|---------------|
| `return_request` | return, send back, damaged, broken, wrong item | `check_return_policy` | Tool call | Yes |
| `order_status` | track, where is, delivery, shipped, tracking | `tracking_lookup` | Tool call | Yes |
| `billing_dispute` | charged, billing, invoice, overcharged | BillingAgent | Handoff | No |
| `general_inquiry` | (fallback) | `faq_lookup` | Tool call | Yes |
| `edge_case_escalate` | sue, lawyer, attorney, court, + frustration keywords | EscalationAgent | Handoff | No |

### 3.1 Frustration/Complaint Keywords

Messages containing these keywords route to `edge_case_escalate`:
- terrible, awful, horrible, worst, hate, angry, furious, livid
- unacceptable, ridiculous, absurd, joke, scam, fraud
- fix this now, speak to manager, supervisor, get me a human
- wasted my time, never again, done with you

### 3.2 Keyword Escalation Override

Keyword classification **wins over LLM** for escalation signals. This prevents the LLM from downgrading frustrated/angry messages to `general_inquiry`.

---

## 4. Agents

All agents live in `app_agents/` and use:
```python
Agent(name=..., instructions=..., model=..., tools=[...])
```

### 4.1 Agent Registry

| Agent | File | Owner | Tools | Guardrails | Output Type |
|-------|------|-------|-------|------------|-------------|
| TriageOrchestrator | `triage_orchestrator.py` | Khizar | `get_customer_profile` | PII Scrubber, Sentiment Monitor | `TriageDecision` |
| PolicyAgent | `policy_agent.py` | Mustafa | `check_return_policy`, `get_customer_profile` | — | `PolicyDecision` |
| ResolutionAgent | `resolution_agent.py` | Hammad | `process_refund`, `create_return_label`, `create_replacement_order` | Refund Cap | `ResolutionSummary` |
| BillingAgent | `billing_agent.py` | Khizar | `process_refund` | Refund Cap | `BillingDecision` |
| CommunicationAgent | `communication_agent.py` | Ammar | `send_notification` | Brand Voice | `CommunicationAgentOutput` |
| EscalationAgent | `escalation_agent.py` | Ammar | `create_human_ticket`, `log_resolution` | — | `EscalationSummary` |

### 4.2 Triage Orchestrator Architecture

**Classifier Only** — does NOT execute tools.

```
Message → Keyword Classifier → Intent
                ↓ (optional enrichment)
         LLM Classifier → Intent + Reasoning
                ↓
         _dispatch_table(intent) → Tool Execution → Result
```

---

## 5. Tools

All tools live in `tools/` and use:
```python
@function_tool
async def tool_name(param: str) -> dict:
```

### 5.1 Tool Registry

| Tool | File | Owner | Signature | Returns |
|------|------|-------|-----------|---------|
| `check_return_policy` | `policy_tools.py` | Mustafa | `(order_id, customer_id)` | `eligible`, `reason`, `recommended_action`, `return_window_days`, `days_since_purchase`, `item_category`, `exclusion_reason`, `fraud_signal`, `error` |
| `get_customer_profile` | `crm_tools.py` | Hammad | `(customer_id)` | `customer_id`, `name`, `email`, `phone`, `loyalty_tier`, `order_history`, `past_returns`, `fraud_flag`, `fraud_reason`, `error` |
| `process_refund` | `payment_tools.py` | Hammad | `(order_id, amount_usd, method)` | `success`, `transaction_id`, `refund_amount`, `currency`, `estimated_days`, `error` |
| `create_return_label` | `shipping_tools.py` | Hammad | `(order_id, carrier)` | `success`, `label_url`, `tracking_number`, `carrier`, `expires_at`, `error` |
| `create_replacement_order` | `shipping_tools.py` | Hammad | `(order_id)` | `success`, `replacement_order_id`, `expedited`, `estimated_delivery`, `error` |
| `send_notification` | `notification_tools.py` | Ammar | `(customer_id, channel, subject, body)` | `success`, `message_id`, `channel`, `delivered_at`, `error` |
| `create_human_ticket` | `helpdesk_tools.py` | Ammar | `(context_bundle)` | `success`, `ticket_id`, `ticket_url`, `priority`, `error` |
| `log_resolution` | `helpdesk_tools.py` | Ammar | `(session_id, outcome)` | `success`, `record_id`, `error` |
| `tracking_lookup` | `tracking_tools.py` | Khizar | `(order_id)` | `success`, `found`, `status`, `carrier`, `tracking_number`, `estimated_delivery`, `last_update`, `error` |
| `faq_lookup` | `tracking_tools.py` | Khizar | `(query)` | `success`, `matched_keyword`, `answer`, `confidence`, `error` |

### 5.2 Error Contract

All tools return:
```python
{"success": False, "error": "<human-readable message>"}
```

### 5.3 Raw Function Variants

Tools export `RAW_<TOOL_NAME>` for direct calls (bypassing SDK wrapper).

---

## 6. Guardrails

All guardrails live in `guardrails/` and use `@input_guardrail` or `@output_guardrail`.

### 6.1 Guardrail Registry

| Guardrail | File | Owner | Type | Wired To | Behaviour |
|-----------|------|-------|------|----------|-----------|
| PII Scrubber | `pii_scrubber.py` | Mustafa | Input | TriageOrchestrator | Replaces credit cards, SSNs, bank accounts with `[REDACTED]` |
| Sentiment Monitor | `sentiment_monitor.py` | Mustafa | Input | TriageOrchestrator | Scores 0.0–1.0; triggers at >= 0.8 |
| Refund Cap | `refund_cap.py` | Khizar | Output | ResolutionAgent, BillingAgent | Blocks refunds > $500; requires human approval |
| Brand Voice | `brand_voice.py` | Ammar | Output | CommunicationAgent | Replaces prohibited language; enforces 150-word limit |

### 6.2 Sentiment Scoring Weights

| Signal | Weight | Example |
|--------|--------|---------|
| ALL CAPS (>10 chars) | +0.3 | "I WILL SUE YOU" |
| Legal keywords | +0.4 | sue, lawyer, attorney, court, legal, litigation |
| Distress keywords | +0.2 | crying, desperate, ruined, outrageous, unacceptable, furious |
| Profanity | +0.2 | fuck, shit, crap, damn, bastard, asshole |
| Multiple exclamations | +0.1–0.2 | "!!!" → +0.1, "!!??" → +0.2 |

**Threshold:** `>= 0.8` triggers escalation.

---

## 7. Natural Language Responses

The triage orchestrator generates friendly English responses via `_generate_response()` for all 7 intent paths:

| Intent | Response Style |
|--------|---------------|
| return_request (eligible) | Confirmation + next steps |
| return_request (ineligible) | Explanation + alternatives |
| order_status | Tracking status + carrier info |
| billing_dispute | Acknowledgment + specialist routing |
| general_inquiry | FAQ answer with keyword match |
| damaged_item | Apology + replacement/refund options |
| edge_case_escalate | Empathy + human escalation |

### 7.1 Technical Details

- Natural language is **primary display** in frontend
- Technical details available in collapsible `<details>` section
- Guardrail activations shown as badges

---

## 8. Data Sources

### 8.1 Live Demo Data

| Source | Location | Type |
|--------|----------|------|
| Tracking Data | `tools/tracking_tools.py` | Hardcoded dict (10 orders) |
| FAQ Database | `tools/tracking_tools.py` | Hardcoded list (12 questions) |
| CRM Data | `tools/crm_tools.py` | External API (`CRM_BASE_URL`) |
| Policy Rules | `tools/policy_tools.py` | Repository (Postgres/File backend) |

### 8.2 Repository Backends

| Backend | Use Case | Config |
|---------|----------|--------|
| PostgreSQL | Production | `DATABASE_URL` env var |
| FileBackend | Development | `FILE_DB_PATH` env var |
| MemoryBackend | Testing | In-memory dict |

---

## 9. LLM Provider

- **Provider:** OpenRouter (free tier)
- **Model:** `openai/gpt-oss-120b:free`
- **Rate limits:** 30 RPM, 1K RPD
- **Compatibility patches:** MultiProvider `unknown_prefix_mode="model_id"`, `response_format` stripped when tools present

---

## 10. Infrastructure

| Component | File | Owner | Purpose |
|-----------|------|-------|---------|
| Redis | `redis_config.py` | Khizar | Session store (24h active, 90d archive) |
| Kafka | `kafka_config.py` | Anas | Consumer per channel (web_chat, email, whatsapp, sms) |
| Datadog | `datadog_setup.py` | Anas | APM instrumentation |
| Monitors | `datadog_monitors.py` | Anas | 3 PagerDuty-bound monitors |
| CSAT | `csat_pipeline.py` | Anas | Rolling CSAT score computation |
| A/B Testing | `ab_test.py` | Anas | Variant assignment, result recording |
| Kubernetes | `k8s/` | Anas | Deployment, service, HPA, configmap, secret |

---

## 11. Frontend

**File**: `frontend/index.html`

Single HTML file, zero dependencies:
- Dark glassmorphism theme
- Live chat interface
- 6 pre-built scenario cards
- 4 guardrail demos
- Architecture visualization
- Routing pipeline panel

**Run:**
```bash
cd frontend && python -m http.server 3000
```

---

## 12. Team

| Member | Name | Role | Scope |
|--------|------|------|-------|
| Lead | Khizar | Lead Developer & Architect | Triage, session mgmt, architecture, CI/CD, billing, tracking |
| M2 | Mustafa | Policy & Guardrails | Policy agent, 3 guardrails, database |
| M3 | Hammad | Resolution & Tools | Resolution agent, CRM/payment/shipping tools |
| M4 | Ammar | Communication & Escalation | Comms + Escalation agents, notification/helpdesk tools, brand voice |
| M5 | Anas | Infrastructure & Observability | Kafka, K8s, Datadog, CSAT pipeline |

---

## 13. Test Coverage

| File | Owner | Tests |
|------|-------|-------|
| test_policy_agent.py | Mustafa | 106 |
| test_resolution_agent.py | Hammad | 21 |
| test_billing_agent.py | Khizar | 18 |
| test_comm_escalation.py | Ammar | 14 |
| test_database.py | Khizar | 37 |
| test_infra_observability.py | Anas | 41 |
| test_tools.py | Hammad | 44 |
| test_integration.py | Khizar | 40 |
| test_tracking_tools.py | Khizar | 32 |
| **Total** | | **369** |

---

## 14. Repository Structure

```
SMIT-SAAS/
├── main.py                          # FastAPI entry point
├── app_agents/
│   ├── triage_orchestrator.py       # Entry point, classification, dispatch
│   ├── policy_agent.py              # Return policy decisions
│   ├── resolution_agent.py          # Refund, label, replacement
│   ├── billing_agent.py             # Billing dispute handling
│   ├── communication_agent.py       # Multi-channel notifications
│   └── escalation_agent.py          # Human handoff
├── tools/
│   ├── policy_tools.py              # check_return_policy
│   ├── crm_tools.py                 # get_customer_profile
│   ├── payment_tools.py             # process_refund
│   ├── shipping_tools.py            # create_return_label, create_replacement_order
│   ├── notification_tools.py        # send_notification
│   ├── helpdesk_tools.py            # create_human_ticket, log_resolution
│   └── tracking_tools.py            # tracking_lookup, faq_lookup
├── guardrails/
│   ├── pii_scrubber.py              # Input: PII redaction
│   ├── sentiment_monitor.py         # Input: Sentiment scoring
│   ├── refund_cap.py                # Output: Refund limit
│   └── brand_voice.py              # Output: Brand tone enforcement
├── database/
│   ├── repository.py                # Abstract Repository + 3 backends
│   ├── models.py                    # SQLAlchemy ORM
│   ├── config.py                    # Database configuration
│   ├── schema.sql                   # DDL
│   └── seed.sql                     # Seed data
├── tests/                           # 369 tests
├── frontend/                        # Presentation UI
├── docs/                            # ADRs, specs
├── specs/                           # Feature specifications
├── presentation/                    # Pitch deck
├── k8s/                             # Kubernetes manifests
└── .opencode/                       # Skills, agents
```

---

## 15. Commands

```bash
# Setup
pip install -r requirements.txt
pip install -e ".[dev]"

# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000
cd frontend && python -m http.server 3000

# Testing
pytest tests/ -v
pytest tests/ --cov -v

# Linting
ruff check .
ruff format --check .
mypy .
```

---

## 16. Git Workflow

- `main` (protected) ← `develop` ← `feature/*`
- All PRs target `develop`
- `main` requires Lead review + CI status check
- Commit convention: Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`)

---

## 17. Acceptance Criteria

- [x] All 6 agents implemented and tested
- [x] All 10 tools implemented and tested
- [x] All 4 guardrails implemented and tested
- [x] Natural language responses for all intents
- [x] Keyword-first classification with LLM enrichment
- [x] Deterministic tool dispatch
- [x] Frontend with live chat and guardrail demos
- [x] 369 tests passing
- [x] Production-ready on `main` branch
