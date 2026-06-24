# Agent 01 — Customer Support & Returns Orchestrator

> Autonomous Resolution from Triage to Refund  
> E-Commerce Multi-Agent System | Built on OpenAI Agents SDK | 2026

---

## Overview

A production-grade multi-agent system that autonomously handles the full lifecycle of customer inquiries, complaints, and return requests. The Triage Orchestrator routes every inbound message to the correct specialist agent, achieving sub-30-second resolution for 80%+ of routine cases.

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

## Team

| Member     | Role                                  | Branch                          | Status |
|------------|---------------------------------------|---------------------------------|--------|
| Lead       | Architect, Triage Orchestrator, Infra | `feature/triage-orchestrator`   | Done   |
| Member 2   | Policy Agent & Guardrails             | `feature/policy-agent`          | Done   |
| Member 3   | Resolution Agent & Tool Integrations  | `feature/resolution-agent`      | Done   |
| Member 4   | Communication & Escalation Agents     | `feature/communication-escalation` | Done (PR #7 merged) |
| Member 5   | Infrastructure & Observability        | `feature/infra-observability`   | Done   |

## Test Suite

| Metric | Count |
|--------|-------|
| Tests Passed | 353 |
| Tests Skipped | 0 |
| Test Files | 9 |
| Coverage Scope | Policy, Resolution, Billing, Communication, Escalation, Database, Infra, Integration, Tracking Tools |

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

# 5. Run the entry point
uvicorn main:app --reload

# 6. Run the presentation frontend (optional)
cd frontend && python -m http.server 3000
```

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

## Branch Strategy

- `main` — protected, production-ready only. PRs require 1 review, linear history, no force-push, admins enforced.
- `develop` — integration branch. All feature branches merge here first.
- `feature/*` — one branch per team member (see table above). Always target `develop`, never `main`.

> **Rule:** PRs target `develop`. Direct merges to `main` are blocked by branch protection. If you need a hotfix, open a PR from a `hotfix/*` branch into `main` and request Lead review.

## Phases

| Phase | Duration | Focus |
|-------|----------|-------|
| 1 — Foundation       | Weeks 1–2 | Triage + Policy + Resolution agents, core tools |
| 2 — Communication    | Week 3    | Communication Agent, brand voice, SendGrid      |
| 3 — Escalation       | Week 4    | Escalation Agent, Zendesk, human handoff        |
| 4 — Guardrails       | Week 5    | PII scrubber, sentiment monitor, refund cap     |
| 5 — Observability    | Week 6    | Tracing dashboard, CSAT pipeline, A/B framework |
| 6 — Production       | Weeks 7–8 | Load testing, chaos engineering, SLA validation |

## KPIs

| KPI | Target |
|-----|--------|
| First Response Time       | < 3 seconds      |
| Full Resolution (Tier 1)  | < 30 seconds     |
| Automation Rate           | > 80%            |
| Fraud Detection Rate      | > 95%            |
| CSAT Score                | > 4.5 / 5.0      |
| Cost per Ticket           | $0.00 (free tier) |

---

*Confidential — Team Internal*
