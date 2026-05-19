"""
Agent 01 — Customer Support & Returns Orchestrator
FastAPI webhook receiver — entry point for all inbound channels.
"""

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from agents.triage_orchestrator import handle_customer_message

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


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "agent01-customer-support"}


@app.post("/webhook/message", response_model=ResolutionResponse)
async def receive_message(payload: InboundMessage):
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
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
