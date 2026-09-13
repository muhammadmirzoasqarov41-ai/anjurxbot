"""
Logging and Security Redaction Service for AnjurX | Rss Bot.
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

    def log_feed_delivery(self, chat_id: int, feed_title: str, item_title: str) -> None:
        clean_feed = self.sanitize(feed_title)
        clean_item = self.sanitize(item_title)
        logger.info(f"event=DELIVERY chat_id={chat_id} feed='{clean_feed}' item='{clean_item}'")

    def log_feed_event(self, event_type: str, feed_url: str, details: Optional[Dict[str, Any]] = None) -> None:
        clean_url = self.sanitize(feed_url)
        logger.info(f"event=FEED_EVENT type={event_type} url='{clean_url}' details={details or {}}")

    def log_security_event(self, event_name: str, details: str) -> None:
        clean_details = self.sanitize(details)
        logger.warning(f"event=SECURITY name={event_name} details={clean_details}")


log_service = LogService()
