"""
put_account_on_test -- Place the verified branch on test for a duration (UC2).

DEMO NOTE:
    Customer data is MOCKED in-code. Acts on the account in the _resolved_account
    session variable (set by lookup_accounts_by_caller / verify_passcode).

GATE & VALIDATION:
    - Refuses unless passcode_verified is True (defense-in-depth).
    - Accepted duration range: 30 to 480 minutes (30 minutes to 8 hours).
      Out-of-range -> error with agent_action telling the agent to re-ask.
"""

import json

_MIN_DURATION = 30
_MAX_DURATION = 480


def put_account_on_test(duration_minutes: int = 0, duration_label: str = "") -> dict:
    """Place the verified branch on test for the given duration.

    Args:
        duration_minutes: Normalized test duration in minutes (e.g., 60).
        duration_label: Human-friendly duration phrase for read-back (e.g., "one hour").

    Returns:
        dict: status, confirmation details, or an error with an agent_action hint.
    """
    raw = context.state.get("_resolved_account", "")
    try:
        account = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        account = {}

    if not account:
        return {
            "status": "error",
            "error": "No resolved account.",
            "agent_action": "Resolve and confirm the caller's branch first via lookup_accounts_by_caller.",
        }

    if not account.get("passcode_verified"):
        return {
            "status": "error",
            "error": "Passcode not verified.",
            "agent_action": "Verify the caller's passcode with verify_passcode before placing the account on test.",
        }

    if not duration_minutes:
        return {
            "status": "error",
            "error": "Missing duration.",
            "agent_action": "Ask the caller how long they would like the branch on test (30 minutes to 8 hours).",
        }

    if duration_minutes < _MIN_DURATION or duration_minutes > _MAX_DURATION:
        return {
            "status": "error",
            "error": "Duration out of range.",
            "agent_action": "Explain that the accepted range is 30 minutes to 8 hours and ask the caller for a duration within that range.",
        }

    label = duration_label or f"{duration_minutes} minutes"

    return {
        "status": "success",
        "on_test": True,
        "branch_name": account.get("branch_name", ""),
        "account_last_digits": account.get("account_last_digits", ""),
        "duration_minutes": duration_minutes,
        "duration_label": label,
        "message": f"The branch account ending in {account.get('account_last_digits', '')} is now on test for {label}.",
    }
