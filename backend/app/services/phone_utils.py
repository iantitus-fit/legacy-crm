"""Phone number utilities for SMS — normalization, formatting, matching.

The CRM stores phone numbers in their human-readable as-imported form
(e.g. "(765) 555-0181"). Twilio requires E.164 (+1XXXXXXXXXX). Conversion
happens in the service layer, not the database.
"""
import re
from typing import Optional


def normalize_to_e164(phone: Optional[str]) -> Optional[str]:
    """Normalize a US phone number to E.164 (+1XXXXXXXXXX).

    Returns None when the input cannot be parsed as a valid US number.
    Handles formats like:
      "(765) 555-0181"
      "765-555-0181"
      "7655550181"
      "+17655550181"
      "1-765-555-0181"
      "765.555.0181"
    """
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]

    if len(digits) != 10:
        return None

    # Reject obviously invalid area codes (must start 2-9 per NANP)
    if digits[0] in ("0", "1"):
        return None
    # Exchange code must also start 2-9
    if digits[3] in ("0", "1"):
        return None

    return f"+1{digits}"


def format_for_display(e164: Optional[str]) -> Optional[str]:
    """Convert +17655550181 to (765) 555-0181 for display.

    Returns the input unchanged if it isn't a valid E.164 US number.
    """
    if not e164:
        return None
    normalized = normalize_to_e164(e164)
    if not normalized:
        return e164
    d = normalized[2:]  # strip +1
    return f"({d[0:3]}) {d[3:6]}-{d[6:10]}"


def match_phone(stored: Optional[str], incoming: Optional[str]) -> bool:
    """Compare two phone numbers ignoring formatting differences."""
    a = normalize_to_e164(stored)
    b = normalize_to_e164(incoming)
    if a is None or b is None:
        return False
    return a == b
