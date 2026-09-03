"""
Centralised configuration for the bot.

All environment variables are read here. The application will exit with a
clear error message if any required variable is missing, rather than failing
with a cryptic traceback later.

Usage:
    from app.config import settings
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import FrozenSet

from dotenv import load_dotenv
import os

# Load .env file (no-op if the file does not exist — production uses real env vars)
load_dotenv()


def _require(key: str) -> str:
    """
    Read a required environment variable.

    Exits the process with a descriptive message if the variable is absent or
    empty so that deployment mistakes are obvious immediately at startup.
    """
    value = os.getenv(key, "").strip()
    if not value:
        print(
            f"[CONFIG ERROR] Required environment variable '{key}' is not set. "
            "Please add it to your .env file or Render environment settings.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _optional(key: str, default: str = "") -> str:
    """Read an optional environment variable, returning *default* if absent."""
    return os.getenv(key, default).strip()


def _parse_admin_ids(raw: str) -> FrozenSet[int]:
    """
    Parse a comma-separated list of Telegram user IDs.

    Invalid (non-integer) tokens are silently skipped so that a stray space
    does not crash the bot.
    """
    ids: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            ids.append(int(token))
    return frozenset(ids)


@dataclass(frozen=True)
class Settings:
    """Immutable, typed snapshot of the runtime configuration."""

    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    bot_token: str

    # Frozenset so it is hashable and cannot be mutated accidentally
    admin_ids: FrozenSet[int]

    # ------------------------------------------------------------------ #
    # Firebase / Firestore
    # ------------------------------------------------------------------ #
    firebase_project_id: str
    firebase_private_key_id: str
    firebase_private_key: str       # may contain literal \n — handled in service
    firebase_client_email: str
    firebase_client_id: str
    firebase_auth_uri: str
    firebase_token_uri: str
    firebase_auth_provider_cert_url: str
    firebase_client_cert_url: str

    # Runtime protection limits; environment values override these defaults.
    rate_limit_callback: int = 5
    rate_limit_callback_window: float = 10.0
    rate_limit_setup: int = 3
    rate_limit_setup_window: float = 30.0
    rate_limit_subscription: int = 5
    rate_limit_subscription_window: float = 20.0
    log_level: int = logging.INFO
    timezone: str = "Asia/Tashkent"
    web_admin_key: str = ""

    # ------------------------------------------------------------------ #
    # Convenience helpers
    # ------------------------------------------------------------------ #
    def is_admin(self, user_id: int) -> bool:
        """Return True if *user_id* belongs to an admin."""
        return user_id in self.admin_ids


def _load_settings() -> Settings:
    """Build and validate the :class:`Settings` object from environment vars."""
    return Settings(
        # Telegram
        bot_token=_require("BOT_TOKEN"),
        admin_ids=_parse_admin_ids(_optional("ADMIN_IDS")),

        # Firebase
        firebase_project_id=_require("FIREBASE_PROJECT_ID"),
        firebase_private_key_id=_require("FIREBASE_PRIVATE_KEY_ID"),
        firebase_private_key=_require("FIREBASE_PRIVATE_KEY"),
        firebase_client_email=_require("FIREBASE_CLIENT_EMAIL"),
        firebase_client_id=_require("FIREBASE_CLIENT_ID"),
        firebase_auth_uri=_optional(
            "FIREBASE_AUTH_URI",
            "https://accounts.google.com/o/oauth2/auth",
        ),
        firebase_token_uri=_optional(
            "FIREBASE_TOKEN_URI",
            "https://oauth2.googleapis.com/token",
        ),
        firebase_auth_provider_cert_url=_optional(
            "FIREBASE_AUTH_PROVIDER_X509_CERT_URL",
            "https://www.googleapis.com/oauth2/v1/certs",
        ),
        firebase_client_cert_url=_require("FIREBASE_CLIENT_X509_CERT_URL"),
        rate_limit_callback=int(_optional("RATE_LIMIT_CALLBACK", "5")),
        rate_limit_callback_window=float(_optional("RATE_LIMIT_CALLBACK_WINDOW", "10")),
        rate_limit_setup=int(_optional("RATE_LIMIT_SETUP", "3")),
        rate_limit_setup_window=float(_optional("RATE_LIMIT_SETUP_WINDOW", "30")),
        rate_limit_subscription=int(_optional("RATE_LIMIT_SUBSCRIPTION", "5")),
        rate_limit_subscription_window=float(_optional("RATE_LIMIT_SUBSCRIPTION_WINDOW", "20")),
        log_level=getattr(logging, _optional("LOG_LEVEL", "INFO").upper(), logging.INFO),
        timezone=_optional("TIMEZONE", "Asia/Tashkent"),
        web_admin_key=_optional("WEB_ADMIN_KEY"),
    )


# Singleton — every module imports this one object
settings: Settings = _load_settings()
