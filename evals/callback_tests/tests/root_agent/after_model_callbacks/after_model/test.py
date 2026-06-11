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
Callback Tests — after_model_callback (Root Agent)

Tests the deterministic farewell-injection callback. The callback injects
FAREWELL_TEXT before an end_session function call when the LLM ends the
session without producing any text — but only if the agent did not already
speak earlier in the same conversational turn (the multi-model-call problem).

BRANCHES COVERED (mirrors the three numbered STEPs in python_code.py):
    STEP 1 no-op: response has no end_session call               -> TestNoEndSession
    STEP 1 no-op: response has end_session AND text this call    -> TestEndSessionWithText
    STEP 2 no-op: end_session + silent now, but agent spoke
                  earlier in the same turn                       -> TestPriorAgentTextInTurn
    STEP 3 inject: end_session + silent now + no prior text      -> TestFarewellInjection
    Edge cases (whitespace text, audio transcript, ordering,
                empty events, user-boundary break)               -> TestEdgeCases

RUNNING:
    pytest evals/callback_tests/tests/ -v

    Or via SCRAPI:
    from cxas_scrapi.evals.callback_evals import CallbackEvals
    cb = CallbackEvals()
    results = cb.test_all_callbacks_in_app_dir(app_dir="evals/callback_tests")
"""

import sys
import os
from unittest.mock import MagicMock

# -------------------------------------------------------------------------
# MOCK INJECTION: Add the python_code.py directory to sys.path and import the
# REAL module, then attach any GECX-provided globals as mocks BEFORE importing
# the function under test. This callback only uses standard-library imports
# plus the auto-provided CallbackContext/Content/Part/LlmResponse globals
# (which the test supplies from cxas_scrapi), so there is no `tools` global to
# stub — but we keep the path/insert pattern so the import resolves to the
# callback's own python_code.py copy.
# -------------------------------------------------------------------------
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "agents", "root_agent",
    "after_model_callbacks", "after_model",
))

from cxas_scrapi.utils.callback_libs import (  # noqa: E402
    CallbackContext,
    Content,
    Part,
    LlmResponse,
    Event,
)

import python_code  # noqa: E402

# The callback references Part / Content / LlmResponse as bare names at runtime
# (the GECX sandbox auto-provides them as module globals — see the
# "PLATFORM GLOBALS (do NOT import these)" note in python_code.py). In the test
# environment they don't exist, so STEP 3 (Part.from_text / LlmResponse.from_parts)
# raises NameError. Inject the real SCRAPI datamodels into the module's globals
# BEFORE importing the function so the callback executes against real types.
python_code.Part = Part
python_code.Content = Content
python_code.LlmResponse = LlmResponse
python_code.CallbackContext = CallbackContext

from python_code import after_model_callback, FAREWELL_TEXT  # noqa: E402


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _end_session_part():
    """A Part carrying the end_session function call (no text)."""
    return Part.from_function_call("end_session", {"session_escalated": False})


def _text_part(text):
    return Part.from_text(text=text)


class _TranscriptPart:
    """A duck-typed Part whose content is an audio transcript, not part.text.

    Mirrors audio mode where the LLM emits a transcript rather than plain text.
    The callback only calls .has_function_call() and .text_or_transcript() on
    parts, so a lightweight stand-in suffices — and avoids the real Blob's
    missing transcript() method in this callback_libs version.
    """

    def __init__(self, transcript):
        self.text = None
        self._transcript = transcript

    def has_function_call(self, name):
        return False

    def text_or_transcript(self):
        return self._transcript


def _transcript_part(text):
    return _TranscriptPart(text)


class _PartsContent:
    """A duck-typed Content holder used for the incoming llm_response so we can
    mix real Parts with duck-typed transcript parts (pydantic Content would
    reject the stand-in). The callback only reads .parts on llm_response.content.
    """

    def __init__(self, parts, role="model"):
        self.parts = parts
        self.role = role


def _response(parts):
    return LlmResponse.model_construct(content=_PartsContent(parts))


_EVT_SEQ = [0]


def _event(author, parts):
    """Build a minimal Event with the required identity fields populated.

    Uses model_construct + a duck-typed content holder so events can carry
    duck-typed transcript parts (real Content would reject the stand-in). The
    callback reaches parts via Event.parts() -> self.content.parts.
    """
    _EVT_SEQ[0] += 1
    role = "user" if author == "user" else "model"
    return Event.model_construct(
        id=f"evt-{_EVT_SEQ[0]}",
        author=author,
        timestamp=_EVT_SEQ[0],
        invocation_id="inv-1",
        content=_PartsContent(parts, role=role),
    )


def _agent_event(text):
    return _event("root_agent", [_text_part(text)])


def _agent_silent_event():
    """An agent event with only a function call, no spoken text."""
    return _event("root_agent", [_end_session_part()])


def _user_event(text="I want to cancel my alarm"):
    return _event("user", [_text_part(text)])


def _ctx(events=None, state=None):
    return CallbackContext(state=(state or {}), events=(events or []))


# -------------------------------------------------------------------------
# STEP 1 — no end_session in this model call => no-op
# -------------------------------------------------------------------------
class TestNoEndSession:
    """Callback must not touch responses that don't end the session."""

    def test_text_only_response_returns_none(self):
        resp = _response([_text_part("Could you provide the passcode?")])
        assert after_model_callback(_ctx(), resp) is None

    def test_other_function_call_returns_none(self):
        """A non-end_session function call (e.g. cancel_alarm) is left alone."""
        resp = _response([Part.from_function_call("cancel_alarm", {"account_id": "1"})])
        assert after_model_callback(_ctx(), resp) is None

    def test_empty_text_no_end_session_returns_none(self):
        resp = _response([_text_part("")])
        assert after_model_callback(_ctx(), resp) is None


# -------------------------------------------------------------------------
# STEP 1 — end_session AND text in the SAME model call => no-op
# -------------------------------------------------------------------------
class TestEndSessionWithText:
    """If the model already spoke in this very call, don't add a farewell."""

    def test_text_before_end_session_returns_none(self):
        resp = _response([
            _text_part("You're all set. Have a good day."),
            _end_session_part(),
        ])
        assert after_model_callback(_ctx(), resp) is None

    def test_text_after_end_session_returns_none(self):
        """Order within the call doesn't matter — any text counts as 'spoke'."""
        resp = _response([
            _end_session_part(),
            _text_part("Goodbye!"),
        ])
        assert after_model_callback(_ctx(), resp) is None

    def test_transcript_text_in_same_call_returns_none(self):
        """Audio mode: text arrives as a transcript, still counts as spoken."""
        resp = _response([
            _transcript_part("Take care now."),
            _end_session_part(),
        ])
        assert after_model_callback(_ctx(), resp) is None


# -------------------------------------------------------------------------
# STEP 2 — silent end_session now, but agent spoke earlier this turn => no-op
# -------------------------------------------------------------------------
class TestPriorAgentTextInTurn:
    """The multi-model-call problem: don't double-text within one turn."""

    def test_prior_agent_text_returns_none(self):
        events = [
            _user_event("Thanks, that's all"),
            _agent_event("You're all set. Have a great day!"),
            _agent_silent_event(),
        ]
        resp = _response([_end_session_part()])
        assert after_model_callback(_ctx(events), resp) is None

    def test_prior_agent_transcript_returns_none(self):
        """Earlier agent speech delivered as an audio transcript also blocks injection."""
        events = [
            _user_event("Goodbye"),
            _event("root_agent", [_transcript_part("Thanks for calling.")]),
            _agent_silent_event(),
        ]
        resp = _response([_end_session_part()])
        assert after_model_callback(_ctx(events), resp) is None

    def test_stops_at_user_boundary(self):
        """Agent text from a PRIOR turn (before the last user msg) is ignored.

        Walking backwards, the loop must break at the most recent user event,
        so the older agent greeting must NOT suppress this turn's farewell.
        """
        events = [
            _agent_event("Rapid Response Monitoring. How can I help you today?"),
            _user_event("Cancel my alarm please"),
            _agent_silent_event(),
        ]
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(events), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]


# -------------------------------------------------------------------------
# STEP 3 — silent end_session, no prior agent text => inject farewell
# -------------------------------------------------------------------------
class TestFarewellInjection:
    """The core behavior: prepend the farewell before a silent end_session."""

    def test_injects_when_no_prior_text(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(), resp)
        assert result is not None

    def test_farewell_is_first_part(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(), resp)
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_end_session_preserved_after_farewell(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(), resp)
        # Farewell first, original end_session call retained after it.
        assert len(result.content.parts) == 2
        assert result.content.parts[1].has_function_call("end_session")

    def test_response_role_is_model(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(), resp)
        assert result.content.role == "model"

    def test_inject_when_only_prior_user_event(self):
        """Last user message exists but agent never spoke -> inject."""
        events = [_user_event("That's everything, bye"), _agent_silent_event()]
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(events), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]


# -------------------------------------------------------------------------
# Farewell language — keyed on the _language session var (set_language writes
# it on an explicit switch); defaults to English.
# -------------------------------------------------------------------------
class TestFarewellLanguage:
    """The injected farewell must match the active conversation language."""

    def test_default_state_uses_english(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(state={}), resp)
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_english_state_uses_english(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(state={"_language": "English"}), resp)
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_spanish_state_uses_spanish(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(state={"_language": "Spanish"}), resp)
        assert result.content.parts[0].text == FAREWELL_TEXT["Spanish"]

    def test_unknown_language_falls_back_to_english(self):
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(state={"_language": "Klingon"}), resp)
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]


# -------------------------------------------------------------------------
# Edge cases
# -------------------------------------------------------------------------
class TestEdgeCases:
    """Whitespace handling, empty events, and prior silent agent events."""

    def test_whitespace_only_text_counts_as_silent(self):
        """Whitespace-only text fails len(strip())>0, so farewell is injected."""
        resp = _response([_text_part("   \n  "), _end_session_part()])
        result = after_model_callback(_ctx(), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_empty_events_injects(self):
        """No event history at all -> still inject (no prior agent text)."""
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx([]), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_prior_silent_agent_events_do_not_block(self):
        """Earlier agent events with only function calls (no text) don't suppress."""
        events = [
            _user_event("Cancel the alarm"),
            _event("root_agent", [Part.from_function_call("cancel_alarm", {"id": "1"})]),
            _agent_silent_event(),
        ]
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(events), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]

    def test_prior_agent_whitespace_text_does_not_block(self):
        """An earlier agent event whose only text is whitespace doesn't count as speaking."""
        events = [
            _user_event("Bye"),
            _agent_event("   "),
            _agent_silent_event(),
        ]
        resp = _response([_end_session_part()])
        result = after_model_callback(_ctx(events), resp)
        assert result is not None
        assert result.content.parts[0].text == FAREWELL_TEXT["English"]
