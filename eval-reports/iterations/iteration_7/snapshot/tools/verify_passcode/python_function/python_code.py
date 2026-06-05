"""
verify_passcode -- Validate a spoken passcode against the resolved account.

DEMO NOTE:
    Customer data is MOCKED in-code (see _MOCK_ACCOUNTS, kept in sync with the
    other tools). Passcodes are real words (demo fixtures).

BEHAVIOR:
    - Identifies the target account by account_id (preferred, for disambiguated
      multi-location callers) or by caller_phone (single-site callers).
    - Compares the spoken passcode case-insensitively.
    - On success, marks passcode_verified=True in _resolved_account state so the
      action tools can enforce the gate.
    - On failure, returns verified False with an agent_action recovery hint.
"""

import json

# Mirror of the dataset in lookup_accounts_by_caller (keep in sync).
_MOCK_ACCOUNTS = {
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


def verify_passcode(passcode: str = "", account_id: str = "") -> dict:
    """Validate a spoken passcode against the resolved account.

    Args:
        passcode: The passcode spoken by the caller.
        account_id: The account being verified (use for multi-location callers).

    Returns:
        dict: status, verified (bool), and on failure an agent_action hint.
    """
    caller_phone = context.state.get("caller_phone", "")
    record = _find_record(account_id, caller_phone)

    if not record:
        return {
            "status": "error",
            "verified": False,
            "error": "No resolved account to verify against.",
            "agent_action": "Re-confirm which branch the caller means before requesting the passcode.",
        }

    if not passcode:
        return {
            "status": "error",
            "verified": False,
            "error": "No passcode provided.",
            "agent_action": "Ask the caller to provide the account passcode.",
        }

    # Normalize whitespace and case: ASR often splits compound spoken words
    # ("Bluebird" -> "Blue Bird") and lowercases them. Real callers on the
    # phone hit this, so the tool — not the eval — must absorb it.
    verified = (
        passcode.replace(" ", "").strip().lower()
        == record["passcode"].replace(" ", "").lower()
    )

    if verified:
        context.state["_resolved_account"] = json.dumps(
            {
                "account_id": record["account_id"],
                "branch_name": record["branch_name"],
                "street_address": record["street_address"],
                "account_last_digits": record["account_last_digits"],
                "has_active_alarm": record["has_active_alarm"],
                "passcode_verified": True,
            }
        )
        return {
            "status": "success",
            "verified": True,
            "branch_name": record["branch_name"],
            "account_last_digits": record["account_last_digits"],
        }

    return {
        "status": "success",
        "verified": False,
        "agent_action": "Tell the caller the passcode did not match and ask them to try again. Allow up to 2 retries (3 attempts total); after the final failure, offer to transfer to a live operator.",
    }


def _find_record(account_id: str, caller_phone: str) -> dict:
    """Locate a mock account record by account_id, else by single-site phone."""
    if account_id:
        for records in _MOCK_ACCOUNTS.values():
            for r in records:
                if r["account_id"] == account_id:
                    return r
    if caller_phone:
        records = _MOCK_ACCOUNTS.get(caller_phone, [])
        if len(records) == 1:
            return records[0]
    return {}
