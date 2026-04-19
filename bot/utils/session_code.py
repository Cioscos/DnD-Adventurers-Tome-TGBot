"""Invite-code generator for game sessions.

Avoids visually ambiguous characters (0/O, 1/I/L) so codes can be dictated by
voice without confusion. 32^6 ≈ 1.07 billion possible codes.
"""

from __future__ import annotations

import secrets

_SAFE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_LENGTH = 6


def generate_session_code() -> str:
    """Return a random 6-character alphanumeric invite code."""
    return "".join(secrets.choice(_SAFE_ALPHABET) for _ in range(_CODE_LENGTH))
