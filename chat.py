"""
Chat - Natural language interface for Agent 01
Run:  python chat.py
"""

import asyncio
import json
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import logging

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("agents").setLevel(logging.WARNING)

os.environ["OPENTELEMETRY_TRACING"] = "0"
try:
    from agents import set_tracing_disabled

    set_tracing_disabled(True)
except ImportError:
    pass

try:
    from agents import set_default_openai_api, set_default_openai_client
    from openai import AsyncOpenAI

    key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    if key:
        client = AsyncOpenAI(api_key=key, base_url=base_url if base_url else None)
        set_default_openai_client(client)
    set_default_openai_api("chat_completions")
except ImportError:
    pass

ORDER_ID_PATTERN = re.compile(r"ORD[-_]?\d+", re.IGNORECASE)
CUSTOMER_ID_PATTERN = re.compile(r"CUST[-_]?\d+", re.IGNORECASE)
AMOUNT_PATTERN = re.compile(r"\$?(\d+(?:\.\d{2})?)", re.IGNORECASE)


def detect_order_id(text: str) -> str | None:
    m = ORDER_ID_PATTERN.search(text)
    return m.group(0).upper() if m else None


def detect_customer_id(text: str) -> str | None:
    m = CUSTOMER_ID_PATTERN.search(text)
    return m.group(0).upper() if m else None


def detect_amount(text: str) -> float | None:
    for m in AMOUNT_PATTERN.finditer(text):
        return float(m.group(1))
    return None


RETURN_KEYWORDS = {
    "return",
    "refund",
    "replace",
    "exchange",
    "send back",
    "damaged",
    "broken",
    "wrong item",
}
POLICY_KEYWORDS = {"eligible", "eligibility", "can i return", "policy", "window"}
PII_KEYWORDS = {"card", "credit card", "ssn", "social security", "bank account"}
SENTIMENT_KEYWORDS = {
    "sue",
    "lawyer",
    "attorney",
    "furious",
    "outrageous",
    "unacceptable",
    "desperate",
    "ruined",
}
REFUND_CAP_KEYWORDS = {"refund cap", "refund limit", "approval required"}


def classify_intent(text: str) -> str:
    lower = text.lower()
    has_return = any(kw in lower for kw in RETURN_KEYWORDS)
    has_policy = any(kw in lower for kw in POLICY_KEYWORDS)
    has_pii = any(kw in lower for kw in PII_KEYWORDS)
    has_sentiment = any(kw in lower for kw in SENTIMENT_KEYWORDS)
    has_refund_cap = any(kw in lower for kw in REFUND_CAP_KEYWORDS)

    if has_refund_cap:
        return "refund_cap"
    if has_sentiment and not has_return:
        return "sentiment"
    if has_pii:
        return "pii"
    if (has_return or has_policy) and detect_order_id(text):
        return "check_return"
    if has_return or has_policy:
        return "check_return"
    return "agent"


async def run_check_return(order_id: str | None, customer_id: str | None, text: str) -> str:
    from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check

    if not order_id:
        order_id = "ORD-001"
    if not customer_id:
        customer_id = "CUST-001"

    r = await check(order_id, customer_id)

    if r.get("success") is False:
        return f"[X] Error: {r['error']}"

    if r["eligible"]:
        action = r["recommended_action"]
        if action == "refund":
            return f"[OK] Eligible for refund! Order {order_id} is within the {r['return_window_days']}-day window ({r['days_since_purchase']} days since purchase)."
        elif action == "replacement":
            return "[OK] Eligible for replacement! Since your item arrived damaged, we will ship a replacement immediately."
        else:
            return f"[OK] Eligible. Recommended action: {action}."
    else:
        return f"[X] Not eligible. {r['reason']}"


async def run_pii_scrubber(text: str) -> str:
    from guardrails.pii_scrubber import RAW_PII_SCRUBBER as scrub

    r = await scrub(None, None, text)
    if r.tripwire_triggered:
        return f"[LOCK] PII detected and redacted.\nScrubbed: {r.output_info['scrubbed_message']}"
    return "[OK] No sensitive information detected."


async def run_sentiment(text: str) -> str:
    from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as score

    r = await score(None, None, text)
    s = r.output_info["score"]
    if r.tripwire_triggered:
        return f"[!] High distress detected! Score: {s}/1.0 - Escalating to human agent."
    return f"[OK] Sentiment OK. Score: {s}/1.0 (threshold: 0.8)"


async def run_refund_cap(text: str) -> str:
    from guardrails.refund_cap import RAW_REFUND_CAP as check

    text_lower = text.lower()
    cap = os.environ.get("REFUND_CAP_USD", "500")

    # Just asking about the cap, not testing a specific amount
    if text_lower in (
        "what is the refund cap?",
        "what is the refund cap",
        "refund cap",
        "refund limit",
    ):
        return f"The refund cap is ${cap}. Any refund up to ${cap} is auto-approved. Amounts above require human approval."

    amount = detect_amount(text) or 600.0
    r = await check(None, None, {"refund_amount": amount})
    if r.tripwire_triggered:
        return f"[BLOCKED] Refund of ${amount:.2f} exceeds ${cap} cap. Human approval required."
    return f"[OK] Refund of ${amount:.2f} is within cap - approved."


async def run_agent(text: str) -> str:
    from app_agents.triage_orchestrator import handle_customer_message

    customer_id = detect_customer_id(text) or "CUST-001"
    order_id = detect_order_id(text)

    try:
        result = await handle_customer_message(
            message=text,
            customer_id=customer_id,
            channel="cli",
        )
        intent = result["intent"]
        reasoning = result.get("reasoning", "")
        action = result.get("suggested_action", "")
        resolution = result.get("resolution", {})

        lines = [f"[AI] Intent: {intent}"]
        if reasoning:
            lines.append(f"Reasoning: {reasoning}")
        if action:
            lines.append(f"Action: {action}")

        # Handle Pydantic models in resolution
        if hasattr(resolution, "model_dump"):
            resolution = resolution.model_dump()
        if resolution:
            lines.append(f"Details: {json.dumps(resolution, indent=2)}")

        return "\n".join(lines)
    except Exception as e:
        return f"[!] Agent error: {e}. Trying tool directly...\n{await run_check_return(order_id, customer_id, text)}"


GREETINGS = {
    "hello",
    "hi",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "sup",
    "yo",
}
HELP_KEYWORDS = {"help", "what can you do", "capabilities", "features", "how does this work"}
UNRELATED = {
    "weather",
    "stock",
    "news",
    "sports",
    "joke",
    "poem",
    "story",
    "movie",
    "song",
    "recipe",
}


def is_generic_message(text_lower: str) -> str | None:
    if any(text_lower.startswith(g) or text_lower == g for g in GREETINGS):
        return "greeting"
    if any(kw in text_lower for kw in HELP_KEYWORDS):
        return "help"
    if any(kw in text_lower for kw in UNRELATED):
        return "unrelated"
    return None


async def respond(text: str) -> str:
    text_lower = text.lower()

    kind = is_generic_message(text_lower)
    if kind == "greeting":
        return "Hello! I am Agent 01, your return processing assistant. Try saying: 'Can I return my order ORD-001?' or 'My credit card is 4111-1111-1111-1111'."
    if kind == "help":
        return "I can help with:\n  - Return eligibility (e.g. 'Can I return ORD-001?')\n  - PII redaction (e.g. 'My card is 4111-1111-1111-1111')\n  - Sentiment monitoring (e.g. 'I will sue you!')\n  - Refund capping (e.g. 'Process a refund of $600')\n  - Policy lookups via LLM (e.g. 'What is the return policy?')\n  - Full demo scenarios with 'demo'"
    if kind == "unrelated":
        return "I specialize in return processing and policy enforcement. I can check return eligibility, detect PII in messages, monitor customer sentiment, and enforce refund caps. Try typing a return-related question!"

    if "pii" in text_lower or "scrub" in text_lower:
        return await run_pii_scrubber(text)
    elif "demo" in text_lower:
        return "Run: python demo.py for full demo with 17 return scenarios."
    elif "sentiment" in text_lower:
        return await run_sentiment(text)
    elif "refund cap" in text_lower or "refund limit" in text_lower:
        return await run_refund_cap(text)
    elif "refund" in text_lower and detect_amount(text):
        return await run_refund_cap(text)
    elif "card" in text_lower or "ssn" in text_lower or "bank account" in text_lower:
        return await run_pii_scrubber(text)
    else:
        intent = classify_intent(text)
        if intent == "check_return":
            order_id = detect_order_id(text)
            customer_id = detect_customer_id(text)
            return await run_check_return(order_id, customer_id, text)
        elif intent == "sentiment":
            return await run_sentiment(text)
        elif intent == "refund_cap":
            return await run_refund_cap(text)
        else:
            return await run_agent(text)


async def main():
    print("=" * 58)
    print("  Agent 01 - Chat Interface")
    print("  Just type naturally. No commands needed.")
    print("=" * 58)
    print()
    print("  Try saying:")
    print('    "Can I return my order ORD-001?"')
    print('    "My card number is 4111-1111-1111-1111"')
    print('    "I will sue you this is outrageous"')
    print('    "What is the refund cap?"')
    print('    "Process a refund of $600"')
    print("    quit  -  exit")
    print()

    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in ("quit", "exit", "q"):
            break

        response = await respond(text)
        print(f"\nAgent: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
