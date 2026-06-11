"""
set_language -- Record the caller's explicitly requested conversation language.

WHEN TO CALL (instruction-enforced):
    Call this ONLY when the caller clearly and specifically asks to switch the
    conversation language (e.g., "Can we continue in Spanish?" / "¿Podemos
    hablar en español?"). The request may be phrased in either language. NEVER
    call it merely because the caller happened to speak or use a word in another
    language — the conversation language changes only on an explicit request.

EFFECT:
    Writes the normalized active language to the _language session variable.
    The after_model callback reads it to pick the farewell language; the agent
    itself conducts the rest of the conversation in the active language by
    following its instructions.

SUPPORTED:
    English and Spanish only. Any other request returns an error with an
    agent_action recovery hint (the agent declines and stays in scope).
"""

_ALIASES = {
    "english": "English",
    "inglés": "English",
    "ingles": "English",
    "en": "English",
    "spanish": "Spanish",
    "español": "Spanish",
    "espanol": "Spanish",
    "es": "Spanish",
}


def set_language(language: str = "") -> dict:
    """Record the conversation language the caller explicitly asked for.

    Args:
        language: The target language the caller requested ("English" or
            "Spanish"; common spellings in either language are accepted).

    Returns:
        dict: status and the normalized active language, or an error with an
            agent_action recovery hint when the language is unsupported.
    """
    lang = _ALIASES.get(language.strip().lower())

    if not lang:
        return {
            "status": "error",
            "language": "",
            "agent_action": "Only English and Spanish are supported. Politely tell the caller you can continue in English or Spanish, and ask which they prefer.",
        }

    context.state["_language"] = lang
    return {"status": "success", "language": lang}
