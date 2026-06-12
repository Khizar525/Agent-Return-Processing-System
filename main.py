"""
Agent 01 — Customer Support & Returns Orchestrator
FastAPI webhook receiver — entry point for all inbound channels.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
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

from app_agents.triage_orchestrator import handle_customer_message

app = FastAPI(
    title="Agent 01 — Customer Support & Returns Orchestrator",
    version="0.1.0",
)


class InboundMessage(BaseModel):
    customer_id: str
    channel: str          # web_chat | email | whatsapp | sms
    raw_message: str
    session_id: str | None = None


class ResolutionResponse(BaseModel):
    session_id: str
    resolution: str
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
