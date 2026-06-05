"""
Callback Tests — before_agent_callback (Root Agent, default demo CLID)

Tests the GTP default-CLID callback: live telephony callers arrive with no
caller_phone in session state, so the callback sets the deployment variant's
DEFAULT_CALLER_PHONE; eval-supplied session parameters must always win.

BRANCHES COVERED:
    Missing caller_phone -> default applied, returns None     -> TestDefaultApplied
    caller_phone preset (eval session param) -> NOT overridden -> TestEvalValueWins
    Every-turn re-fire -> state unchanged on second call        -> TestEveryTurnGuard
    Falsy-but-present value ("") -> treated as missing          -> TestFalsyValue

RUNNING:
    pytest evals/callback_tests/tests/ -v
"""

import sys
import os

# -------------------------------------------------------------------------
# MOCK INJECTION: Add the python_code.py directory to sys.path and import the
# REAL module, then attach the GECX-provided globals BEFORE importing the
# function under test (the callback's type annotations reference
# CallbackContext/Content as bare names the sandbox auto-provides).
# -------------------------------------------------------------------------
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "agents", "root_agent",
    "before_agent_callbacks", "before_agent",
))

from cxas_scrapi.utils.callback_libs import (  # noqa: E402
    CallbackContext,
    Content,
)

import python_code  # noqa: E402

python_code.CallbackContext = CallbackContext
python_code.Content = Content

from python_code import before_agent_callback, DEFAULT_CALLER_PHONE  # noqa: E402


def _ctx(state=None):
    return CallbackContext(state=(state if state is not None else {}), events=[])


class TestDefaultApplied:
    """Live GTP caller: no caller_phone in session -> variant default set."""

    def test_sets_default_when_missing(self):
        ctx = _ctx({})
        result = before_agent_callback(ctx)
        assert result is None
        assert ctx.state["caller_phone"] == DEFAULT_CALLER_PHONE

    def test_default_is_a_mock_dataset_clid(self):
        # The canonical default must be the single-site demo CLID so the
        # canonical app resolves a real mock customer out of the box.
        assert DEFAULT_CALLER_PHONE == "+15125550142"


class TestEvalValueWins:
    """Eval session_parameters land in state before the callback -> never override."""

    def test_preset_value_not_overridden(self):
        ctx = _ctx({"caller_phone": "+12145550199"})
        result = before_agent_callback(ctx)
        assert result is None
        assert ctx.state["caller_phone"] == "+12145550199"

    def test_other_state_untouched(self):
        ctx = _ctx({"caller_phone": "+12145550199", "_resolved_account": "{}"})
        before_agent_callback(ctx)
        assert ctx.state["_resolved_account"] == "{}"


class TestEveryTurnGuard:
    """before_agent fires on EVERY turn; the second fire must be a no-op."""

    def test_second_invocation_leaves_state_unchanged(self):
        ctx = _ctx({})
        before_agent_callback(ctx)
        first = dict(ctx.state)
        result = before_agent_callback(ctx)
        assert result is None
        assert dict(ctx.state) == first

    def test_second_invocation_does_not_clobber_mid_call_state(self):
        ctx = _ctx({})
        before_agent_callback(ctx)
        ctx.state["_resolved_account"] = '{"passcode_verified": true}'
        before_agent_callback(ctx)
        assert ctx.state["_resolved_account"] == '{"passcode_verified": true}'
        assert ctx.state["caller_phone"] == DEFAULT_CALLER_PHONE


class TestFalsyValue:
    """An empty-string caller_phone counts as missing."""

    def test_empty_string_replaced_with_default(self):
        ctx = _ctx({"caller_phone": ""})
        result = before_agent_callback(ctx)
        assert result is None
        assert ctx.state["caller_phone"] == DEFAULT_CALLER_PHONE
