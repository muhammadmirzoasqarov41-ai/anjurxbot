"""
Content analysis services for the Guard system.

Provides stateless detection functions for:
  - Links (anti_link)
  - Advertisements (anti_ads)
  - Repeated messages (anti_repeat)
  - Bad words (bad_words)
  - Composite spam check (anti_spam)

All functions are pure — they take a Message and return bool.
No Firestore reads happen here; settings are injected by the middleware.

Design principles:
  * No ReDoS-prone regexes (patterns are simple and anchored where possible)
  * Prefer Telegram entity parsing over regex when available
  * False positives are minimised — when in doubt, allow the message
"""

from __future__ import annotations

import collections
import hashlib
import re
import time
from typing import Deque, DefaultDict

from aiogram.enums import MessageEntityType
from aiogram.types import Message

# ------------------------------------------------------------------ #
# Anti-Link
# ------------------------------------------------------------------ #

# Entity types that indicate a URL in the message
_URL_ENTITY_TYPES = {
    MessageEntityType.URL,
    MessageEntityType.TEXT_LINK,
}

# Fallback regex for links not caught by entities
_LINK_RE = re.compile(
    r"(?:https?://|www\.|t\.me/|telegram\.me/)\S+",
    re.IGNORECASE,
)


def has_link(message: Message) -> bool:
    """
    Return True if the message contains any clickable URL.

    First checks Telegram message entities (most reliable),
    then falls back to a simple regex.
    """
    # Check entities first
    entities = message.entities or []
    for entity in entities:
        if entity.type in _URL_ENTITY_TYPES:
            return True

    # Caption entities (photos, documents with captions)
    caption_entities = message.caption_entities or []
    for entity in caption_entities:
        if entity.type in _URL_ENTITY_TYPES:
            return True

    # Regex fallback on raw text / caption
    text = message.text or message.caption or ""
    return bool(_LINK_RE.search(text))


# ------------------------------------------------------------------ #
# Anti-Advertisement
# ------------------------------------------------------------------ #

# Phone number pattern (Uzbekistan and common international formats)
_PHONE_RE = re.compile(
    r"(?:\+?998|8)[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|(?:\+\d{1,3}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}",
    re.IGNORECASE,
)

# Ad-trigger keywords (word-boundary matched to reduce false positives)
_AD_KEYWORDS_RE = re.compile(
    r"\b(?:"
    r"sotiladi|sotilayapti|xizmat|aksiya|chegirma|"
    r"zakaz|buyurtma|murojaat|reklama|"
    r"bepul|tekin|arzon|pullik|tarif"
    r")\b",
    re.IGNORECASE,
)

# Minimum ad score to flag a message (keeps false-positive rate low)
_AD_SCORE_THRESHOLD = 2


def is_advertisement(message: Message) -> bool:
    """
    Return True if the message looks like an advertisement.

    Scoring-based approach (threshold = 2) to avoid aggressive filtering:
      +1  phone number present
      +1  ad keyword present
      +1  more than 2 links in message
      +1  inline mention of another channel/group (@username with ad keyword nearby)

    Ordinary chat like "narxi qancha?" scores 0 and is NOT flagged.
    """
    text = (message.text or message.caption or "").strip()
    if not text:
        return False

    score = 0

    # Phone number
    if _PHONE_RE.search(text):
        score += 1

    # Ad keyword
    if _AD_KEYWORDS_RE.search(text):
        score += 1

    # Multiple links (2+)
    entities = list(message.entities or []) + list(message.caption_entities or [])
    link_count = sum(1 for e in entities if e.type in _URL_ENTITY_TYPES)
    if link_count >= 2:
        score += 1

    # Channel mention alongside keyword
    mention_count = sum(1 for e in entities if e.type == MessageEntityType.MENTION)
    if mention_count >= 1 and _AD_KEYWORDS_RE.search(text):
        score += 1

    return score >= _AD_SCORE_THRESHOLD


# ------------------------------------------------------------------ #
# Anti-Repeat  (in-memory per chat/user)
# ------------------------------------------------------------------ #

# How many identical messages trigger the filter
_REPEAT_THRESHOLD = 3
# Window in seconds in which repeats are counted
_REPEAT_WINDOW = 60.0

# (chat_id, user_id) -> deque of (text_hash, timestamp)
_repeat_cache: DefaultDict[
    tuple[int, int], Deque[tuple[int, float]]
] = collections.defaultdict(collections.deque)


def is_repeated_message(
    chat_id: int,
    user_id: int,
    message: Message,
    threshold: int = _REPEAT_THRESHOLD,
) -> bool:
    """
    Return True if the user has sent the same message *threshold* times
    within _REPEAT_WINDOW seconds.
    """
    text = " ".join((message.text or message.caption or "").split()).casefold()
    if not text:
        return False

    # Keep only a bounded digest, never the potentially large message body.
    text_hash = hashlib.sha256(text[:4096].encode("utf-8")).hexdigest()
    now = time.monotonic()
    key = (chat_id, user_id)
    dq = _repeat_cache[key]

    # Evict old entries
    while dq and now - dq[0][1] > _REPEAT_WINDOW:
        dq.popleft()

    # Count same-hash entries
    dq.append((text_hash, now))
    same_count = sum(1 for h, _ in dq if h == text_hash)
    return same_count >= threshold


# ------------------------------------------------------------------ #
# Bad Word Filter
# ------------------------------------------------------------------ #

def contains_bad_word(message: Message, bad_words: list[str]) -> bool:
    """
    Return True if the message text contains any word from *bad_words*.

    Matching is:
      - Case-insensitive
      - Whole-word only (uses \b boundaries) to avoid partial matches
        (e.g. 'class' would not match 'classical')
    """
    if not bad_words:
        return False

    text = (message.text or message.caption or "").lower()
    if not text:
        return False

    for word in bad_words:
        if not word:
            continue
        # Escape special regex chars in the word, then wrap with word boundaries
        pattern = r"\b" + re.escape(word.lower()) + r"\b"
        try:
            if re.search(pattern, text):
                return True
        except re.error:
            # Malformed pattern — skip silently
            continue

    return False


# ------------------------------------------------------------------ #
# Anti-Spam composite check
# ------------------------------------------------------------------ #

def is_spam(
    chat_id: int,
    user_id: int,
    message: Message,
    check_links: bool = True,
    check_ads: bool = True,
    check_repeat: bool = True,
) -> tuple[bool, str]:
    """
    Composite spam check that combines multiple signals.

    Returns (is_spam: bool, reason: str).

    Used when anti_spam is the master toggle and individual sub-feature
    toggles are not separately configured. The middleware uses this
    when it needs a single pass result.

    Note: This does NOT check flood (flood requires time-tracking and
    is handled separately by flood_service).
    """
    if check_repeat and is_repeated_message(chat_id, user_id, message):
        return True, "anti_repeat"

    if check_links and has_link(message):
        return True, "anti_link"

    if check_ads and is_advertisement(message):
        return True, "anti_ads"

    return False, ""
