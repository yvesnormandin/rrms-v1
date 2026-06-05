"""
verify_passcode -- Validate a spoken passcode against the resolved account.

DEMO NOTE:
    Customer data is mocked, with a SINGLE SOURCE OF TRUTH in
    lookup_accounts_by_caller (_MOCK_ACCOUNTS). That tool writes the caller's
    full records to the _caller_accounts session variable; this tool reads them
    from state — it holds no dataset copy. Passcodes never appear in any tool's
    return value, so the model never sees them.

BEHAVIOR:
    - Requires lookup_accounts_by_caller to have run first (it populates
      _caller_accounts); otherwise returns an error with a recovery hint.
    - Identifies the target account by account_id (preferred, for disambiguated
      multi-location callers) or implicitly when the caller has one account.
    - Compares the spoken passcode case-insensitively and whitespace-tolerantly.
    - On success, writes _resolved_account with passcode_verified=True (and
      dispatch_status) so the action tools can enforce the gate.
    - On failure, returns verified False with an agent_action recovery hint.
"""

import json


def verify_passcode(passcode: str = "", account_id: str = "") -> dict:
    """Validate a spoken passcode against the resolved account.

    Args:
        passcode: The passcode spoken by the caller.
        account_id: The account being verified (use for multi-location callers).

    Returns:
        dict: status, verified (bool), and on failure an agent_action hint.
    """
    record = _find_record(account_id)

    if not record:
        return {
            "status": "error",
            "verified": False,
            "error": "No resolved account to verify against.",
            "agent_action": "Resolve the caller's account first via lookup_accounts_by_caller, and re-confirm which branch the caller means before requesting the passcode.",
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
                "dispatch_status": record["dispatch_status"],
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


def _find_record(account_id: str) -> dict:
    """Locate the target record in _caller_accounts session state.

    By account_id when given (disambiguated multi-location caller); otherwise
    only an unambiguous single-account caller resolves implicitly.
    """
    raw = context.state.get("_caller_accounts", "")
    try:
        records = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        records = []

    if account_id:
        for r in records:
            if r.get("account_id") == account_id:
                return r
    if len(records) == 1:
        return records[0]
    return {}
