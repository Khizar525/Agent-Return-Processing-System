"""
Brand Voice — Output Guardrail
Owner: Member 4

Rejects or rewrites any Communication Agent output that contains
prohibited language or violates the brand tone guidelines.

Prohibited language (block immediately, do not send):
    - Profanity or offensive terms
    - Legal admissions ("it was our fault", "we are liable")
    - Promises outside policy ("we guarantee", "you will definitely")
    - Competitor names

Tone requirements:
    - Professional and empathetic
    - Under 150 words
    - No ALL CAPS except acronyms
    - Always address customer by first name if known

Must be applied as an output_guardrail on the Communication Agent.

Usage (once implemented):
    from guardrails.brand_voice import brand_voice_guardrail
    communication_agent = Agent(..., output_guardrails=[brand_voice_guardrail])
"""

# TODO (Member 4): implement brand_voice_guardrail below
# from app_agents.guardrails import output_guardrail, GuardrailFunctionOutput
#
# @output_guardrail
# async def brand_voice_guardrail(ctx, agent, output) -> GuardrailFunctionOutput:
#     ...
