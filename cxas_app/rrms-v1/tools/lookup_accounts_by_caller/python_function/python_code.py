"""
lookup_accounts_by_caller -- Resolve caller phone number to account(s).

DEMO NOTE:
    All customer data is MOCKED in-code (no real backend). _MOCK_ACCOUNTS below
    is the SINGLE SOURCE OF TRUTH for the demo customers — edit it here only.
    Downstream tools never hold a copy: this tool writes the caller's full
    records (including private fields like passcode and dispatch_status) to the
    _caller_accounts session variable, and verify_passcode / the action tools
    read state instead. Private fields stay out of the tool's RETURN value, so
    the model never sees them.

BEHAVIOR:
    - Every known caller -> returns the caller's company_name (one company per
      caller, even multi-branch — used in the personalized greeting).
    - Single-site caller -> returns exactly one account record.
    - Multi-location caller -> returns multiple branch records (drives
      disambiguation in the instruction).
    - Unknown caller -> returns an error with agent_action so the agent can
      apologize and offer an operator transfer.
"""

import json

# -----------------------------------------------------------------------------
# MOCK DATASET (demo fixtures -- placeholder phone numbers, real-word passcodes).
# Keyed by caller phone number. Each value holds ONE company_name (companies are
# single entities even when multi-branch — company_name lives OUTSIDE the branch
# records) plus the list of branch/account records.
# -----------------------------------------------------------------------------
_MOCK_ACCOUNTS = {
    # Single-site caller: Johnson Verizon Store (UC1 -- false-alarm cancellation).
    # Single branch, so the company name matches the branch name.
    "+15125550142": {
        "company_name": "Johnson Verizon Store",
        "branches": [
            {
                "account_id": "RRMS-1001",
                "branch_name": "Johnson Verizon Store",
                "street_address": "742 Commerce Drive",
                "account_last_digits": "118",
                "passcode": "Sunset",
                "has_active_alarm": True,
                "dispatch_status": "not dispatched",
            }
        ],
    },
    # Multi-location manager (UC2 -- on-test). Several branches force disambiguation.
    "+12145550199": {
        "company_name": "Lone Star Communications",
        "branches": [
            {
                "account_id": "RRMS-2001",
                "branch_name": "Dallas",
                "street_address": "123 Main Street",
                "account_last_digits": "345",
                "passcode": "Bluebird",
                "has_active_alarm": False,
                "dispatch_status": "not dispatched",
            },
            {
                "account_id": "RRMS-2002",
                "branch_name": "Fort Worth",
                "street_address": "456 Oak Avenue",
                "account_last_digits": "782",
                "passcode": "Maple",
                "has_active_alarm": True,
                "dispatch_status": "not dispatched",
            },
            {
                "account_id": "RRMS-2003",
                "branch_name": "Plano",
                "street_address": "789 Elm Street",
                "account_last_digits": "614",
                "passcode": "Harbor",
                "has_active_alarm": True,
                "dispatch_status": "dispatched",
            },
        ],
    },
}


def lookup_accounts_by_caller() -> dict:
    """Look up account(s) linked to the caller's phone number.

    The caller's phone number is read from the caller_phone session variable
    (set by the telephony platform). It is never supplied by the model, so the
    lookup is deterministic and immune to misheard/reformatted numbers.

    Returns:
        dict: status, and either the caller's company_name plus a list of
            account records, or an error with an agent_action recovery hint.
    """
    phone = context.state.get("caller_phone", "")
    if not phone:
        return {
            "status": "error",
            "error": "No caller phone number available.",
            "agent_action": "Apologize that you cannot locate the account and offer to transfer the caller to a live operator.",
        }

    customer = _MOCK_ACCOUNTS.get(phone)
    if not customer:
        return {
            "status": "error",
            "error": "No account linked to this phone number.",
            "agent_action": "Apologize that you cannot locate an account for this number and offer to transfer the caller to a live operator.",
        }
    records = customer["branches"]

    # Single source of truth: stash the caller's FULL records (incl. passcode,
    # dispatch_status) in session state for verify_passcode / action tools.
    # State is never shown to the model — only the return value below is.
    context.state["_caller_accounts"] = json.dumps(records)

    # Public view excludes the passcode (never returned to the agent/caller).
    accounts = [
        {
            "account_id": r["account_id"],
            "branch_name": r["branch_name"],
            "street_address": r["street_address"],
            "account_last_digits": r["account_last_digits"],
            "has_active_alarm": r["has_active_alarm"],
        }
        for r in records
    ]

    # If single account, resolve it now so downstream tools have context.
    if len(records) == 1:
        context.state["_resolved_account"] = json.dumps(
            {
                "account_id": records[0]["account_id"],
                "branch_name": records[0]["branch_name"],
                "street_address": records[0]["street_address"],
                "account_last_digits": records[0]["account_last_digits"],
                "has_active_alarm": records[0]["has_active_alarm"],
                "dispatch_status": records[0]["dispatch_status"],
                "passcode_verified": False,
            }
        )

    return {
        "status": "success",
        "company_name": customer["company_name"],
        "account_count": len(accounts),
        "accounts": accounts,
    }
