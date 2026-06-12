# Implementation Plan: 002 — Policy Agent & Guardrails

**Branch**: `feature/policy-agent` | **Date**: 2026-05-20 | **Spec**: `specs/002-policy-agent/spec.md`
**Owner**: Member 2

## Summary

Build the Policy Agent (return eligibility validator) + 3 guardrails (PII scrubber, sentiment monitor, refund cap) using the openai-agents SDK. The agent uses `gemini-2.0-flash` (free tier via Google Gemini OpenAI-compatible endpoint), calls `check_return_policy` tool, and outputs a structured JSON decision. Guardrails plug into triage/resolution agents via `@input_guardrail`/`@output_guardrail`. Cross-team dependencies use commented-out imports.

## Architecture Context

```
Customer Message
       │
       ▼
[Triage Orchestrator]  ◄── PII Scrubber   (input guardrail — M2)
                      ◄── Sentiment Monitor (input guardrail — M2)
       │
  return_request handoff
       │
       ▼
[Policy Agent]  ──► check_return_policy tool (M2)
                      └─► get_customer_profile (commented out — M3)
       │
       ▼
[Resolution Agent]  ◄── Refund Cap (output guardrail — M2)
```

## Technical Context

| Field | Value |
|-------|-------|
| Language/Version | Python 3.11+ |
| SDK | `openai-agents>=0.1.0` (`Agent`, `Runner`, `@function_tool`, `@input_guardrail`, `@output_guardrail`, `GuardrailFunctionOutput`) |
| Web Framework | FastAPI>=0.111.0 (entry only, no changes needed) |
| Testing | pytest>=8.0, pytest-asyncio>=0.23 (asyncio_mode=auto), pytest-cov>=5.0 |
| Linting | ruff>=0.4 (line-length=100, target-version=py311) |
| Typecheck | mypy>=1.10 (strict mode, python-version=3.11) |
| Target | Linux server, Docker/K8s |
| Config | `.env` vars via `os.environ.get()` with hardcoded defaults |
| Storage | None (stateless — eligibility computed fresh each call) |

## Constitution Check

No violations. Feature is single-agent with 3 guardrails. No new external services, no data persistence, no cross-cutting architectural changes.

## Data Contracts

### check_return_policy output (tool → agent)

Per `docs/tool_interface_spec.md` — `success` field only present in error dict, not in success return.

**Success return**:
```python
{
    "eligible":            bool,
    "reason":              str,
    "recommended_action":  "refund" | "replacement" | "reject" | "escalate",
    "return_window_days":  int,
    "days_since_purchase": int,
    "item_category":       str,
    "exclusion_reason":    str | None,
    "fraud_signal":        bool,
    "error":               str | None,
}
```

**Error return**:
```python
{
    "success": False,
    "error": "<human-readable message>",
    # all other fields set to None or empty defaults
}
```

### Policy agent output (agent → triage/resolution)
```python
{
    "eligible":           bool,
    "reason":             str,
    "recommended_action": "refund" | "replacement" | "reject" | "escalate",
}
```

### GuardrailFunctionOutput (guardrail → SDK runtime)
```python
GuardrailFunctionOutput(
    tripwire_triggered=bool,
    output_dict=dict,   # scrubbed message or blocked output
)
```

### PII scrubber output_dict
```python
{ "scrubbed_message": str }
```

### Sentiment monitor output_dict
```python
{ "score": float, "escalate": bool }
```

### Refund cap output_dict
```python
{
    "human_approval_required": bool,
    "amount":                  float | None,
    "reason":                  str,
}
```

## Project Structure

```
specs/002-policy-agent/
├── spec.md          # This feature spec
├── plan.md          # This file

agents/
├── policy_agent.py  # [MODIFY] Fill stub with Agent definition

tools/
├── policy_tools.py  # [CREATE] check_return_policy @function_tool

guardrails/
├── pii_scrubber.py      # [MODIFY] PII redaction @input_guardrail
├── sentiment_monitor.py # [MODIFY] CSAT risk @input_guardrail
├── refund_cap.py        # [MODIFY] Refund limit @output_guardrail

tests/
├── test_policy_agent.py # [MODIFY] Fill 10 test stubs

docs/
├── tool_interface_spec.md  # Reference — no changes needed
```

## Implementation Phases

### Phase 0 — Policy Tool (`tools/policy_tools.py`)

**Depends on**: Nothing  
**Time estimate**: 1 session

Create `tools/policy_tools.py` with module docstring (Owner: Member 2).

```python
from agents import function_tool
import os

EXCLUDED_CATEGORIES = {"digital_goods", "perishables", "final_sale"}
RETURN_WINDOW_DAYS = int(os.environ.get("RETURN_WINDOW_DAYS", "30"))

@function_tool
async def check_return_policy(order_id: str, customer_id: str) -> dict:
    # 1. Validate inputs — return { "success": false, "error": "..." } if missing
    # 2. Look up order (mocked — hardcoded dict until M3 CRM merge)
    # 3. Check return window: days_since_purchase <= RETURN_WINDOW_DAYS
    # 4. Check exclusion list: item_category not in EXCLUDED_CATEGORIES
    # 5. Check fraud flag (mocked — random or hardcoded until M3 merge)
    # 6. Cross-reference fraud DB (mocked — hardcoded until populated)
    # 7. Determine recommended_action based on results
    # 8. Return full contract dict (all fields filled, never None for non-error case)
    pass  # TODO: implement
```

**Key decisions**:
- Mock external data with inline dicts (replaced when M3's `get_customer_profile` merges)
- Error path returns `{ "success": false, "error": "<reason>", "eligible": False, ... }` — never raises
- Exclusion list is module-level set (not env-based — business rule, not config)

### Phase 1 — Policy Agent (`agents/policy_agent.py`)

**Depends on**: Phase 0 (tool must exist)  
**Time estimate**: 1 session

Replace the commented-out stub with a live `Agent`:

```python
from agents import Agent
from tools.policy_tools import check_return_policy
# from tools.crm_tools import get_customer_profile  # uncomment after M3 merges

policy_agent = Agent(
    name="PolicyAgent",
    instructions="""
    You validate return eligibility for customer orders.

    Rules:
    1. Call check_return_policy(order_id, customer_id) to evaluate eligibility.
    2. If eligible is true and recommended_action is "refund" or "replacement", pass through to resolution.
    3. If eligible is false, explain the reason clearly.
    4. If recommended_action is "escalate", recommend human review.

    Always include customer_id and session_id in context when handing off.
    Output must be valid JSON: {{"eligible": bool, "reason": str, "recommended_action": str}}
    """,
    model="gemini-2.0-flash",
    tools=[check_return_policy],
)
```

**Key decisions**:
- `get_customer_profile` is commented out — the tool currently simulates profile data itself
- Agent instructions use double-brace JSON template to avoid f-string conflicts
- No handoffs defined here — handoff is wired in `triage_orchestrator.py` by Lead

### Phase 2 — Guardrails (3 files)

**Depends on**: Nothing (self-contained, no runtime deps on other agents)  
**Time estimate**: 1–2 sessions

#### 2a — PII Scrubber (`guardrails/pii_scrubber.py`)

```python
import re
from agents.guardrails import input_guardrail, GuardrailFunctionOutput

CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
BANK_PATTERN = re.compile(r"\b\d{8,17}\b")

@input_guardrail
async def pii_scrubber_guardrail(ctx, agent, message: str) -> GuardrailFunctionOutput:
    scrubbed = message
    scrubbed = CC_PATTERN.sub("[REDACTED]", scrubbed)
    scrubbed = SSN_PATTERN.sub("[REDACTED]", scrubbed)
    scrubbed = BANK_PATTERN.sub("[REDACTED]", scrubbed)
    triggered = scrubbed != message
    return GuardrailFunctionOutput(
        tripwire_triggered=triggered,
        output_dict={"scrubbed_message": scrubbed},
    )
```

#### 2b — Sentiment Monitor (`guardrails/sentiment_monitor.py`)

```python
from agents.guardrails import input_guardrail, GuardrailFunctionOutput
import os, re

THRESHOLD = float(os.environ.get("SENTIMENT_ESCALATION_THRESHOLD", "0.8"))
DISTRESS_KEYWORDS = {"lawyer", "sue", "court", "attorney", "crying", "desperate", "ruined"}

@input_guardrail
async def sentiment_monitor_guardrail(ctx, agent, message: str) -> GuardrailFunctionOutput:
    score = 0.0
    # +0.3 if ALL CAPS
    # +0.3 if legal keywords
    # +0.2 if distress indicators
    # +0.2 if multiple !!! or ???
    score = min(score, 1.0)
    escalate = score > THRESHOLD
    return GuardrailFunctionOutput(
        tripwire_triggered=escalate,
        output_dict={"score": score, "escalate": escalate},
    )
```

#### 2c — Refund Cap (`guardrails/refund_cap.py`)

```python
from agents.guardrails import output_guardrail, GuardrailFunctionOutput
import os

CAP = float(os.environ.get("REFUND_CAP_USD", "500.0"))

@output_guardrail
async def refund_cap_guardrail(ctx, agent, output) -> GuardrailFunctionOutput:
    amount = output.get("refund_amount", 0)
    if amount > CAP:
        return GuardrailFunctionOutput(
            tripwire_triggered=True,
            output_dict={
                "human_approval_required": True,
                "amount": amount,
                "reason": "exceeds_cap",
            },
        )
    return GuardrailFunctionOutput(tripwire_triggered=False, output_dict=output)
```

**Key decisions**:
- Guardrails are self-contained — no cross-team imports needed
- PII patterns use regex (simple, no external dep needed)
- Sentiment uses keyword scoring (no ML model — fast, deterministic, low cost)
- Refund cap reads `output` dict directly (Resolution Agent output structure TBD with M3; guardrail adapts later)

### Phase 3 — Tests (`tests/test_policy_agent.py`)

**Depends on**: Phase 0 + Phase 1 (agent + tool implemented)  
**Time estimate**: 1 session

Fill all 10 test stubs. Strategy:
- **No fixture files needed yet** — mock data inline or with pytest fixtures in the test module
- Use `pytest-asyncio` for async tool tests
- Directly test `check_return_policy` tool (not via Runner.run — that's integration)
- Test the agent's JSON output contract by constructing expected return values

| Test | What it covers | Mock strategy |
|------|---------------|---------------|
| `test_eligible_return_within_window` | eligible=true, basic path | Inline order mock |
| `test_ineligible_return_outside_window` | window > 30 days | Inline order mock |
| `test_ineligible_item_in_exclusion_list` | exclusion match | Inline order mock |
| `test_fraud_flag_blocks_return` | fraud_flag=true | Inline profile mock |
| `test_output_is_valid_json` | output contract format | Direct assertion |
| `test_recommended_action_refund` | clean return | Inline mocks |
| `test_recommended_action_replacement` | damaged item | Inline mocks |
| `test_recommended_action_reject` | policy violation | Inline mocks |
| `test_recommended_action_escalate` | ambiguous fraud | Inline mocks |
| `test_fraud_detection_cross_reference` | fraud DB match | Inline fraud DB mock |

Example test pattern:
```python
import pytest
from tools.policy_tools import check_return_policy

@pytest.mark.asyncio
async def test_eligible_return_within_window():
    result = await check_return_policy(order_id="ORD-001", customer_id="CUST-001")
    assert result["eligible"] is True
    assert result["recommended_action"] in ("refund", "replacement")
```

### Phase 4 — Verification

**Depends on**: All prior phases  
**Time estimate**: 15 min

```bash
ruff check . --fix
mypy tools/policy_tools.py agents/policy_agent.py guardrails/ tests/test_policy_agent.py
pytest tests/test_policy_agent.py -v -x
pytest tests/ --cov -v
```

### Phase 5 — Commit & PR

**Depends on**: Phase 4 (verification passes)  
**Time estimate**: 10 min

**Commit format** (per `CONTRIBUTING.md` — Conventional Commits):
```
<type>: <short description>

Types: feat: | fix: | test: | docs: | chore: | refactor:
```

Recommended commits for this feature:
```bash
git add tools/policy_tools.py agents/policy_agent.py
git commit -m "feat: implement policy agent with check_return_policy tool"

git add guardrails/pii_scrubber.py guardrails/sentiment_monitor.py guardrails/refund_cap.py
git commit -m "feat: add PII scrubber, sentiment monitor, and refund cap guardrails"

git add tests/test_policy_agent.py
git commit -m "test: add 10 unit tests for policy agent"

git add specs/002-policy-agent/spec.md specs/002-policy-agent/plan.md
git commit -m "docs: add spec and implementation plan for 002-policy-agent"
```

**Push**:
```bash
git push origin feature/policy-agent
```

**PR checklist** (per `CONTRIBUTING.md`):
- [ ] Branch up to date with `develop` (`git pull origin develop`)
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] No secrets committed (`git diff --staged`)
- [ ] PR title references issue (e.g. `feat: #12 implement policy_agent`)
- [ ] PR description explains: what changed, how to test, known risks
- [ ] No tool function signatures changed without Lead approval
- [ ] Model name not changed without Lead approval

PR merges to `develop` (not `main`).

## Dependency Graph

```
Phase 0 (tool) ──► Phase 1 (agent) ──► Phase 3 (tests)
                                              │
Phase 2 (guardrails) ─────────────────────────┘
                                              │
                                        Phase 4 (verify)
```

Phase 2 is independent — can be done in parallel with Phase 0/1.

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `openai-agents` API changes between SDK versions | Low | High | Pin to `>=0.1.0`, test against locked version |
| PII regex false positives (legit numbers redacted) | Medium | Medium | Keep patterns conservative; log stats |
| Sentiment monitor over-triggers on normal ALL CAPS | Medium | Low | Threshold in `.env`, tune after launch |
| Refund cap blocks when M3 output format differs | Medium | High | Unit test against agreed contract; guardrail is adaptable |
| Test fixtures not ready (Lead delay) | Medium | Low | Use inline mocks — no dependency on fixture files |

## File Change Summary

| File | Action | Lines (est.) |
|------|--------|-------------|
| `tools/policy_tools.py` | Create | ~80 |
| `agents/policy_agent.py` | Modify (fill stub) | ~30 |
| `guardrails/pii_scrubber.py` | Modify (fill stub) | ~40 |
| `guardrails/sentiment_monitor.py` | Modify (fill stub) | ~50 |
| `guardrails/refund_cap.py` | Modify (fill stub) | ~30 |
| `tests/test_policy_agent.py` | Modify (fill 10 stubs) | ~120 |
