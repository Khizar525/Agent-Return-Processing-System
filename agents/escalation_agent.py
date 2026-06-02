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
# from tools.helpdesk_tools import create_human_ticket, log_resolution

# TODO (Member 4): implement escalation_agent below with proper tools
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
    # tools=[create_human_ticket, log_resolution],  # uncomment after M4 merges
)
