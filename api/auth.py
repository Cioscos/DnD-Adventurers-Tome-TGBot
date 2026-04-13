"""Telegram Mini App initData verification.

Every API endpoint (except /health) requires the raw ``initData`` string from
``window.Telegram.WebApp.initData`` passed as the ``X-Telegram-Init-Data``
request header. This module verifies its HMAC-SHA256 signature and extracts
the authenticated Telegram user_id.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# When set, bypasses Telegram initData verification and returns this user_id.
# Set DEV_USER_ID=<your_telegram_id> in .env for local development.
DEV_USER_ID: int | None = int(os.environ["DEV_USER_ID"]) if os.environ.get("DEV_USER_ID") else None
_DEV_USER_ID = DEV_USER_ID  # kept for internal use

# Maximum age (in seconds) of a valid initData.
_MAX_AGE_SECONDS = 86400  # 24 hours


def _compute_secret_key(bot_token: str) -> bytes:
    """Derive the HMAC secret key from the bot token per Telegram's spec."""
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(init_data: str, bot_token: str = _BOT_TOKEN) -> int:
    """Verify *init_data* and return the authenticated Telegram user_id.

    Raises ``HTTPException(401)`` on any verification failure.
    """
    if not bot_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BOT_TOKEN not configured",
        )

    # Parse the URL-encoded string into key/value pairs.
    pairs = dict(parse_qsl(unquote(init_data), keep_blank_values=True))
    logger.debug("initData parsed keys: %s", list(pairs.keys()))

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        logger.warning("initData missing 'hash' field. Raw (first 200 chars): %.200s", init_data)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing hash in initData",
        )

    # Build the data-check string: sorted key=value pairs joined by '\n'.
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(pairs.items())
    )
    logger.debug("data_check_string:\n%s", data_check_string)

    # Compute the expected HMAC.
    secret_key = _compute_secret_key(bot_token)
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        logger.warning(
            "initData signature mismatch. expected=%s received=%s keys=%s",
            expected_hash, received_hash, list(pairs.keys()),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid initData signature",
        )

    # Validate freshness.
    auth_date = pairs.get("auth_date")
    if auth_date and abs(time.time() - int(auth_date)) > _MAX_AGE_SECONDS:
        logger.warning("initData expired. auth_date=%s now=%s", auth_date, int(time.time()))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="initData expired",
        )

    # Extract user_id from the 'user' JSON field.
    user_json = pairs.get("user")
    if not user_json:
        logger.warning("initData missing 'user' field. keys=%s", list(pairs.keys()))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user in initData",
        )
    try:
        user = json.loads(user_json)
        user_id = int(user["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("initData invalid 'user' field: %s", user_json)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user field in initData",
        ) from exc

    return user_id


def get_current_user(
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
) -> int:
    """FastAPI dependency that returns the verified Telegram user_id."""
    if _DEV_USER_ID is not None:
        return _DEV_USER_ID
    if not x_telegram_init_data:
        logger.warning("Request missing X-Telegram-Init-Data header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Telegram-Init-Data header",
        )
    logger.debug("X-Telegram-Init-Data header length: %d", len(x_telegram_init_data))
    return verify_init_data(x_telegram_init_data)
