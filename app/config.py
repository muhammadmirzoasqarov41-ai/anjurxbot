"""
Application configuration module.
Loads and validates environment variables securely without leaking credentials.
"""
import os
import json
import base64
import logging
from dataclasses import dataclass, field
from typing import List, Optional
try:
    from dotenv import load_dotenv
    # Load .env if present
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("anjurxbot.config")


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    bot_username: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", "").strip())
    super_admin_id: Optional[int] = None
    admin_ids: List[int] = field(default_factory=list)
    firebase_service_account: Optional[dict] = None
    firebase_project_id: str = field(
        default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", "anjurxbot").strip() or "anjurxbot"
    )
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))
    web_admin_key: str = field(default_factory=lambda: os.getenv("WEB_ADMIN_KEY", "").strip())
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Tashkent").strip())
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"))
    
    # RSS Feed Polling and Rate Limits
    min_interval: int = field(default_factory=lambda: int(os.getenv("MIN_INTERVAL", "300")))
    max_interval: int = field(default_factory=lambda: int(os.getenv("MAX_INTERVAL", "43200")))
    max_feed_size: int = field(default_factory=lambda: int(os.getenv("MAX_FEED_SIZE", "5242880")))
    rate_limit_default: float = field(default_factory=lambda: float(os.getenv("RATE_LIMIT_DEFAULT", "1.0")))
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "./data/rssbot.json").strip())

    def __post_init__(self):
        # 1. Parse SUPER_ADMIN_ID strictly as numeric integer
        raw_super_admin = os.getenv("SUPER_ADMIN_ID", "8157452043").strip()
        parsed_super_admin: Optional[int] = None
        if raw_super_admin:
            try:
                parsed_super_admin = int(raw_super_admin)
                logger.info(f"SUPER_ADMIN_ID is configured and parsed: {parsed_super_admin}")
            except ValueError:
                logger.error(
                    f"error_type=ConfigError message=SUPER_ADMIN_ID '{raw_super_admin}' is invalid! Must be numeric Telegram user ID."
                )
                parsed_super_admin = 8157452043

        # 2. Parse additional ADMIN_IDS / ADMIN_ID if provided
        raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
        raw_single_admin = os.getenv("ADMIN_ID", "").strip()
        parsed_admin_ids: List[int] = []
        if parsed_super_admin is not None:
            parsed_admin_ids.append(parsed_super_admin)

        for val in [raw_admin_ids, raw_single_admin]:
            if val:
                for item in val.split(","):
                    clean = item.strip()
                    if clean:
                        try:
                            clean_int = int(clean)
                            parsed_admin_ids.append(clean_int)
                        except ValueError:
                            logger.warning(f"Skipping invalid admin ID value in env: '{clean}'")

        self.admin_ids = list(dict.fromkeys(parsed_admin_ids))
        self.super_admin_id = parsed_super_admin or (self.admin_ids[0] if self.admin_ids else None)

        # Parse Firebase Service Account
        raw_sa = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        raw_b64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64", "").strip()
        file_path = (
            os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip()
            or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        )

        if raw_sa:
            try:
                if raw_sa.startswith("{") and raw_sa.endswith("}"):
                    self.firebase_service_account = json.loads(raw_sa)
                elif os.path.exists(raw_sa):
                    with open(raw_sa, "r", encoding="utf-8") as f:
                        self.firebase_service_account = json.load(f)
                else:
                    # Attempt base64 decode of raw_sa if it's encoded
                    try:
                        decoded = base64.b64decode(raw_sa).decode("utf-8")
                        if decoded.startswith("{") and decoded.endswith("}"):
                            self.firebase_service_account = json.loads(decoded)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"error_type=FirebaseConfigError message=Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON: {e}")

        if not self.firebase_service_account and raw_b64:
            try:
                decoded = base64.b64decode(raw_b64).decode("utf-8")
                self.firebase_service_account = json.loads(decoded)
            except Exception as e:
                logger.error(f"error_type=FirebaseConfigError message=Failed to parse FIREBASE_SERVICE_ACCOUNT_BASE64: {e}")

        if not self.firebase_service_account and file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.firebase_service_account = json.load(f)
            except Exception as e:
                logger.error(f"error_type=FirebaseConfigError message=Failed to load credentials from file {file_path}: {e}")

        # Individual environment variables fallback (Render friendly)
        if not self.firebase_service_account:
            client_email = os.getenv("FIREBASE_CLIENT_EMAIL", "").strip()
            private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").strip()
            project_id = os.getenv("FIREBASE_PROJECT_ID", "").strip() or self.firebase_project_id
            if client_email and private_key:
                self.firebase_service_account = {
                    "type": "service_account",
                    "project_id": project_id,
                    "private_key": private_key,
                    "client_email": client_email,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }

        # Sanitize private_key if needed (e.g. literal escaped \n from env vars)
        if self.firebase_service_account and isinstance(self.firebase_service_account.get("private_key"), str):
            pk = self.firebase_service_account["private_key"]
            if "\\n" in pk:
                self.firebase_service_account["private_key"] = pk.replace("\\n", "\n")

        # Sync project_id from service account if specified
        if self.firebase_service_account and self.firebase_service_account.get("project_id"):
            self.firebase_project_id = self.firebase_service_account["project_id"]

    def is_super_admin(self, user_id: Optional[int]) -> bool:
        """
        Strict ID-based check for Super Admin.
        Security rule: Super Admin access is granted solely by Telegram numeric User ID, never by username.
        Telegram username changing does NOT revoke super-admin rights.
        """
        if user_id is None:
            return False
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            return False

        if self.super_admin_id is not None and uid == self.super_admin_id:
            return True
        return uid in self.admin_ids

    def is_admin(self, user_id: Optional[int] = None, username: Optional[str] = None) -> bool:
        """Strict ID-based authorization helper. Usernames are never used for privilege checks."""
        return self.is_super_admin(user_id)

    def has_token(self) -> bool:
        return bool(self.bot_token and len(self.bot_token) > 10)


# Global singleton instance
config = Config()
