"""
Integration Tests — Full Pipeline
Owner: Project Lead

Tests the end-to-end flow: Triage → Policy → Resolution → Communication.
Run after all specialist agent branches have been merged to develop.

Run:
    pytest tests/test_integration.py -v
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_return_message():
    return {
        "customer_id": "cust_001",
        "channel": "web_chat",
        "raw_message": "I want to return my order #12345. It arrived damaged.",
    }


@pytest.fixture
def sample_tracking_message():
    return {
        "customer_id": "cust_002",
        "channel": "email",
        "raw_message": "Where is my order? It's been 10 days and I haven't received it.",
    }


@pytest.fixture
def sample_escalation_message():
    return {
        "customer_id": "cust_003",
        "channel": "web_chat",
        "raw_message": "This is absolutely unacceptable. I'm going to take legal action if this isn't resolved NOW.",
    }


# ---------------------------------------------------------------------------
# TODO (Lead): implement integration tests below once all agents are merged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_return_request_routes_to_policy_agent(sample_return_message):
    """
    A return_request message must be routed to the Policy Agent.
    The pipeline should complete in < 30 seconds with a resolution output.
    """
    pytest.skip("Implement after Policy + Resolution agents are merged (Week 4)")


@pytest.mark.asyncio
async def test_legal_threat_routes_to_escalation_agent(sample_escalation_message):
    """
    A message containing legal keywords must bypass Policy Agent
    and route directly to the Escalation Agent.
    """
    pytest.skip("Implement after Escalation Agent is merged (Week 4)")


@pytest.mark.asyncio
async def test_full_return_pipeline_end_to_end(sample_return_message):
    """
    Full pipeline: Triage → Policy (eligible) → Resolution (refund) → Communication.
    Assert: resolution contains a transaction_id and a label_url.
    """
    pytest.skip("Implement after all agents are merged (Week 4)")


@pytest.mark.asyncio
async def test_session_persists_across_handoffs(sample_return_message):
    """
    Session object must contain the full agent_chain after pipeline completes.
    Expected chain: ['TriageOrchestrator', 'PolicyAgent', 'ResolutionAgent', 'CommunicationAgent']
    """
    pytest.skip("Implement after Redis + all agents are merged (Week 4)")


@pytest.mark.asyncio
async def test_pii_stripped_before_agent_receives_message():
    """
    A message containing a credit card number must have it redacted
    before the Triage Orchestrator sees it.
    """
    pytest.skip("Implement after PII guardrail is merged (Week 5)")


@pytest.mark.asyncio
async def test_refund_cap_blocks_high_value_refund():
    """
    A refund request > $500 must set human_approval_required: true
    and NOT call process_refund.
    """
    pytest.skip("Implement after refund_cap guardrail is merged (Week 5)")
