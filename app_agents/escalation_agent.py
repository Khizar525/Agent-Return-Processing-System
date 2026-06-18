"""
Escalation Agent
Owner: Member 4

Handles edge cases that cannot be resolved autonomously:
    - Sentiment Monitor score > 0.8 (customer distress)
    - High-value orders (> $500 refund cap)
    - Legal threats or explicit escalation demands
    - Repeat fraud flags on account

Responsibilities:
    1. Compile full context bundle (customer_id, order history,
       agent_chain, all tool results, timestamps)
    2. Open ticket in Zendesk via create_human_ticket
    3. Log resolution outcome via log_resolution

Model: gpt-4o (elevated reasoning approved for edge cases)

Dependencies:
    - tools/helpdesk_tools.py  (create_human_ticket, log_resolution) — Member 4 (you)
"""

from agents import Agent
from tools.helpdesk_tools import create_human_ticket, log_resolution


class EscalationAgent:
    """
    Escalation Agent that handles edge cases requiring human intervention.
    """

    def __init__(self):
        # Escalation thresholds
        self.sentiment_threshold = 0.8
        self.high_value_threshold = 500.0

    def should_escalate(self, context: dict) -> bool:
        """
        Determine if a case should be escalated based on context.

        Args:
            context: Dictionary containing customer context including:
                - sentiment_score: float (0.0 to 1.0)
                - order_value: float (in USD)
                - legal_threats: bool
                - repeat_fraud: bool

        Returns:
            bool: True if case should be escalated
        """
        return (
            context.get("sentiment_score", 0) > self.sentiment_threshold or
            context.get("order_value", 0) > self.high_value_threshold or
            context.get("legal_threats", False) or
            context.get("repeat_fraud", False)
        )

    def compile_context_bundle(self, base_context: dict) -> dict:
        """
        Compile a full context bundle for escalation.

        Args:
            base_context: Basic context dictionary

        Returns:
            dict: Full context bundle suitable for create_human_ticket
        """
        # Start with base context
        context_bundle = base_context.copy()

        # Ensure all required fields are present with defaults
        context_bundle.setdefault("customer_id", "unknown")
        context_bundle.setdefault("session_id", "unknown")
        context_bundle.setdefault("agent_chain", [])
        context_bundle.setdefault("intent", "escalation")
        context_bundle.setdefault("policy_decision", None)
        context_bundle.setdefault("resolution_action", None)
        context_bundle.setdefault("escalation_reason", "unknown")
        context_bundle.setdefault("order_history", [])
        context_bundle.setdefault("timestamps", {})
        context_bundle.setdefault("raw_conversation", [])

        # Determine escalation reason if not already set
        if context_bundle.get("escalation_reason") == "unknown":
            if context_bundle.get("sentiment_score", 0) > self.sentiment_threshold:
                context_bundle["escalation_reason"] = "high_sentiment"
            elif context_bundle.get("order_value", 0) > self.high_value_threshold:
                context_bundle["escalation_reason"] = "high_value_order"
            elif context_bundle.get("legal_threats", False):
                context_bundle["escalation_reason"] = "legal_threats"
            elif context_bundle.get("repeat_fraud", False):
                context_bundle["escalation_reason"] = "repeat_fraud"
            else:
                context_bundle["escalation_reason"] = "other"

        return context_bundle


# Initialize the escalation agent
escalation_agent_instance = EscalationAgent()

# Legacy Agent wrapper for backward compatibility with existing Agent framework
# This maintains the interface expected by the rest of the system
escalation_agent = Agent(
    name="EscalationAgent",
    instructions=(
        "You handle escalated customer issues that cannot be resolved autonomously.\n\n"
        "Reasons for escalation:\n"
        "- Legal threats or extreme distress\n"
        "- High-value orders exceeding the refund cap\n"
        "- Repeat fraud signals on account\n"
        "- Sentiment Monitor score > 0.8\n\n"
        "Your job:\n"
        "1. Compile a full context bundle with all available data.\n"
        "2. Create a human ticket (once create_human_ticket is available).\n"
        "3. Log the resolution outcome.\n\n"
        "Be thorough — include every detail the human agent will need."
    ),
    model="gpt-4o",
    tools=[create_human_ticket, log_resolution],
)