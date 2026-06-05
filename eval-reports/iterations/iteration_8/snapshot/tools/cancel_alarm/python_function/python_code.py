"""
cancel_alarm -- Cancel the active alarm on the verified account (UC1).

DEMO NOTE:
    Customer data is MOCKED in-code. This tool acts on the account resolved and
    verified earlier in the conversation, read from the _resolved_account session
    variable (set by lookup_accounts_by_caller / verify_passcode).

GATE:
    Refuses to act unless passcode_verified is True in _resolved_account. This is
    defense-in-depth; the instruction also enforces the passcode gate.
"""

import json


def cancel_alarm() -> dict:
    """Cancel the active alarm on the verified account.

    Returns:
        dict: status, confirmation details (branch, dispatch status), or an
            error with an agent_action recovery hint.
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
            "agent_action": "Resolve the caller's account first via lookup_accounts_by_caller.",
        }

    if not account.get("passcode_verified"):
        return {
            "status": "error",
            "error": "Passcode not verified.",
            "agent_action": "Verify the caller's passcode with verify_passcode before canceling the alarm.",
        }

    if not account.get("has_active_alarm"):
        return {
            "status": "no_active_alarm",
            "branch_name": account.get("branch_name", ""),
            "agent_action": "Inform the caller there is no active alarm signal on the account and nothing to cancel, then offer further help.",
        }

    # Mock cancellation: clear the active alarm in state.
    account["has_active_alarm"] = False
    context.state["_resolved_account"] = json.dumps(account)

    # Data-driven dispatch status (carried into _resolved_account by
    # lookup_accounts_by_caller / verify_passcode from the mock dataset).
    dispatch_status = account.get("dispatch_status", "not dispatched")
    return {
        "status": "success",
        "canceled": True,
        "branch_name": account.get("branch_name", ""),
        "dispatch_status": dispatch_status,
        "message": f"The alarm has been canceled. Police were {dispatch_status}.",
    }
