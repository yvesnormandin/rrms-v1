"""
before_agent_callback — Root Agent (default demo CLID)

PURPOSE:
    Default the `caller_phone` session variable for live telephony (GTP)
    callers. The demo is publicly callable, so real callers' CLIDs are not in
    the mock dataset — instead, each deployed GTP variant hard-codes one demo
    CLID so every caller to that number maps to a fixed mock customer.

DEPLOYMENT VARIANTS:
    DEFAULT_CALLER_PHONE below is the single point of per-variant
    substitution — deploy-variants.sh rewrites it when regenerating the GTP
    variant apps from this canonical source:
      rrms-demo-store     -> "+15125550142" (Johnson Verizon Store, UC1)
      rrms-demo-multisite -> "+12145550199" (Dallas/Fort Worth/Plano, UC2)
    The canonical dev/eval app keeps the single-site CLID.

EVAL COMPATIBILITY:
    Eval session_parameters populate state BEFORE this callback runs, so the
    missing-only guard means eval-supplied caller_phone values always win and
    the existing golden/sim suites pass unchanged on any variant.

IMPORTANT: before_agent_callback fires on EVERY agent turn, not just once at
    conversation start. The set-only-if-missing check doubles as the required
    early-return guard — once set, state is never touched again.

PLATFORM GLOBALS (do NOT import these):
    CallbackContext, Content, Part, LlmResponse, LlmRequest are auto-provided
    by the GECX sandbox at runtime. Only standard library imports are needed.
"""

from typing import Optional

# Substituted per deployment variant by deploy-variants.sh — see module
# docstring. Do not rename without updating that script.
DEFAULT_CALLER_PHONE = "+15125550142"


def before_agent_callback(callback_context: CallbackContext) -> Optional[Content]:
    state = callback_context.state

    # Set the variant's demo CLID ONLY when the session has no caller_phone:
    # live GTP callers arrive without one; evals supply theirs via
    # session_parameters (which land in state before this runs) and must win.
    # The same check guards against the every-turn re-fire.
    if not state.get("caller_phone"):
        state["caller_phone"] = DEFAULT_CALLER_PHONE

    return None
