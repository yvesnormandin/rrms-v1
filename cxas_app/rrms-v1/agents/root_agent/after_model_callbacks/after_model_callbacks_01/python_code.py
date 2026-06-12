# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
after_model_callback — Root Agent

PURPOSE:
    Two complementary guarantees around the close:
    - CASE A (farewell injection): when the LLM calls end_session WITHOUT saying
      anything first, inject farewell text so the caller hears a goodbye.
    - CASE B (dropped-end_session rescue, audio): when the LLM SPEAKS its sign-off
      but DROPS the end_session call (the audio tool-drop, now the dominant
      residual once cancel_alarm/put_account_on_test are forced via before_model),
      append the missing end_session so the call actually terminates. The trigger
      is the model's OWN farewell, so we never decide to hang up — we only complete
      the mechanical call it dropped.

WHY THIS EXISTS:
    The LLM frequently calls end_session without producing any text, causing
    the customer to hear silence before the call disconnects. This callback
    ensures the customer always hears a goodbye message.

THE MULTI-MODEL-CALL PROBLEM:
    A single conversational "turn" can span MULTIPLE model calls. For example:
      - Model call 1: LLM produces text ("Thank you for calling!")
      - Model call 2: LLM calls payload_update_tool
      - Model call 3: LLM calls end_session (no text)

    The after_model_callback fires on EACH model call separately. A naive check
    for "no text in this response" would inject text on call 3 even though the
    agent already said something in call 1 — causing DOUBLE text.

FIX:
    Use callback_context.events to check if the agent already produced text in
    a prior model call within the same turn. Only inject if no text was produced
    anywhere in the current turn.

KEY PATTERNS DEMONSTRATED:
    1. text_or_transcript(): Use instead of part.text for audio-safe detection.
       In audio mode, the LLM produces transcripts, not text. text_or_transcript()
       handles both.
    2. callback_context.events: Full session event history. Walk backwards from
       the most recent event to find the last user message; if any agent event
       between now and then has text, the agent already spoke.
    3. Prepend text before end_session: Put the farewell Part BEFORE the
       end_session Part so the customer hears it first.

PLATFORM GLOBALS (do NOT import these):
    CallbackContext, Content, Part, LlmResponse, LlmRequest are auto-provided
    by the GECX sandbox at runtime. Only standard library imports need explicit
    import statements.
"""

from typing import Optional

# The farewell message to inject when the LLM ends the session silently.
# Keyed by active conversation language (_language session var, written by
# set_language when the caller explicitly switches). Defaults to English — the
# conversation always starts in English. Keep these generic; the LLM should
# normally have already said something contextual in the active language.
FAREWELL_TEXT = {
    "English": "Thank you for calling Rapid Response Monitoring. Have a great day!",
    "Spanish": "Gracias por llamar a Rapid Response Monitoring. ¡Que tenga un buen día!",
}

# --- Dropped-end_session rescue (audio) -----------------------------------
# In audio/Live the model intermittently SPEAKS its sign-off but DROPS the
# end_session function call, so the call never formally terminates. We detect
# the model's OWN farewell and append the missing end_session. Using the model's
# spoken farewell as the trigger means we never decide to hang up — the model
# already did; we only complete the mechanical call it dropped (no premature-
# hangup risk). Markers are matched as lowercased substrings on the spoken text.
_CLOSING_MARKERS = (
    "have a good day", "have a great day", "have a wonderful day",
    "have a nice day", "have a good one", "take care", "goodbye", "good bye",
    "good night",
    # Spanish sign-offs
    "buen día", "buen dia", "buena tarde", "buenas tardes", "buena noche",
    "cuídese", "cuidese", "que tenga un", "que tenga una",
)
# If the same utterance still OFFERS further help, it is NOT a close — the
# conversation is continuing — so we must not force end_session.
_FURTHER_HELP_MARKERS = (
    "anything else", "something else", "is there anything", "anything more",
    "how else", "can i help", "may i help",
    "algo más", "algo mas", "en qué más", "en que mas", "puedo ayudar",
)


def _looks_like_close(text: str) -> bool:
    """True when the spoken text is a terminal sign-off (and not still offering help)."""
    low = text.lower()
    if any(h in low for h in _FURTHER_HELP_MARKERS):
        return False
    return any(m in low for m in _CLOSING_MARKERS)


def after_model_callback(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:

    # -------------------------------------------------------------------------
    # STEP 1: Check if THIS model call contains end_session AND text.
    # -------------------------------------------------------------------------
    has_end_session = False
    has_text_this_call = False
    this_call_text = []

    for part in llm_response.content.parts:
        if part.has_function_call("end_session"):
            has_end_session = True
        else:
            # text_or_transcript() handles both text and audio transcripts.
            # WHY not part.text? In audio mode, the LLM produces transcripts
            # (part.inline_data with transcript metadata), not part.text.
            # text_or_transcript() returns whichever is available.
            content = part.text_or_transcript()
            if content and len(content.strip()) > 0:
                has_text_this_call = True
                this_call_text.append(content)

    # -------------------------------------------------------------------------
    # CASE B — DROPPED end_session RESCUE (audio):
    # The model spoke a terminal sign-off but did NOT call end_session in this
    # call. Append the missing end_session so the session actually ends. We add
    # ONLY the function_call (not the farewell text — the model already said it),
    # which in audio's append-only semantics avoids a doubled goodbye. This only
    # triggers when the model itself signaled the close, so there is no risk of
    # hanging up on a caller who still needs help. In text mode end_session is
    # not dropped, so this branch effectively never fires there.
    # -------------------------------------------------------------------------
    if not has_end_session and _looks_like_close(" ".join(this_call_text)):
        return LlmResponse.from_parts(parts=[
            Part.from_function_call(name="end_session", args={}),
        ])

    # If there's no end_session, or the LLM already said something, no-op.
    if not has_end_session or has_text_this_call:
        return None

    # -------------------------------------------------------------------------
    # STEP 2: Check if the agent produced text in an EARLIER model call
    # within this same turn.
    #
    # WHY: The multi-model-call problem. Walk backwards through events until
    # we hit the last user message. If any agent event in between has text,
    # the agent already spoke — don't double-text.
    # -------------------------------------------------------------------------
    for event in reversed(callback_context.events):
        if event.is_user():
            # Reached the last user message — no prior agent text found
            break
        if event.is_agent():
            for p in event.parts():
                content = p.text_or_transcript()
                if content and len(content.strip()) > 0:
                    # Agent already said something in an earlier model call
                    return None

    # -------------------------------------------------------------------------
    # STEP 3: No text anywhere in this turn — inject farewell BEFORE end_session.
    #
    # WHY prepend? The customer needs to hear the farewell before the session
    # terminates. Parts are processed in order.
    #
    # Pick the farewell in the active conversation language (set_language writes
    # _language on an explicit switch); default to English.
    # -------------------------------------------------------------------------
    language = callback_context.state.get("_language") or "English"
    farewell = FAREWELL_TEXT.get(language, FAREWELL_TEXT["English"])
    new_parts = [Part.from_text(text=farewell)]
    new_parts.extend(llm_response.content.parts)
    return LlmResponse.from_parts(parts=new_parts)
