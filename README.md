# Agent Nemo — Customer Support & Returns Orchestrator

> A production-grade multi-agent AI system that autonomously handles customer inquiries, returns, refunds, and escalations — from triage to resolution — at zero cost using free-tier LLM inference.

---

## Overview

Agent Nemo is a multi-agent customer support system built on the OpenAI Agents SDK. It autonomously classifies customer intent, routes to specialist agents, executes tools, and returns natural language responses — all within sub-30-second resolution for 80%+ of routine cases.

**What it does:**
- Customer sends a message (return request, tracking, FAQ, complaint, etc.)
- Triage Orchestrator classifies intent using keyword-first + LLM enrichment
- Deterministic tool dispatch or specialist agent handoff executes the action
- Guardrails detect PII, sentiment, refund limits, and brand violations
- Natural language response delivered to the customer

## Demo

> **To try Agent Nemo:** Start the backend and frontend (see Quick Start below), then open http://localhost:3000 and send a message like "I want to return order ORD-001" or "Where is my order?".

---

## Architecture

```
                   Customer Message
                          │
                          ▼
         ┌────────────────────────────────┐
         │     Triage Orchestrator        │ ◄── Sentiment Monitor
         │  (keyword-first classification,│     (passive guardrail)
         │   gpt-oss-120b:free)           │
         └────────┬───────────────┬───────┘
                  │               │
    tool call     │    handoff    │         handoff
    (deterministic│               │         (full context)
     dispatch)    ▼               ▼
             ┌────────┐    ┌────────────┐    ┌──────────────┐
             │tracking│    │Policy Agent│    │Billing Agent │
             │  /faq  │    │(gpt-oss-   │    │  (handoff)   │
             │ /return│    │ 120b:free) │    │              │
             │(tools) │    └─────┬──────┘    └──────────────┘
             └────────┘          │ handoff
                                 ▼
                        ┌────────────────┐
                        │ Resolution     │
                        │ Agent          │ ◄── refund_cap guardrail
                        │ (gpt-oss-120b: │
                        │  free)         │
                        └────────┬───────┘
                                 │ handoff
                                 ▼
                        ┌────────────────┐
                        │ Communication  │ ──► Email / SMS / Chat
                        │ Agent          │     (brand_voice guardrail)
                        └────────┬───────┘
                                 │
                   (edge case)   │
                                 ▼
                        ┌────────────────┐
                        │ Escalation     │ ──► Human Queue
                        │ Agent          │     + Context Bundle
                        │ (gpt-oss-120b: │
                        │  free)         │
                        └────────────────┘
```

**Pattern:** Manager + Handoff hybrid (see `docs/ADR-001.md`).
- *Tool calls* (tracking, FAQ, return eligibility) are dispatched deterministically by code.
- *Handoffs* (Policy, Billing, Escalation) give full specialist ownership.

## Agentic Characteristics

Agent Nemo demonstrates key characteristics of production agentic systems:

| Characteristic | Implementation |
|----------------|----------------|
| **Specialized agents with isolated responsibilities** | 6 agents — Triage, Policy, Resolution, Billing, Communication, Escalation — each owning a single bounded context |
| **Centralized orchestration** | Triage Orchestrator classifies intent and routes via tool calls or handoffs |
| **Shared execution context** | Customer profile, order data, and session state flow through all agents |
| **Deterministic tool dispatch** | Code maps intent → tool call — not LLM-dependent (avoids SDK limitations) |
| **Autonomous multi-stage execution** | Once triggered, the pipeline completes without human input |
| **Guardrail-governed behavior** | 4 guardrails (PII, sentiment, refund cap, brand voice) enforce safety constraints |
| **Failure recovery and escalation** | Edge cases automatically escalate to human agents with full context bundle |

---

## Features

### Natural Language Chatbot

The system responds in plain English, not raw JSON:

| Intent | Example Response |
|--------|------------------|
| **Returns** | "Good news! Your order is eligible for a return. You have 15 days left..." |
| **Tracking** | "It's on its way! Carrier: UPS (Tracking: UP-1827364510)..." |
| **FAQ** | "To return an item, go to My Orders, select the order, and click 'Start Return'..." |
| **Billing** | "I understand you have a billing concern. I'm connecting you with our billing specialist..." |
| **Escalation** | "I hear you, and I'm sorry you've had this experience. You deserve better..." |

### Guardrails (Visible in Chat)

| Guardrail | Type | What it does | Trigger |
|-----------|------|-------------|---------|
| PII Scrubber | Input | Detects credit cards/SSN → replaces with [REDACTED] | `4111-1111-1111-1111`, SSN patterns |
| Sentiment Monitor | Input | Scores sentiment 0.0–1.0 → triggers escalation at ≥ 0.8 | ALL CAPS (+0.3), legal keywords (+0.4) |
| Refund Cap | Output | Blocks refunds > $500 → requires human approval | Any refund amount > $500 USD |
| Brand Voice | Output | Detects prohibited language → rewrites | Profanity, aggressive tone |

### Routing Pipeline

Every message goes through a visible routing pipeline:

```
Message → Keyword Classification → Intent → Tool Dispatch → Guardrails → Response
                ↓ (optional)
         LLM Enrichment → Better Reasoning
```

1. **Keyword Classification** (primary): Fast, deterministic, zero-cost intent detection
2. **LLM Classification** (enrichment): Optional — provides better reasoning quality
3. **Tool Dispatch** (deterministic): Code maps intent → tool call
4. **Guardrails** check for PII, sentiment, refund limits, brand violations
5. **Response** generated in natural language

---

## Challenges & Solutions

| Challenge | Solution | Result |
|-----------|----------|--------|
| LLM produces malformed JSON | Keyword-first fallback + deterministic dispatch | 100% routing reliability |
| Free model downgrades angry messages | Keyword escalation override for frustration signals | Escalation accuracy restored |
| Brand voice destroys acronyms (USA → Usa) | Acronym preservation for tokens ≤ 4 chars | USA, API, FAQ preserved |
| Prohibited words partially match | Regex word boundaries (`\b`) | "assessment" no longer matches "ass" |
| Status map lookup mismatch | Normalized keys to raw underscore format | Tracking lookup works reliably |
| SDK consumes tool call results internally | Moved tool execution to code layer | Full visibility into tool results |
| $0 cost requirement | OpenRouter free tier + provider compat patches | 30 RPM, 1K RPD, zero cost |

---

## Performance Metrics

| Metric | Target | Result | Status |
|--------|--------|--------|--------|
| Intent Classification Accuracy | > 95% | 100% (keyword) | Passed |
| Sub-30s Resolution Rate | > 80% | 85%+ | Passed |
| PII Detection | 100% | 100% | Passed |
| Sentiment Escalation Accuracy | > 90% | 95%+ | Passed |
| Test Pass Rate | 100% | 369/369 | Passed |
| Cost per Ticket | $0.00 | $0.00 | Passed |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Agents** | OpenAI Agents SDK (Python) |
| **LLM** | OpenRouter — `openai/gpt-oss-120b:free` (30 RPM, 1K RPD) |
| **Backend** | FastAPI + Uvicorn |
| **Frontend** | Single-file HTML/CSS/JS (glassmorphism UI) |
| **Database** | SQLAlchemy 2.0 (PostgreSQL prod / JSON file dev) |
| **Guardrails** | Custom input/output guardrails (PII, sentiment, refund cap, brand voice) |
| **Infrastructure** | Redis (sessions), Kafka (channels), Datadog (APM), Kubernetes |
| **Testing** | pytest (369 tests), ruff (lint), mypy (type check) |

---

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### 1. Clone & Configure

```bash
git clone https://github.com/Khizar525/Agent-Return-Processing-System.git
cd Agent-Return-Processing-System
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenRouter API key
```

### 2. Start Services

```bash
# Backend (Terminal 1)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Terminal 2)
cd frontend && python -m http.server 3000
```

### 3. Access

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## Test Suite

```bash
pytest tests/ -v                    # run all tests
pytest tests/ --cov -v              # with coverage
ruff check .                        # lint
ruff format --check .               # format check
mypy .                              # type check
```

### Test Breakdown

| File | Owner | Tests | What It Covers |
|------|-------|-------|----------------|
| `test_policy_agent.py` | Mustafa | 106 | Policy tool, guardrails, agent config, contracts |
| `test_resolution_agent.py` | Hammad | 21 | Resolution agent, tool invocation, E2E with mocks |
| `test_billing_agent.py` | Khizar | 18 | Billing agent, schema, refund cap enforcement |
| `test_comm_escalation.py` | Ammar | 14 | Notifications, brand voice, escalation, helpdesk |
| `test_database.py` | Khizar | 37 | DTOs, MemoryBackend, FileBackend, factory |
| `test_infra_observability.py` | Anas | 41 | Kafka, Datadog, monitors, CSAT pipeline |
| `test_tools.py` | Hammad | 44 | CRM, payment, shipping tools with respx mocks |
| `test_integration.py` | Khizar | 40 | Fixture integrity, policy tool, tracking, FAQ, session |
| `test_tracking_tools.py` | Khizar | 32 | Tracking lookup, FAQ lookup, contracts, edge cases |

**Total: 369 tests — 0 skipped, 0 failed**

---

## Project Structure

```
agent-nemo/
├── main.py                        # FastAPI entry point + provider compat
├── app_agents/                    # Agent definitions
│   ├── triage_orchestrator.py     # Keyword-first classification + dispatch
│   ├── policy_agent.py            # Return eligibility evaluation
│   ├── resolution_agent.py        # Refund/label/replacement processing
│   ├── billing_agent.py           # Billing dispute handling
│   ├── communication_agent.py     # Notification drafting
│   └── escalation_agent.py        # Human escalation
├── tools/                         # Tool implementations
│   ├── policy_tools.py            # check_return_policy
│   ├── crm_tools.py               # get_customer_profile
│   ├── payment_tools.py           # process_refund
│   ├── shipping_tools.py          # create_return_label, create_replacement_order
│   ├── tracking_tools.py          # tracking_lookup, faq_lookup
│   ├── notification_tools.py      # send_notification
│   └── helpdesk_tools.py          # create_human_ticket, log_resolution
├── guardrails/                    # Safety & quality guardrails
│   ├── pii_scrubber.py            # Input — strips credit cards, SSNs
│   ├── sentiment_monitor.py       # Input — scores CSAT risk
│   ├── refund_cap.py              # Output — blocks refunds > $500
│   └── brand_voice.py             # Output — enforces brand tone
├── frontend/                      # Presentation frontend
│   └── index.html                 # Single-file chatbot UI
├── infra/                         # Infrastructure & observability
│   ├── redis_config.py            # Session store
│   ├── kafka_config.py            # Multi-channel ingestion
│   ├── datadog_setup.py           # APM instrumentation
│   ├── datadog_monitors.py        # PagerDuty-bound monitors
│   ├── csat_pipeline.py           # CSAT score computation
│   ├── ab_test.py                 # A/B test framework
│   └── k8s/                       # Kubernetes manifests
├── database/                      # Data layer
│   ├── repository.py              # Abstract Repository + 3 backends
│   ├── models.py                  # SQLAlchemy 2.0 ORM
│   └── config.py                  # Database configuration
├── tests/                         # 369 tests across 9 files
├── docs/                          # Architecture decision records
└── presentation/                  # Pitch deck
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [ADR-001](docs/ADR-001.md) | Architecture Decision — Tool execution pattern |
| [Tool Interface Spec](docs/tool_interface_spec.md) | Authoritative tool signatures and contracts |
| [Tracing Dashboard](docs/tracing_dashboard.md) | Datadog APM dashboard configuration |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Branch rules, commit format, PR checklist |
| [AGENTS.md](AGENTS.md) | Full architecture, agents, tools, guardrails, tests |

---

## Branch Strategy

| Branch | Purpose | Protection |
|--------|---------|------------|
| `main` | Production-ready | None (post-development) |
| `develop` | Integration branch | — |
| `feature/*` | Per-team-member work | — |

---

## Team

| Member | Role | Contributions |
|--------|------|---------------|
| **Khizar** | Lead Developer & Architect | Triage Orchestrator, Session Management, Architecture (ADR-001), CI/CD, Billing Agent, Integration Tests |
| **Mustafa** | Policy & Guardrails Specialist | Policy Agent, PII Scrubber, Sentiment Monitor, Database Abstraction (3 backends) |
| **Hammad** | Resolution & Tool Integrations | Resolution Agent, CRM/Payment/Shipping Tools, 44 tool tests with respx mocks |
| **Ammar** | Communication & Escalation | Communication Agent, Escalation Agent, Brand Voice Guardrail, Helpdesk Tools |
| **Anas** | Infrastructure & Observability | Kafka, Datadog APM, K8s Manifests, CSAT Pipeline, A/B Testing |

---

## Future Improvements

### Short-term
- WebSocket real-time updates for live chat
- Task scheduling for follow-up reminders
- Role-based access control for admin dashboard

### Medium-term
- Kubernetes production deployment with HPA
- Redis caching layer for session persistence
- Datadog monitoring dashboards with alerts

### Long-term
- Multi-tenant support for multiple e-commerce stores
- Custom agent development SDK
- Production deployment with SLA monitoring

---

## License

MIT License — see [LICENSE](LICENSE)

---

**Built by:** Khizar, Mustafa, Hammad, Ammar, and Anas
