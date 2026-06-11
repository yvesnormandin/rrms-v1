"""
verify_passcode -- Validate a spoken passcode against the resolved account.

DEMO NOTE:
    Customer data is mocked, with a SINGLE SOURCE OF TRUTH in
    lookup_accounts_by_caller (_MOCK_ACCOUNTS). That tool writes the caller's
    full records to the _caller_accounts session variable; this tool reads them
    from state — it holds no dataset copy. Passcodes never appear in any tool's
    return value, so the model never sees them.

MATCHING POLICY (fuzzy, voice-friendly):
    The spoken passcode is accepted when its Levenshtein (edit) distance from
    the stored passcode is <= 2, after normalizing BOTH strings:
      - lower-cased
      - accents/diacritics removed ("café" -> "cafe")
      - all whitespace removed (ASR splits compound words: "Bluebird" -> "Blue Bird")
      - all punctuation removed
    This absorbs the transcription errors real phone callers hit (casing,
    word-splitting, a couple of misheard letters — e.g. ASR hearing
    "blueberg" for "Bluebird", distance 2) while still rejecting genuinely
    wrong passcodes (the demo's wrong-passcode fixtures are all distance >= 3
    from the real ones).

BEHAVIOR:
    - Requires lookup_accounts_by_caller to have run first (it populates
      _caller_accounts); otherwise returns an error with a recovery hint.
    - Identifies the target account by account_id (preferred, for disambiguated
      multi-location callers) or implicitly when the caller has one account.
    - On success, writes _resolved_account with passcode_verified=True (and
      dispatch_status) so the action tools can enforce the gate.
    - On failure, returns verified False with an agent_action recovery hint.
"""

import json
import unicodedata


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

    # Fuzzy match (see MATCHING POLICY above): accept when the normalized
    # edit distance is <= 2 — absorbs ASR casing, word-splitting, accents,
    # and up to two misheard characters ("blueberg" for "Bluebird").
    verified = _distance(passcode, record["passcode"]) <= 2

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


def _normalize(s: str) -> str:
    """Lower-case the string, strip accents, whitespace and punctuation.

    Accents/diacritics are removed by decomposing to NFKD and dropping the
    combining marks, so "café" -> "cafe" and "Noël" -> "noel". Uses Unicode
    categories so it behaves sensibly on accented and non-ASCII text:
    whitespace, combining marks (category 'Mn') and punctuation (categories
    starting with 'P') are dropped.
    """
    s = s.lower()
    # Decompose accented characters into base char + combining mark(s).
    s = unicodedata.normalize("NFKD", s)
    result = []
    for ch in s:
        if ch.isspace():
            continue
        category = unicodedata.category(ch)
        if category == "Mn":  # combining mark (the accent itself)
            continue
        if category.startswith("P"):  # any punctuation
            continue
        result.append(ch)
    return "".join(result)


def _levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein distance between strings a and b.

    Cost of 1 for each insertion, deletion, or substitution. Implemented with
    a space-optimized dynamic-programming row (O(len(a) * len(b)) time,
    O(min(len(a), len(b))) space).
    """
    # Keep the shorter string as the inner loop to minimize memory.
    if len(a) < len(b):
        a, b = b, a

    if len(b) == 0:
        return len(a)

    previous_row = list(range(len(b) + 1))

    for i, ca in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            deletion = previous_row[j] + 1
            insertion = current_row[j - 1] + 1
            substitution = previous_row[j - 1] + (0 if ca == cb else 1)
            current_row[j] = min(deletion, insertion, substitution)
        previous_row = current_row

    return previous_row[-1]


def _distance(s1: str, s2: str) -> int:
    """Normalize both strings, then return their Levenshtein distance."""
    return _levenshtein(_normalize(s1), _normalize(s2))


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
