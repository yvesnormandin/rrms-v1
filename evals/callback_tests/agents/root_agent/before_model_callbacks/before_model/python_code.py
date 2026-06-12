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
before_model_callback — Root Agent (deterministic action tools)

PURPOSE:
    Guarantee that the state-changing action tool actually runs once a request
    is verified. In audio/Live mode, gemini-3.1-flash-live intermittently DROPS
    the action function call (cancel_alarm / put_account_on_test) and instead
    speaks a fabricated confirmation ("your alarm has been canceled", "the
    branch is now on test") without ever calling the tool. Every prompt-side fix
    tried failed against this model-level behavior (experiment_log Iteration 25 —
    the pre-call "bridge" made it worse).

WHY A CALLBACK (deterministic emission), NOT tool_config=ANY:
    The clean decoder-level fix would be to set the model's function-calling
    mode to ANY for the action turn. The CXAS callback sandbox does NOT expose
    the LlmRequest config/tool_config (only llm_request.contents is available),
    so that lever is unreachable. Instead we use the supported — and stronger —
    pattern: when state shows a verified action is pending, this callback RETURNS
    the action function call itself, short-circuiting the model for that one
    turn. The model literally cannot drop a call it never had to make. The next
    model turn sees the tool's response in history and speaks the confirmation
    grounded in the real result. (Confirmed 2026-06-12: a before_model-returned
    function_call DOES execute in Live/audio — cancel_alarm drop went to zero.)

WHY THE GATE IS SAFE:
    We fire ONLY when a verified action is pending, keyed on _pending_action,
    which verify_passcode sets ONLY on a SUCCESSFUL verification and ONLY from
    the intent the model passed. So:
      - We never fire before the passcode gate (passcode_verified must be True;
        the action tools also re-check this defensively).
      - The intent flag (not has_active_alarm) is what discriminates cancel vs
        test: has_active_alarm alone is NOT a safe proxy — the Fort Worth / Plano
        on-test branches also carry active alarms, so a naive trigger would
        wrongly cancel an on-test caller's alarm.
      - A per-action "_forced" flag + clearing _pending_action prevent re-fire.
    If verify_passcode never recorded a usable intent (e.g., the model omitted
    the arg, or a "test" with no in-range duration), the relevant precondition is
    unmet and this callback no-ops → the agent falls back to today's behavior.
    The failure mode is "no speed-up," never a wrong action.

    cancel_alarm is argument-free (reads _resolved_account). put_account_on_test
    needs a duration, so verify_passcode also stashes the validated duration in
    state (_test_duration_minutes / _test_duration_label) for the callback to
    reconstruct the call; we force it only when that duration is present.

PLATFORM GLOBALS (do NOT import these):
    CallbackContext, Content, Part, LlmResponse, LlmRequest are auto-provided
    by the GECX sandbox at runtime. Only standard library imports are needed.
"""

import json
from typing import Optional


def before_model_callback(callback_context: CallbackContext, llm_request: LlmRequest) -> Optional[LlmResponse]:
    state = callback_context.state

    pending = state.get("_pending_action")
    if pending not in ("cancel", "test"):
        return None

    # Read the verified account. The gate below is defense-in-depth on top of
    # each action tool's own passcode check.
    raw = state.get("_resolved_account", "")
    try:
        account = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        account = {}

    if not bool(account.get("passcode_verified")):
        # Passcode not yet verified — never fire before the gate.
        return None

    # ---- Cancel an alarm (UC1) -------------------------------------------
    if pending == "cancel":
        if str(state.get("_cancel_forced", "false")).lower() == "true":
            return None
        if not bool(account.get("has_active_alarm")):
            # Nothing to cancel — let the model handle this turn (it will tell
            # the caller there's no active alarm). cancel_alarm flipping
            # has_active_alarm False also makes this branch idempotent.
            return None
        # cancel_alarm is argument-free (reads _resolved_account from state).
        state["_pending_action"] = ""
        state["_cancel_forced"] = "true"
        return LlmResponse.from_parts(parts=[
            Part.from_function_call(name="cancel_alarm", args={}),
        ])

    # ---- Place a branch on test (UC2) ------------------------------------
    if pending == "test":
        if str(state.get("_test_forced", "false")).lower() == "true":
            return None
        # Only force when verify_passcode stashed an in-range duration. If it's
        # missing (caller hadn't stated a duration by verification time), no-op
        # and let the agent capture the duration / call the tool itself.
        raw_minutes = state.get("_test_duration_minutes", "")
        try:
            duration_minutes = int(raw_minutes)
        except (ValueError, TypeError):
            return None
        duration_label = state.get("_test_duration_label", "") or f"{duration_minutes} minutes"
        state["_pending_action"] = ""
        state["_test_forced"] = "true"
        return LlmResponse.from_parts(parts=[
            Part.from_function_call(
                name="put_account_on_test",
                args={"duration_minutes": duration_minutes, "duration_label": duration_label},
            ),
        ])

    return None
