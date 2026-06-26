"""
CLI — Agent 01 Customer Support System
Usage:
    python cli.py shell                       Interactive shell — test everything
    python cli.py server                      Start the backend API server
    python cli.py check <order> <cust>        Check return policy
    python cli.py guardrail pii <msg>         Test PII scrubber
    python cli.py guardrail sentiment <msg>   Test sentiment monitor
    python cli.py guardrail refund <amt>      Test refund cap
    python cli.py run <message>               Run triage agent
    python cli.py agent <message>             Run policy agent
"""

import asyncio
import json
import logging
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("agents").setLevel(logging.WARNING)
os.environ["OPENTELEMETRY_TRACING"] = "0"
try:
    from agents import set_tracing_disabled

    set_tracing_disabled(True)
except ImportError:
    pass

# Load .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Configure SDK for Gemini (OpenAI-compatible endpoint uses chat_completions)
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


def print_json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


# ── Command: check ────────────────────────────────────────────────────────


async def cmd_check(order_id: str, customer_id: str) -> None:
    from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check

    result = await check(order_id, customer_id)
    print_json(result)


# ── Command: guardrail ────────────────────────────────────────────────────


async def cmd_guardrail_pii(message: str) -> None:
    from guardrails.pii_scrubber import RAW_PII_SCRUBBER as check

    output = await check(None, None, message)
    print(f"Tripwire triggered: {output.tripwire_triggered}")
    print(f"Scrubbed message:  {output.output_info['scrubbed_message']}")


async def cmd_guardrail_sentiment(message: str) -> None:
    from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as check

    output = await check(None, None, message)
    print_json(output.output_info)


async def cmd_guardrail_refund(amount: str) -> None:
    from guardrails.refund_cap import RAW_REFUND_CAP as check

    try:
        amt = float(amount)
    except ValueError:
        print("Amount must be a number")
        sys.exit(1)
    output = await check(None, None, {"refund_amount": amt})
    print_json(output.output_info)


# ── Command: run (triage agent) ──────────────────────────────────────────


async def cmd_run(message: str) -> None:
    from agents import Runner
    from app_agents.triage_orchestrator import triage_agent

    print(f"[Running TriageAgent with: '{message}']")
    result = await Runner.run(triage_agent, input=message)
    print(f"Output:\n{result.final_output}")


# ── Command: agent (policy agent) ────────────────────────────────────────


async def cmd_agent(message: str) -> None:
    from agents import Runner
    from app_agents.policy_agent import policy_agent

    print(f"[Running PolicyAgent with: '{message}']")
    result = await Runner.run(policy_agent, input=message)
    print(f"Output:\n{result.final_output}")


# ── Command: chat ─────────────────────────────────────────────────────────


async def cmd_chat() -> None:
    import httpx

    base = os.environ.get("API_BASE_URL", "http://localhost:8000")
    session_id: str | None = None
    print(f"Connected to {base}. Type 'quit' to exit.\n")

    while True:
        try:
            text = input("You: ")
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        if not text.strip():
            continue

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{base}/webhook/message",
                    json={
                        "customer_id": "CUST-001",
                        "channel": "web_chat",
                        "raw_message": text,
                        "session_id": session_id,
                    },
                    timeout=60,
                )
                data = resp.json()
                session_id = data.get("session_id", session_id)
                print(f"\nAgent: {data.get('resolution', 'No response')}")
                print(f"Chain: {data.get('agent_chain', [])}\n")
        except Exception as e:
            print(f"Error: {e}")


# ── Command: shell (interactive) ─────────────────────────────────────────


async def cmd_shell() -> None:
    from tools.policy_tools import RAW_CHECK_RETURN_POLICY as check_return
    from guardrails.pii_scrubber import RAW_PII_SCRUBBER as scrub_pii
    from guardrails.sentiment_monitor import RAW_SENTIMENT_MONITOR as score_sent
    from guardrails.refund_cap import RAW_REFUND_CAP as check_refund
    from chat import respond as chat_respond

    print("\n" + "=" * 56)
    print("  Agent 01 — Interactive Shell")
    print("=" * 56)
    print("  Just type naturally, or use prefix commands:")
    print("    check <order> <cust>      Check return policy")
    print("    pii <msg>                 Test PII scrubber")
    print("    sentiment <msg>           Test sentiment monitor")
    print("    refund <amt>              Test refund cap")
    print("    agent <msg>               Run policy agent (needs API key)")
    print("    triage <msg>              Run triage agent (needs API key)")
    print("    demo                      Run full scenario demo")
    print("    help                      Show this menu")
    print("    quit                      Exit")
    print("=" * 56)
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text == "quit":
            break
        if text == "help":
            print("Commands: check, pii, sentiment, refund, agent, triage, demo, quit")
            continue
        if text == "demo":
            from demo import main as run_demo

            await run_demo()
            continue
        parts = text.split(maxsplit=1)
        cmd = parts[0] if parts else ""
        if cmd in ("check", "pii", "sentiment", "refund", "agent", "triage") and len(parts) >= 2:
            args = parts[1]
            if cmd == "check":
                sub = args.split()
                if len(sub) < 2:
                    print("Usage: check <order_id> <customer_id>")
                    continue
                r = await check_return(sub[0], sub[1])
                print_json(r)
            elif cmd == "pii":
                r = await scrub_pii(None, None, args)
                print(f"  Triggered: {r.tripwire_triggered}")
                print(f"  Scrubbed:  {r.output_info['scrubbed_message']}")
            elif cmd == "sentiment":
                r = await score_sent(None, None, args)
                s = r.output_info
                print(f"  Score: {s['score']} | Escalate: {s['escalate']}")
            elif cmd == "refund":
                try:
                    r = await check_refund(None, None, {"refund_amount": float(args)})
                    print_json(r.output_info)
                except ValueError:
                    print("Amount must be a number")
            elif cmd == "agent":
                from agents import Runner
                from app_agents.policy_agent import policy_agent

                print("  [Calling PolicyAgent...]")
                r = await Runner.run(policy_agent, input=args)
                print(f"  Output: {r.final_output}")
            elif cmd == "triage":
                from agents import Runner
                from app_agents.triage_orchestrator import triage_agent

                print("  [Calling TriageAgent...]")
                r = await Runner.run(triage_agent, input=args)
                print(f"  Output: {r.final_output}")
        else:
            # No recognized command prefix — use natural language
            response = await chat_respond(text)
            print(f"  {response}")


# ── Command: server ───────────────────────────────────────────────────────


def cmd_server() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting server on http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)


# ── Main dispatcher ───────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "server":
        cmd_server()

    elif cmd == "check":
        if len(sys.argv) < 4:
            print("Usage: python cli.py check <order_id> <customer_id>")
            sys.exit(1)
        asyncio.run(cmd_check(sys.argv[2], sys.argv[3]))

    elif cmd == "guardrail":
        if len(sys.argv) < 4:
            print("Usage: python cli.py guardrail <pii|sentiment|refund> <value>")
            sys.exit(1)
        sub = sys.argv[2]
        value = " ".join(sys.argv[3:])
        if sub == "pii":
            asyncio.run(cmd_guardrail_pii(value))
        elif sub == "sentiment":
            asyncio.run(cmd_guardrail_sentiment(value))
        elif sub == "refund":
            asyncio.run(cmd_guardrail_refund(value))
        else:
            print(f"Unknown guardrail: {sub}")
            sys.exit(1)

    elif cmd == "chat":
        asyncio.run(cmd_chat())

    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: python cli.py run <message>")
            sys.exit(1)
        asyncio.run(cmd_run(" ".join(sys.argv[2:])))

    elif cmd == "agent":
        if len(sys.argv) < 3:
            print("Usage: python cli.py agent <message>")
            sys.exit(1)
        asyncio.run(cmd_agent(" ".join(sys.argv[2:])))

    elif cmd == "shell":
        asyncio.run(cmd_shell())

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
