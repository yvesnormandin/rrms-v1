"""
lookup_accounts_by_caller -- Resolve caller phone number to account(s).

DEMO NOTE:
    All customer data is MOCKED in-code (no real backend). The mock dataset is
    defined in _MOCK_ACCOUNTS below and is duplicated across the action tools so
    each tool is self-contained in the GECX sandbox. Keep the dataset in sync
    across tools if you edit it.

BEHAVIOR:
    - Single-site caller -> returns exactly one account record.
    - Multi-location caller -> returns multiple branch records (drives
      disambiguation in the instruction).
    - Unknown caller -> returns an error with agent_action so the agent can
      apologize and offer an operator transfer.
"""

import json

# -----------------------------------------------------------------------------
# MOCK DATASET (demo fixtures -- placeholder phone numbers, real-word passcodes).
# Keyed by caller phone number. Each value is a list of branch/account records.
# -----------------------------------------------------------------------------
_MOCK_ACCOUNTS = {
    # Single-site caller: Johnson Verizon Store (UC1 -- false-alarm cancellation).
    "+15125550142": [
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
    # Multi-location manager (UC2 -- on-test). Several branches force disambiguation.
    "+12145550199": [
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
            "has_active_alarm": False,
            "dispatch_status": "not dispatched",
        },
        {
            "account_id": "RRMS-2003",
            "branch_name": "Plano",
            "street_address": "789 Elm Street",
            "account_last_digits": "614",
            "passcode": "Harbor",
            "has_active_alarm": False,
            "dispatch_status": "not dispatched",
        },
    ],
}


def lookup_accounts_by_caller(caller_phone: str = "") -> dict:
    """Look up account(s) linked to the caller's phone number.

    Args:
        caller_phone: The caller's phone number. If empty, falls back to the
            caller_phone session variable.

    Returns:
        dict: status, and either a list of account records or an error with an
            agent_action recovery hint.
    """
    phone = caller_phone or context.state.get("caller_phone", "")
    if not phone:
        return {
            "status": "error",
            "error": "No caller phone number available.",
            "agent_action": "Apologize that you cannot locate the account and offer to transfer the caller to a live operator.",
        }

    records = _MOCK_ACCOUNTS.get(phone)
    if not records:
        return {
            "status": "error",
            "error": "No account linked to this phone number.",
            "agent_action": "Apologize that you cannot locate an account for this number and offer to transfer the caller to a live operator.",
        }

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
    if len(accounts) == 1:
        context.state["_resolved_account"] = json.dumps(
            {
                "account_id": accounts[0]["account_id"],
                "branch_name": accounts[0]["branch_name"],
                "street_address": accounts[0]["street_address"],
                "account_last_digits": accounts[0]["account_last_digits"],
                "has_active_alarm": accounts[0]["has_active_alarm"],
                "passcode_verified": False,
            }
        )

    return {
        "status": "success",
        "account_count": len(accounts),
        "accounts": accounts,
    }
