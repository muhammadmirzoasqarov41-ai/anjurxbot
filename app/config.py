"""
Application configuration module.
Loads and validates environment variables securely without leaking credentials.
"""
import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

logger = logging.getLogger("anjurxbot.config")


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())
    bot_username: str = field(default_factory=lambda: os.getenv("BOT_USERNAME", "").strip())
    admin_ids: List[int] = field(default_factory=list)
    firebase_service_account: Optional[dict] = None
    firebase_project_id: str = field(default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", "").strip())
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))
    web_admin_key: str = field(default_factory=lambda: os.getenv("WEB_ADMIN_KEY", "").strip())
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Tashkent").strip())
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"))
    
    # Cache and Rate Limiting TTLs
    cache_ttl_group_config: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_GROUP_CONFIG", "300")))
    cache_ttl_member_status: int = field(default_factory=lambda: int(os.getenv("CACHE_TTL_MEMBER_STATUS", "60")))
    rate_limit_default: float = field(default_factory=lambda: float(os.getenv("RATE_LIMIT_DEFAULT", "2.0")))
    rate_limit_subscription: float = field(default_factory=lambda: float(os.getenv("RATE_LIMIT_SUBSCRIPTION", "3.0")))
    rate_limit_subscription_window: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_SUBSCRIPTION_WINDOW", "5.0"))
    )

    def __post_init__(self):
        # Parse Admin IDs
        raw_admin_ids = os.getenv("ADMIN_IDS", "").strip()
        if raw_admin_ids:
            parsed = []
            for item in raw_admin_ids.split(","):
                clean = item.strip()
                if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
                    parsed.append(int(clean))
            self.admin_ids = parsed

        # Parse Firebase Service Account
        raw_sa = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
        file_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "").strip() or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

        if raw_sa:
            try:
                if raw_sa.startswith("{") and raw_sa.endswith("}"):
                    self.firebase_service_account = json.loads(raw_sa)
                elif os.path.exists(raw_sa):
                    with open(raw_sa, "r", encoding="utf-8") as f:
                        self.firebase_service_account = json.load(f)
            except Exception as e:
                logger.error("error_type=FirebaseConfigError message=Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON")

        if not self.firebase_service_account and file_path and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.firebase_service_account = json.load(f)
            except Exception as e:
                logger.error(f"error_type=FirebaseConfigError message=Failed to load credentials from file {file_path}")

        # Sanitize private_key if needed (e.g. literal escaped \n from env vars)
        if self.firebase_service_account and isinstance(self.firebase_service_account.get("private_key"), str):
            pk = self.firebase_service_account["private_key"]
            if "\\n" in pk:
                self.firebase_service_account["private_key"] = pk.replace("\\n", "\n")

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def has_token(self) -> bool:
        return bool(self.bot_token and len(self.bot_token) > 10)


# Global singleton instance
config = Config()
