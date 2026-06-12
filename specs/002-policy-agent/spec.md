# Feature Specification: 002 — Policy Agent & Guardrails

**Feature Branch**: `feature/policy-agent`
**Created**: 2026-05-20
**Status**: Draft
**Owner**: Member 2
**Plan**: `specs/002-policy-agent/plan.md`

## Member 2 Deliverables

| File | Type | Description |
|------|------|-------------|
| `tools/policy_tools.py` | Create | `check_return_policy` tool per `docs/tool_interface_spec.md` |
| `agents/policy_agent.py` | Modify | Policy agent using `Agent(name=..., model="gemini-2.0-flash", tools=[...])` |
| `guardrails/pii_scrubber.py` | Modify | PII redaction input guardrail via `@input_guardrail` |
| `guardrails/sentiment_monitor.py` | Modify | CSAT risk scoring input guardrail via `@input_guardrail` |
| `guardrails/refund_cap.py` | Modify | Refund limit output guardrail via `@output_guardrail` |
| `tests/test_policy_agent.py` | Modify | 10 unit test cases |

## Tool Contract — `check_return_policy`

Per `docs/tool_interface_spec.md`. Does not involve other members' code.

**Signature**: `check_return_policy(order_id: str, customer_id: str) -> dict`

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

**Error return** (order/customer not found, or unrecoverable failure):
```python
{
    "success": False,
    "error": "<human-readable message>",
    # all other fields set to None or empty defaults
}
```

**Rules**:
1. `@function_tool` decorator from `openai-agents`, `async def`
2. Never raise unhandled exceptions — catch and return error dict
3. Business rules from `.env` via `os.environ.get()` with hardcoded defaults
4. All timestamps ISO-8601

## Policy Agent Output Contract

```python
{
    "eligible":           bool,
    "reason":             str,
    "recommended_action": "refund" | "replacement" | "reject" | "escalate",
}
```

## Guardrail Contracts

**PII Scrubber**: `@input_guardrail` → `GuardrailFunctionOutput(tripwire_triggered=bool, output_dict={"scrubbed_message": str})`

**Sentiment Monitor**: `@input_guardrail` → `GuardrailFunctionOutput(tripwire_triggered=bool, output_dict={"score": float, "escalate": bool})`

**Refund Cap**: `@output_guardrail` → `GuardrailFunctionOutput(tripwire_triggered=bool, output_dict=...)` — triggers when `refund_amount > REFUND_CAP_USD`

## User Stories

### User Story 1 — Return Eligibility Validation (Priority: P1)

The policy agent validates return eligibility based on return window and exclusion list.

**Independent Test**: Call `check_return_policy` with an in-window non-excluded item (expect eligible=true) and an out-of-window item (expect eligible=false with reason).

**Acceptance Scenarios**:

1. **Given** an order placed 15 days ago with a non-excluded item category, **When** `check_return_policy` is called, **Then** it returns `eligible: true`, `days_since_purchase: 15`, `exclusion_reason: null`.
2. **Given** an order placed 45 days ago, **When** `check_return_policy` is called, **Then** it returns `eligible: false`, `reason` explains the 30-day window was exceeded.
3. **Given** an order containing a digital download item, **When** `check_return_policy` is called, **Then** it returns `eligible: false`, `exclusion_reason` identifies the item category as excluded.

---

### User Story 2 — Fraud Detection & Cross-Reference (Priority: P1)

The policy agent checks fraud indicators and cross-references against a fraud signal database.

**Independent Test**: Call `check_return_policy` with a fraud-flagged customer (expect eligible=false, fraud_signal=true, reject) and a fraud DB matched customer (expect eligible=false, fraud_signal=true, escalate).

**Acceptance Scenarios**:

1. **Given** a customer profile with `fraud_flag: true`, **When** `check_return_policy` is called, **Then** it returns `eligible: false`, `fraud_signal: true`, `recommended_action: "reject"`.
2. **Given** a customer with no fraud flag but a match in the fraud signal database, **When** `check_return_policy` is called, **Then** it returns `eligible: false`, `fraud_signal: true`, `recommended_action: "escalate"`.
3. **Given** a clean customer with no fraud indicators, **When** `check_return_policy` runs, **Then** `fraud_signal` is `false` and eligibility is determined by other rules only.

---

### User Story 3 — Recommended Actions (Priority: P1)

Based on eligibility, the tool recommends one of four actions.

**Independent Test**: Call `check_return_policy` with four scenarios — clean return (expect refund), damaged item (expect replacement), policy violation (expect reject), fraud DB match without flag (expect escalate).

**Acceptance Scenarios**:

1. **Given** an eligible return with a returnable item, **When** policy check completes, **Then** `recommended_action` is `"refund"`.
2. **Given** an eligible return for a damaged/shipping-damaged item, **When** policy check completes, **Then** `recommended_action` is `"replacement"`.
3. **Given** an ineligible return due to policy violation, **When** policy check completes, **Then** `recommended_action` is `"reject"`.
4. **Given** an ambiguous fraud signal (possible match, not confirmed), **When** policy check completes, **Then** `recommended_action` is `"escalate"`.

---

### User Story 4 — PII Scrubber Input Guardrail (Priority: P2)

Redacts PII from inbound customer messages before any agent processes them.

**Independent Test**: Call the guardrail function directly with messages containing credit card numbers, SSNs, bank accounts, and a clean message. Assert `[REDACTED]` appears in output for PII messages and unchanged for clean.

**Acceptance Scenarios**:

1. **Given** a message containing a credit card number "4111-1111-1111-1111", **When** the guardrail runs, **Then** the number is replaced with `[REDACTED]`.
2. **Given** a message containing an SSN "123-45-6789", **When** the guardrail runs, **Then** the SSN is replaced with `[REDACTED]`.
3. **Given** a message containing a bank account number "87654321", **When** the guardrail runs, **Then** the account number is replaced with `[REDACTED]`.
4. **Given** a message with no PII patterns, **When** the guardrail runs, **Then** the message passes through unchanged (`tripwire_triggered: false`).

---

### User Story 5 — Sentiment Monitor Input Guardrail (Priority: P2)

Scores inbound messages for CSAT risk and triggers escalation routing when threshold exceeded.

**Independent Test**: Feed angry messages (legal keywords, ALL CAPS, distress words) and neutral messages. Assert angry messages score > 0.8 with tripwire_triggered=true, neutral messages score ≤ 0.8 with tripwire_triggered=false.

**Acceptance Scenarios**:

1. **Given** a message containing legal keywords ("lawyer", "sue") and ALL CAPS phrasing, **When** the guardrail runs, **Then** sentiment score > 0.8 and `tripwire_triggered: true`.
2. **Given** a message with multiple exclamation marks and emotional distress indicators ("desperate", "ruined"), **When** the guardrail runs, **Then** sentiment score > 0.8 and `tripwire_triggered: true`.
3. **Given** a neutral message ("I'd like to check my order status"), **When** the guardrail runs, **Then** sentiment score ≤ 0.8 and `tripwire_triggered: false`.

---

### User Story 6 — Refund Cap Output Guardrail (Priority: P2)

Blocks resolution outputs where refund amount exceeds cap, returning human approval required signal.

**Independent Test**: Call the guardrail with output dicts containing refund_amount=$600 (> cap) and refund_amount=$200 (≤ cap). Assert first blocks with tripwire_triggered=true, second passes through unchanged.

**Acceptance Scenarios**:

1. **Given** a resolution output with a refund amount of $600 (> cap), **When** the guardrail runs, **Then** `tripwire_triggered: true`, output indicates `human_approval_required`.
2. **Given** a resolution output with a refund amount of $200 (≤ cap), **When** the guardrail runs, **Then** `tripwire_triggered: false` and output passes through unchanged.

---

## Requirements

### Functional Requirements

- **FR-001**: `check_return_policy` MUST use `@function_tool` decorator and be `async def`.
- **FR-002**: `check_return_policy` MUST return the success dict per `docs/tool_interface_spec.md` when inputs are valid.
- **FR-003**: `check_return_policy` MUST return `{ "success": false, "error": "..." }` on invalid inputs or failures (never raise).
- **FR-004**: Return window MUST be validated against `RETURN_WINDOW_DAYS` env var (default 30).
- **FR-005**: Exclusion list MUST block `digital_goods`, `perishables`, and `final_sale` item categories.
- **FR-006**: `fraud_flag` on customer profile MUST set `fraud_signal: true` and block eligibility.
- **FR-007**: Fraud DB cross-reference MUST be performed before approving; match sets `fraud_signal: true`.
- **FR-008**: `recommended_action` MUST be one of: `"refund"`, `"replacement"`, `"reject"`, `"escalate"`.
- **FR-009**: Policy agent MUST be defined as `Agent(name="PolicyAgent", model="gemini-2.0-flash", tools=[check_return_policy])`.
- **FR-010**: Policy agent output MUST be valid JSON matching the output contract.
- **FR-011**: PII scrubber MUST use `@input_guardrail` and return `GuardrailFunctionOutput`.
- **FR-012**: PII scrubber MUST replace credit card numbers, SSNs, bank account numbers, and embedded tokens with `[REDACTED]`.
- **FR-013**: Sentiment monitor MUST use `@input_guardrail` and return `GuardrailFunctionOutput`.
- **FR-014**: Sentiment monitor MUST score 0.0–1.0 and set `tripwire_triggered: true` when score > threshold.
- **FR-015**: Refund cap MUST use `@output_guardrail` and return `GuardrailFunctionOutput`.
- **FR-016**: Refund cap MUST block refunds > `REFUND_CAP_USD` (default $500) via `tripwire_triggered: true`.
- **FR-017**: Refund cap MUST pass through outputs where amount ≤ cap unchanged.
- **FR-018**: Cross-team imports (e.g. `get_customer_profile`) MUST use commented-out pattern as stubs.

### Excluded from this spec (other members)

| Item | Owner | Dependency pattern |
|------|-------|-------------------|
| `get_customer_profile` tool | Member 3 | Commented-out import in policy_agent.py |
| Triage Orchestrator guardrail wiring | Lead | Guardrails provided as importable functions |
| Resolution Agent guardrail wiring | Member 3 | Guardrail provided as importable function |
| Integration tests | Lead | Requires all agents merged first |
| Test fixture files | Lead | Inline mocks used until fixtures arrive |

## Edge Cases

- **Missing order_id**: `{ "success": false, "error": "order not found" }`
- **Missing customer_id**: `{ "success": false, "error": "customer not found" }`
- **Order-customer mismatch**: `{ "success": false, "error": "Order does not belong to this customer" }`
- **Compound violations**: Window exceeded AND fraud flag — both reported, eligible=false
- **Missing env var RETURN_WINDOW_DAYS**: Default 30
- **Missing env var REFUND_CAP_USD**: Default 500
- **Missing env var SENTIMENT_ESCALATION_THRESHOLD**: Default 0.8

## Success Criteria

- **SC-001**: All 4 recommended_action branches ("refund", "replacement", "reject", "escalate") return the correct value per FR-008 in their respective unit tests.
- **SC-002**: Return window correctly accepts ≤30 days and rejects >30 days.
- **SC-003**: Fraud detection flags both `fraud_flag` accounts and DB cross-reference matches.
- **SC-004**: PII scrubber removes all 4 pattern types.
- **SC-005**: Sentiment monitor correctly scores and triggers above threshold.
- **SC-006**: Refund cap blocks >$500 and passes ≤$500.
- **SC-007**: All 10 test cases in `tests/test_policy_agent.py` pass.
