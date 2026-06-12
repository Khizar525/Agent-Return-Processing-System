# AGENTS.md

Active feature: `002-policy-agent` (Member 2).  
Branch: `feature/policy-agent`.

## Commands

```bash
pip install -r requirements.txt     # deps
pip install -e ".[dev]"            # + dev deps (pytest, ruff, mypy)
uvicorn main:app --reload           # dev server
pytest tests/test_policy_agent.py -v -x  # single test file, stop on first failure
pytest tests/ --cov -v              # all tests + coverage
ruff check .                        # lint (line-length=100)
mypy .                              # typecheck (strict mode, py311)
```

Run `ruff check . --fix; mypy .; pytest tests/ -v` in that order before PR.

## SDD Workflow

Specs go in `specs/<feature>/spec.md`, plans in `specs/<feature>/plan.md`.  
Use `.specify/templates/spec-template.md` to write specs.  
PHRs are auto-created under `history/prompts/<feature>/` after every user prompt (SDD rule — do not skip).

## Architecture

- **Pattern**: Manager + Handoff Hybrid (see `docs/ADR-001.md`). Handoff for multi-step specialist flows (`return_request`), tool-call for single-step lookups (`order_status`).
- **Entry**: `main.py` → FastAPI `POST /webhook/message` → `triage_orchestrator.handle_customer_message()`.
- **Entry agent**: `app_agents/triage_orchestrator.py` — `gemini-2.0-flash`, classifies intent, hands off.
- **Policy agent**: `app_agents/policy_agent.py` — validated by you. Uses `gemini-2.0-flash`. Enforces: return window (30d), exclusion list, fraud flag check, fraud DB cross-reference.

## Code Conventions

- Every file: module docstring with owner, purpose, output schema.
- Cross-team imports commented out: `# from tools.crm_tools import ...  # uncomment after M3 merges`.
- All tools: `@function_tool` (openai-agents), `async def`, return dict with `"success": bool, "error": str | None`.
- All agents: `Agent(name=..., instructions=..., model=..., tools=[...])` from `agents` package.
- Type hints: Python 3.11+ (`str | None`). Ruff line-length=100. mypy strict.
- Commit convention: Conventional Commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`, `refactor:`).

## Member 2 Inventory

| File | Status |
|------|--------|
| `agents/policy_agent.py` | Stub — implement agent + `check_return_policy` tool |
| `tools/policy_tools.py` | Not created yet — create with `check_return_policy()` per `docs/tool_interface_spec.md` |
| `guardrails/pii_scrubber.py` | Stub — input guardrail for triage agent |
| `guardrails/refund_cap.py` | Stub — output guardrail for resolution agent |
| `guardrails/sentiment_monitor.py` | Stub — input guardrail for triage agent |
| `tests/test_policy_agent.py` | 10 stubs — fill before PR (covers window, exclusion, fraud flag, JSON output, all 4 recommended_actions) |
| `specs/002-policy-agent/spec.md` | Not created yet — create first (use `.specify/templates/spec-template.md`) |
| `specs/002-policy-agent/plan.md` | Empty — fill after spec |

Policy agent output JSON contract: `{"eligible": bool, "reason": str, "recommended_action": "refund"|"replacement"|"reject"|"escalate"}`.

## Tool Interface Contract

All tools in `docs/tool_interface_spec.md` — authoritative. Do not change signatures without Lead approval.
Key for you: tool `check_return_policy(order_id, customer_id)` returns `eligible`, `reason`, `recommended_action`, `return_window_days`, `days_since_purchase`, `item_category`, `exclusion_reason`, `fraud_signal`, `error`.

## Branch & Team

- `main` (protected) ← `develop` ← `feature/*`
- M2 owns `feature/policy-agent`. PRs merge to `develop`.
- Your guardrails plug into triage/resolution agents owned by Lead/M3 — use commented-out import pattern until they merge.

## Test Fixtures

`tests/fixtures/` expects synthetic JSON: `customers.json`, `orders.json`, `fraud_signals.json` (Lead to populate). Use mocks until they exist.
