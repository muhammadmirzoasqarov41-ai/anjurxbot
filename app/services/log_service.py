"""
Logging and Security Redaction Service.
Ensures sensitive tokens, private keys, and passwords never appear in console logs.
"""
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("anjurxbot.audit")

# Redaction patterns
TOKEN_PATTERN = re.compile(r"\b\d{8,10}:[a-zA-Z0-9_-]{35}\b")
PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[^-]+-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL)


class LogService:
    def sanitize(self, text: str) -> str:
        if not text or not isinstance(text, str):
            return ""
        text = TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", text)
        text = PRIVATE_KEY_PATTERN.sub("[REDACTED_PRIVATE_KEY]", text)
        return text

    def log_moderation(
        self,
        group_id: int,
        user_id: int,
        action: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        clean_reason = self.sanitize(reason)
        logger.info(
            f"event=MODERATION group_id={group_id} user_id={user_id} action={action} reason={clean_reason}"
        )

    def log_security_event(self, event_name: str, details: str) -> None:
        clean_details = self.sanitize(details)
        logger.warning(f"event=SECURITY name={event_name} details={clean_details}")


log_service = LogService()
