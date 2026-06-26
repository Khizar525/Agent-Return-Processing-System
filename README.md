# Agent 01 — Customer Support & Returns Orchestrator

> Autonomous Resolution from Triage to Refund
> E-Commerce Multi-Agent System | Built on OpenAI Agents SDK | 2026

---

## Overview

A production-grade multi-agent system that autonomously handles the full lifecycle of customer inquiries, complaints, and return requests. The Triage Orchestrator routes every inbound message to the correct specialist agent, achieving sub-30-second resolution for 80%+ of routine cases.

**What it does:**
- Customer sends a message (return request, tracking, FAQ, complaint, etc.)
- System classifies intent, executes tools, and returns a **natural language response**
- Guardrails detect PII, sentiment, refund limits, and brand violations
- Escalates to human agents when needed

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

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd agent-01-customer-support

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env template and fill in your keys
cp .env.example .env

# 5. Start backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 6. Start frontend (separate terminal)
cd frontend && python -m http.server 3000
```

**Frontend:** http://localhost:3000
**Backend API:** http://localhost:8000
**Health check:** http://localhost:8000/health

## Features

### Natural Language Chatbot
The system responds in plain English, not raw JSON:
- **Returns:** "Good news! Your order is eligible for a return. You have 15 days left..."
- **Tracking:** "It's on its way! Carrier: UPS (Tracking: UP-1827364510)..."
- **FAQ:** "To return an item, go to My Orders, select the order, and click 'Start Return'..."
- **Billing:** "I understand you have a billing concern. I'm connecting you with our billing specialist..."
- **Escalation:** "I hear you, and I'm sorry you've had this experience. You deserve better..."

### Guardrails (Visible in Chat)
| Guardrail | Type | What it does |
|-----------|------|-------------|
| PII Scrubber | Input | Detects credit cards/SSN → replaces with [REDACTED] |
| Sentiment Monitor | Input | Scores sentiment (0.0–1.0) → triggers escalation at >= 0.8 |
| Refund Cap | Output | Blocks refunds > $500 → requires human approval |
| Brand Voice | Output | Detects prohibited language → rewrites |

### Routing Pipeline
Every message goes through a visible routing pipeline:
1. **Triage Orchestrator** classifies intent (keyword-first, LLM enrichment)
2. **Tool dispatch** executes the appropriate tool (deterministic)
3. **Guardrails** check for violations
4. **Response** generated in natural language

## LLM Provider

The system uses **OpenRouter** free tier for all agents:

- **Model:** `openai/gpt-oss-120b:free`
- **Rate limits:** 30 RPM, 1K RPD
- **Cost:** $0.00 (free tier)
- **No credit card required**

Provider compatibility patches are applied at startup in `main.py`:
- MultiProvider `unknown_prefix_mode="model_id"` for model names with `/`
- `response_format` stripped when tools/handoffs are present

## Environment Variables

See `.env.example` for all required keys. Never commit a populated `.env` to Git.

## Test Suite

```bash
pytest tests/ -v                    # run all tests
pytest tests/ --cov -v              # with coverage
ruff check .                        # lint
ruff format --check .               # format check
```

| Metric | Count |
|--------|-------|
| Tests Passed | 353 |
| Tests Skipped | 0 |
| Test Files | 9 |

## Project Structure

```
├── main.py                    # FastAPI entry point
├── app_agents/                # Agent definitions
│   ├── triage_orchestrator.py # Entry point — keyword-first classification
│   ├── policy_agent.py        # Return eligibility evaluation
│   ├── resolution_agent.py    # Refund/label/replacement processing
│   ├── billing_agent.py       # Billing dispute handling
│   ├── communication_agent.py # Notification drafting
│   └── escalation_agent.py    # Human escalation
├── tools/                     # Tool implementations
│   ├── policy_tools.py        # check_return_policy
│   ├── crm_tools.py           # get_customer_profile
│   ├── payment_tools.py       # process_refund
│   ├── shipping_tools.py      # create_return_label, create_replacement_order
│   ├── tracking_tools.py      # tracking_lookup, faq_lookup
│   ├── notification_tools.py  # send_notification
│   └── helpdesk_tools.py      # create_human_ticket, log_resolution
├── guardrails/                # Guardrails
│   ├── pii_scrubber.py        # Input — strips credit cards, SSNs
│   ├── sentiment_monitor.py   # Input — scores CSAT risk
│   ├── refund_cap.py          # Output — blocks refunds > $500
│   └── brand_voice.py         # Output — enforces brand tone
├── frontend/                  # Presentation frontend
│   └── index.html             # Single-file chatbot UI
├── infra/                     # Infrastructure
│   ├── redis_config.py        # Session store
│   ├── kafka_config.py        # Multi-channel ingestion
│   ├── datadog_setup.py       # APM instrumentation
│   ├── datadog_monitors.py    # PagerDuty-bound monitors
│   ├── csat_pipeline.py       # CSAT score computation
│   └── ab_test.py             # A/B test framework
├── database/                  # Data layer
│   ├── repository.py          # Abstract Repository + 3 backends
│   ├── models.py              # SQLAlchemy 2.0 ORM
│   └── config.py              # Database configuration
├── tests/                     # 353 tests across 9 files
└── docs/                      # Architecture decision records
```

## Branch Strategy

- `main` — protected, production-ready. PRs require review.
- `develop` — integration branch. All feature branches merge here first.
- `feature/*` — one branch per team member.

## Team

| Member     | Role                                  | Status |
|------------|---------------------------------------|--------|
| Lead       | Architect, Triage Orchestrator, Infra | Done   |
| Member 2   | Policy Agent & Guardrails             | Done   |
| Member 3   | Resolution Agent & Tool Integrations  | Done   |
| Member 4   | Communication & Escalation Agents     | Done   |
| Member 5   | Infrastructure & Observability        | Done   |

---

*Confidential — Team Internal*
