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
Callback Tests — before_model_callback (Root Agent)

Tests the DETERMINISTIC ACTION-TOOL EMISSION callback. In audio/Live mode
gemini-3.1-flash-live intermittently DROPS the state-changing action call
(cancel_alarm / put_account_on_test) and speaks a fabricated confirmation. The
callback closes that gap: when state shows a verified action is pending, it
RETURNS the function call itself, short-circuiting the model for that turn — the
model literally cannot drop a call it never had to make.

These tests pin the SAFETY GATES that the (stochastic) goldens cannot
deterministically exercise — the branches that decide whether to fire at all:

    No-op when no pending action / unknown intent      -> TestNoPendingAction
    No-op unless passcode_verified (gate never bypassed)-> TestPasscodeGate
    Cancel: fires only on verified + active + not-fired -> TestCancelEmission
    Test:   fires only with an in-range stashed duration -> TestPutOnTestEmission
    Intent (NOT has_active_alarm) drives cancel-vs-test  -> TestIntentDiscrimination

The cancel-vs-test discrimination is the load-bearing safety property: the
Fort Worth / Plano on-test branches ALSO carry an active alarm, so
has_active_alarm alone would wrongly cancel an on-test caller's alarm. The
callback keys on the _pending_action intent (written by verify_passcode on a
SUCCESSFUL verification) instead.

RUNNING (one file per pytest invocation — `python_code` module-name collision):
    python -m pytest evals/callback_tests/tests/root_agent/before_model_callbacks/before_model/test.py -q
"""

import sys
import os
import json
from unittest.mock import MagicMock

# -------------------------------------------------------------------------
# MOCK INJECTION: resolve `import python_code` to this callback's synced copy,
# then attach the GECX-provided globals the callback references at runtime
# (Part / LlmResponse) plus the type-annotation names (CallbackContext /
# LlmRequest) before importing the function. Mirrors the after_model test.
# -------------------------------------------------------------------------
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "agents", "root_agent",
    "before_model_callbacks", "before_model",
))

from cxas_scrapi.utils.callback_libs import (  # noqa: E402
    CallbackContext,
    Content,
    Part,
    LlmResponse,
    LlmRequest,
)

import python_code  # noqa: E402

# The callback references Part / LlmResponse as bare names at runtime (the GECX
# sandbox auto-provides them — see the "PLATFORM GLOBALS" note in python_code.py).
# Inject the real SCRAPI datamodels so the callback executes against real types.
python_code.Part = Part
python_code.Content = Content
python_code.LlmResponse = LlmResponse
python_code.CallbackContext = CallbackContext
python_code.LlmRequest = LlmRequest

from python_code import before_model_callback  # noqa: E402


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _account(passcode_verified=True, has_active_alarm=True, **extra):
    """JSON-encoded _resolved_account (the tool writes this as a string)."""
    acct = {"passcode_verified": passcode_verified, "has_active_alarm": has_active_alarm}
    acct.update(extra)
    return json.dumps(acct)


def _ctx(state):
    return CallbackContext(state=state, events=[])


def _req():
    """The callback never reads llm_request (only callback_context.state)."""
    return MagicMock()


def _fc(result):
    """Extract the single returned function_call (name, args)."""
    assert result is not None, "expected the callback to emit a function call"
    parts = result.content.parts
    assert len(parts) == 1, f"expected exactly one part, got {len(parts)}"
    return parts[0].function_call


# -------------------------------------------------------------------------
# No pending action / unknown intent => no-op
# -------------------------------------------------------------------------
class TestNoPendingAction:
    """The callback must stay inert unless a recognized action is pending."""

    def test_no_pending_returns_none(self):
        assert before_model_callback(_ctx({}), _req()) is None

    def test_empty_pending_returns_none(self):
        state = {"_pending_action": "", "_resolved_account": _account()}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_unknown_pending_returns_none(self):
        state = {"_pending_action": "transfer", "_resolved_account": _account()}
        assert before_model_callback(_ctx(state), _req()) is None


# -------------------------------------------------------------------------
# Passcode gate — never fire before verify_passcode succeeds
# -------------------------------------------------------------------------
class TestPasscodeGate:
    """The gate is load-bearing: no forced action without a verified passcode,
    even when everything else looks ready."""

    def test_cancel_without_verified_passcode_returns_none(self):
        state = {
            "_pending_action": "cancel",
            "_resolved_account": _account(passcode_verified=False, has_active_alarm=True),
        }
        assert before_model_callback(_ctx(state), _req()) is None

    def test_test_without_verified_passcode_returns_none(self):
        state = {
            "_pending_action": "test",
            "_resolved_account": _account(passcode_verified=False),
            "_test_duration_minutes": "60",
        }
        assert before_model_callback(_ctx(state), _req()) is None

    def test_missing_resolved_account_returns_none(self):
        # No _resolved_account at all -> account {} -> passcode_verified falsey.
        state = {"_pending_action": "cancel"}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_malformed_resolved_account_returns_none(self):
        # Corrupt JSON -> defensive empty account -> gate blocks.
        state = {"_pending_action": "cancel", "_resolved_account": "{not valid json"}
        assert before_model_callback(_ctx(state), _req()) is None


# -------------------------------------------------------------------------
# Cancel emission
# -------------------------------------------------------------------------
class TestCancelEmission:
    """cancel_alarm is forced only when verified, an alarm is active, and it has
    not already been forced this turn."""

    def test_fires_when_verified_and_active(self):
        state = {"_pending_action": "cancel", "_resolved_account": _account()}
        fc = _fc(before_model_callback(_ctx(state), _req()))
        assert fc.name == "cancel_alarm"
        assert (fc.args or {}) == {}  # argument-free (reads _resolved_account)

    def test_clears_pending_and_sets_forced_flag(self):
        # CallbackContext(state=...) COPIES the dict, so assert on ctx.state
        # (the dict the callback actually mutated), not the input dict.
        ctx = _ctx({"_pending_action": "cancel", "_resolved_account": _account()})
        before_model_callback(ctx, _req())
        assert ctx.state["_pending_action"] == ""
        assert str(ctx.state["_cancel_forced"]).lower() == "true"

    def test_noop_when_no_active_alarm(self):
        # Nothing to cancel -> let the model handle it (it tells the caller).
        state = {"_pending_action": "cancel",
                 "_resolved_account": _account(has_active_alarm=False)}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_noop_when_already_forced(self):
        # Re-fire guard: don't emit cancel_alarm twice in one flow.
        state = {"_pending_action": "cancel", "_resolved_account": _account(),
                 "_cancel_forced": "true"}
        assert before_model_callback(_ctx(state), _req()) is None


# -------------------------------------------------------------------------
# put_account_on_test emission
# -------------------------------------------------------------------------
class TestPutOnTestEmission:
    """put_account_on_test is forced only when an in-range duration was stashed
    in state by verify_passcode; the args are reconstructed from that state."""

    def test_fires_with_stashed_duration(self):
        state = {
            "_pending_action": "test",
            "_resolved_account": _account(),
            "_test_duration_minutes": "60",
            "_test_duration_label": "1 hour",
        }
        fc = _fc(before_model_callback(_ctx(state), _req()))
        assert fc.name == "put_account_on_test"
        assert fc.args["duration_minutes"] == 60
        assert fc.args["duration_label"] == "1 hour"

    def test_clears_pending_and_sets_forced_flag(self):
        ctx = _ctx({"_pending_action": "test", "_resolved_account": _account(),
                    "_test_duration_minutes": "120", "_test_duration_label": "2 hours"})
        before_model_callback(ctx, _req())
        assert ctx.state["_pending_action"] == ""
        assert str(ctx.state["_test_forced"]).lower() == "true"

    def test_noop_without_duration(self):
        # Duration not stated by verify time -> not stashed -> safe fallback.
        state = {"_pending_action": "test", "_resolved_account": _account()}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_noop_with_invalid_duration(self):
        state = {"_pending_action": "test", "_resolved_account": _account(),
                 "_test_duration_minutes": "soon"}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_noop_when_already_forced(self):
        state = {"_pending_action": "test", "_resolved_account": _account(),
                 "_test_duration_minutes": "60", "_test_forced": "true"}
        assert before_model_callback(_ctx(state), _req()) is None

    def test_label_fallback_when_missing(self):
        # No label stashed -> synthesize "<minutes> minutes".
        state = {"_pending_action": "test", "_resolved_account": _account(),
                 "_test_duration_minutes": "45"}
        fc = _fc(before_model_callback(_ctx(state), _req()))
        assert fc.args["duration_minutes"] == 45
        assert fc.args["duration_label"] == "45 minutes"


# -------------------------------------------------------------------------
# Intent discrimination — the load-bearing safety property
# -------------------------------------------------------------------------
class TestIntentDiscrimination:
    """_pending_action (intent), NOT has_active_alarm, decides cancel vs test.

    The Fort Worth / Plano on-test branches carry an ACTIVE alarm too, so a
    has_active_alarm-based trigger would wrongly cancel an on-test caller's
    alarm. These two cases pin that the intent flag governs the choice."""

    def test_test_intent_on_active_alarm_emits_test_not_cancel(self):
        # On-test branch that ALSO has an active alarm + a test intent pending.
        state = {
            "_pending_action": "test",
            "_resolved_account": _account(has_active_alarm=True),
            "_test_duration_minutes": "120",
            "_test_duration_label": "2 hours",
        }
        fc = _fc(before_model_callback(_ctx(state), _req()))
        assert fc.name == "put_account_on_test"
        assert fc.name != "cancel_alarm"

    def test_cancel_intent_emits_cancel(self):
        state = {"_pending_action": "cancel",
                 "_resolved_account": _account(has_active_alarm=True)}
        fc = _fc(before_model_callback(_ctx(state), _req()))
        assert fc.name == "cancel_alarm"
        assert fc.name != "put_account_on_test"
