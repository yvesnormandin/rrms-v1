"""
send_confirmation_sms -- Send a (mock) SMS confirmation of the completed action.

DEMO NOTE:
    No real SMS is sent. This returns a mock success. Call only after the caller
    has accepted the SMS offer. The destination phone defaults to the caller_phone
    session variable.
"""

import json


def send_confirmation_sms(message_summary: str = "") -> dict:
    """Send a mock SMS confirmation to the caller.

    Args:
        message_summary: A short summary of the action to confirm in the text
            (e.g., "Dallas branch on test for one hour").

    Returns:
        dict: status and the (mock) delivery details.
    """
    to_phone = context.state.get("caller_phone", "")

    if not to_phone:
        return {
            "status": "error",
            "sent": False,
            "error": "No destination phone number on file for this caller.",
            "agent_action": "Tell the caller you do not have a phone number on file to text, and continue without sending the confirmation SMS.",
        }

    raw = context.state.get("_resolved_account", "")
    try:
        account = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        account = {}

    summary = message_summary or "your recent request"

    return {
        "status": "success",
        "sent": True,
        "to": to_phone,
        "branch_name": account.get("branch_name", ""),
        "message": f"A confirmation text for {summary} has been sent.",
    }
