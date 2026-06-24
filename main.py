"""
Agent 01 — Customer Support & Returns Orchestrator
FastAPI webhook receiver — entry point for all inbound channels.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ── Datadog APM instrumentation ───────────────────────────────────────────
try:
    from infra.datadog_setup import configure_datadog

    configure_datadog()
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
        # Force Chat Completions API (SDK defaults to Responses API which
        # not all providers support).
        set_default_openai_api("chat_completions")

        # ── Provider compatibility layer ────────────────────────────────
        # Free-tier OpenAI-compatible providers (OpenRouter, Groq, Cerebras)
        # have two limitations vs the official OpenAI API:
        #   1. Model names with "/" (e.g. "openai/gpt-oss-120b:free") are
        #      misinterpreted as provider prefixes by MultiProvider.
        #   2. `response_format` (structured output) cannot be combined
        #      with `tools` in the same request.
        # We patch both for broad provider compatibility.

        # Patch 1: MultiProvider passes full model names through as-is
        import agents.models.multi_provider as _mp

        _orig_mp_init = _mp.MultiProvider.__init__

        def _patched_mp_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("unknown_prefix_mode", "model_id")
            _orig_mp_init(self, *args, **kwargs)

        _mp.MultiProvider.__init__ = _patched_mp_init  # type: ignore[method-assign]

        # Patch 2: Strip response_format when tools/handoffs are present
        # (providers like OpenRouter/Groq reject the combination)
        import agents.models.openai_chatcompletions as _chat

        _orig_fetch = _chat.OpenAIChatCompletionsModel._fetch_response

        async def _compat_fetch(  # type: ignore[no-untyped-def]
            self, system_instructions, input, model_settings, tools,
            output_schema, handoffs, span, tracing, stream=False,
            prompt=None,
        ):
            has_tools = bool(tools) or bool(handoffs)
            if has_tools and output_schema and not output_schema.is_plain_text():
                output_schema = None
            return await _orig_fetch(
                self, system_instructions, input, model_settings, tools,
                output_schema, handoffs, span, tracing, stream, prompt,
            )

        _chat.OpenAIChatCompletionsModel._fetch_response = _compat_fetch  # type: ignore[assignment]

except ImportError:
    pass

from app_agents.triage_orchestrator import handle_customer_message

app = FastAPI(
    title="Agent 01 — Customer Support & Returns Orchestrator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InboundMessage(BaseModel):
    customer_id: str
    channel: str  # web_chat | email | whatsapp | sms
    raw_message: str
    session_id: str | None = None


class ResolutionResponse(BaseModel):
    session_id: str
    resolution: dict | str
    agent_chain: list[str]


@app.get("/")
async def root() -> str:
    import os
    from dotenv import load_dotenv

    load_dotenv()
    has_key = bool(os.environ.get("OPENAI_API_KEY"))
    return f"""<html><body style="font-family:sans-serif;max-width:700px;margin:40px">
<h2>Agent 01 — Customer Support & Returns</h2>
<form method="post" action="/webhook/message" enctype="application/json">
  <p><b>Test the API:</b></p>
  <pre style="background:#f4f4f4;padding:12px;border-radius:6px">
curl -X POST http://localhost:8000/webhook/message \\
  -H "Content-Type: application/json" \\
  -d '{{"customer_id":"CUST-001","channel":"web_chat","raw_message":"I want to return my order ORD-001"}}'
  </pre>
  <p><b>Or use the CLI:</b> <code>python cli.py chat</code></p>
  <p><b>Or run full demo:</b> <code>python demo.py</code></p>
  <p>API key configured: {"<span style='color:green'>YES</span>" if has_key else "<span style='color:red'>NO</span>"}</p>
  <p><a href="/health">/health</a></p>
</form></body></html>"""


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "agent01-customer-support"}


@app.post("/webhook/message", response_model=ResolutionResponse)
async def receive_message(payload: InboundMessage) -> ResolutionResponse:
    """
    Main inbound webhook — receives messages from Kafka consumers
    (one consumer per channel: web_chat, email, whatsapp, sms).
    """
    try:
        result = await handle_customer_message(
            message=payload.raw_message,
            customer_id=payload.customer_id,
            channel=payload.channel,
            session_id=payload.session_id,
        )
        return ResolutionResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
