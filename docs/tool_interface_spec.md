# Tool Interface Specification

**Owner:** Project Lead  
**Status:** Authoritative — do not change function signatures without Lead approval  
**Available:** Week 1, Day 3  

> This document defines the exact function signatures, input/output schemas,
> and error contracts for every tool in the system. All teammates must read
> this before writing any tool implementation.

---

## Rules for All Tools

1. Every tool must be decorated with `@function_tool` from `openai-agents`.
2. Every tool must be `async`.
3. Every tool must handle API errors gracefully — never raise an unhandled exception.
   Catch all external API errors and return `{ "success": false, "error": "<message>" }`.
4. Never hardcode credentials — use `os.environ.get("KEY_NAME")`.
5. All timestamps must be ISO-8601 strings (e.g. `"2026-05-19T10:30:00Z"`).

---

## CRM Tools — `tools/crm_tools.py` (Member 3)

### `get_customer_profile(customer_id: str) -> dict`

```python
# Returns:
{
    "customer_id":   str,
    "name":          str,
    "email":         str,
    "phone":         str,
    "loyalty_tier":  str,        # "bronze" | "silver" | "gold" | "platinum"
    "order_history": list[dict], # last 10 orders
    "past_returns":  list[dict], # last 5 returns
    "fraud_flag":    bool,
    "fraud_reason":  str | None,
    "error":         str | None,
}
```

---

## Payment Tools — `tools/payment_tools.py` (Member 3)

### `process_refund(order_id: str, amount_usd: float, method: str) -> dict`

```python
# method: "stripe" | "paypal"
# MUST raise ValueError("human_approval_required") if amount_usd > REFUND_CAP_USD

# Returns:
{
    "success":         bool,
    "transaction_id":  str,
    "refund_amount":   float,
    "currency":        str,   # always "USD"
    "estimated_days":  int,   # business days until customer sees refund
    "error":           str | None,
}
```

---

## Shipping Tools — `tools/shipping_tools.py` (Member 3)

### `create_return_label(order_id: str, carrier: str) -> dict`

```python
# carrier: "fedex" | "ups"

# Returns:
{
    "success":          bool,
    "label_url":        str,
    "tracking_number":  str,
    "carrier":          str,
    "expires_at":       str,   # ISO-8601
    "error":            str | None,
}
```

### `create_replacement_order(order_id: str) -> dict`

```python
# Returns:
{
    "success":                bool,
    "replacement_order_id":   str,
    "expedited":              bool,
    "estimated_delivery":     str,   # ISO-8601
    "error":                  str | None,
}
```

---

## Notification Tools — `tools/notification_tools.py` (Member 4)

### `send_notification(customer_id: str, channel: str, subject: str, body: str) -> dict`

```python
# channel: "email" | "sms"
# subject: used for email only, pass "" for sms

# Returns:
{
    "success":      bool,
    "message_id":   str,
    "channel":      str,
    "delivered_at": str,   # ISO-8601
    "error":        str | None,
}
```

---

## Helpdesk Tools — `tools/helpdesk_tools.py` (Member 4)

### `create_human_ticket(context_bundle: dict) -> dict`

```python
# context_bundle MUST contain ALL of these keys — missing keys will fail validation:
{
    "customer_id":        str,
    "session_id":         str,
    "agent_chain":        list[str],
    "intent":             str,
    "policy_decision":    dict | None,
    "resolution_action":  str | None,
    "escalation_reason":  str,
    "order_history":      list[dict],
    "timestamps":         dict,
    "raw_conversation":   list[dict],
}

# Returns:
{
    "success":    bool,
    "ticket_id":  str,
    "ticket_url": str,
    "priority":   str,   # "low" | "normal" | "high" | "urgent"
    "error":      str | None,
}
```

### `log_resolution(session_id: str, outcome: dict) -> dict`

```python
# Returns:
{
    "success":    bool,
    "record_id":  str,
    "error":      str | None,
}
```

---

## Policy Tools — `tools/policy_tools.py` (Member 2)

### `check_return_policy(order_id: str, customer_id: str) -> dict`

```python
# Returns:
{
    "eligible":            bool,
    "reason":              str,
    "recommended_action":  str,   # "refund" | "replacement" | "reject" | "escalate"
    "return_window_days":  int,
    "days_since_purchase": int,
    "item_category":       str,
    "exclusion_reason":    str | None,
    "fraud_signal":        bool,
    "error":               str | None,
}
```

---

## Error Contract (all tools)

If an external API call fails for any reason, tools must return:

```python
{
    "success": False,
    "error": "<human-readable description of what failed>",
    # ... all other fields set to None or empty defaults
}
```

**Never** let an API error bubble up as an unhandled Python exception.
The agent runtime will treat unhandled exceptions as system failures.
