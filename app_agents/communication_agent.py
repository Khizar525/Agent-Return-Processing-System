"""
Communication Agent
Owner: Member 4

Drafts and sends customer-facing messages (email, SMS, chat) after a
resolution has been confirmed by the Resolution Agent.

Requirements:
    - Brand voice guardrail applied to every output (see guardrails/brand_voice.py)
    - Messages must be <= 150 words
    - Tone: professional, empathetic, concise
    - Must include: resolution summary, next steps, reference/ticket number

Dependencies:
    - tools/notification_tools.py  (send_notification)  — Member 4 (you)
    - guardrails/brand_voice.py                         — Member 4 (you)
"""

# from tools.notification_tools import send_notification
# from guardrails.brand_voice import brand_voice_guardrail

# TODO (Member 4): implement communication_agent below
# communication_agent = Agent(
#     name="CommunicationAgent",
#     instructions="...",
#     model="gemini-2.0-flash",
#     tools=[send_notification],
#     output_guardrails=[brand_voice_guardrail],
# )
