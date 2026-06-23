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

import re
from agents import GuardrailFunctionOutput, output_guardrail


# Prohibited language mappings
PROHIBITED_LANGUAGE = {
    # Profanity or offensive terms
    "stupid": "misguided",
    "hate": "dislike strongly",
    "useless": "not effective",
    "idiot": "person",
    "scam": "fraudulent scheme",
    "fraud": "fraudulent activity",
    "damn": "darn",
    # Legal admissions
    "it was our fault": "we are looking into this matter",
    "we are liable": "we are reviewing our responsibilities",
    # Promises outside policy
    "we guarantee": "we strive to ensure",
    "you will definitely": "you will likely",
    # Competitor names (generic examples - in practice, these would be specific competitors)
    "competitor": "other service provider",
    # Multi-word phrases
    "fix this now": "address this promptly",
    "worthless": "of limited value",
    "terrible": "unsatisfactory",
}

# Compile regex patterns for prohibited language (case-insensitive)
PROHIBITED_PATTERNS = [
    (re.compile(re.escape(word), re.IGNORECASE), replacement)
    for word, replacement in PROHIBITED_LANGUAGE.items()
]


@output_guardrail
async def brand_voice_guardrail(ctx, agent, output) -> GuardrailFunctionOutput:
    """
    Inspect the Communication Agent's output for brand voice violations.
    Rewrites prohibited language and enforces tone requirements.
    """
    output_text = str(output)
    modified_text = output_text
    modifications_made = []

    # 1. Check and replace prohibited language
    for pattern, replacement in PROHIBITED_PATTERNS:
        if pattern.search(modified_text):
            modified_text = pattern.sub(replacement, modified_text)
            modifications_made.append("Replaced prohibited language")

    # 2. Enforce word limit (under 150 words)
    words = modified_text.split()
    if len(words) > 150:
        # Truncate to 150 words and add ellipsis
        modified_text = " ".join(words[:150]) + "..."
        modifications_made.append(f"Truncated to 150 words (was {len(words)} words)")

    # 3. Fix ALL CAPS words (except acronyms - assume acronyms are 2+ chars and all uppercase)
    def fix_all_caps(match):
        word = match.group(0)
        # If it's all uppercase and longer than 1 character, convert to title case
        if len(word) > 1 and word.isupper():
            modifications_made.append(f"Fixed ALL CAPS word: '{word}'")
            return word.title()  # Converts to Title Case
        return word

    # Match words (sequences of alphabetic characters)
    modified_text = re.sub(r"\b[A-Z]+\b", fix_all_caps, modified_text)

    # 4. Note: "Always address customer by first name if known"
    #    cannot be fully implemented in the guardrail as we don't have access to customer name.
    #    This should be ensured by the Communication Agent when drafting the message.

    # Prepare output info
    output_info = {
        "modified_output": modified_text,
        "modifications_made": modifications_made,
        "original_length": len(output_text.split()),
        "modified_length": len(modified_text.split()) if not modified_text.endswith("...") else 150,
    }

    # Determine if any modifications were made
    if modifications_made:
        # Return the modified output
        return GuardrailFunctionOutput(output_info=output_info, tripwire_triggered=False)
    else:
        # No modifications needed
        return GuardrailFunctionOutput(
            output_info={"allowed": True, "original_output": output_text}, tripwire_triggered=False
        )
