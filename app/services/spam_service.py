"""
Spam, Links, Ads, and Bad Words Detection Service for AnjurXBot Qorovul.
Equipped with multi-signal advertising scoring, MessageEntity link extraction,
domain whitelisting, Cyrillic-Latin homoglyph fuzzy profanity filtering,
and cross-user duplicate spam detection.
"""
import re
import time
import unicodedata
from typing import List, Optional, Set, Tuple, Dict
from aiogram.types import Message, MessageEntity

# Regex for URL detection
URL_REGEX = re.compile(
    r"(https?://[^\s/$.?#].[^\s]*|www\.[^\s/$.?#].[^\s]*|t\.me/[^\s]+|telegram\.me/[^\s]+|telegram\.dog/[^\s]+)",
    re.IGNORECASE,
)

# Telegram invite links
INVITE_LINK_REGEX = re.compile(
    r"(t\.me/(\+|joinchat/)[a-zA-Z0-9_\-]+|telegram\.me/(\+|joinchat/)[a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)

# Telegram @handle regex
TELEGRAM_HANDLE_REGEX = re.compile(r"(?<!\w)@([a-zA-Z0-9_]{4,32})")

# Phone number regex (Uzbekistan & international formats)
PHONE_REGEX = re.compile(
    r"(\+?998[\s\-]?)?(9[0-9]|88|33|77|55)[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}\b"
    r"|(\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"
)

# Commercial / Ad keywords with weights
COMMERCIAL_KEYWORDS = [
    ("sotiladi", 1.5), ("sotamiz", 1.5), ("narxi", 1.2), ("narx", 1.0),
    ("zakaz", 1.5), ("buyurtma", 1.5), ("aksiya", 1.5), ("chegirma", 1.5),
    ("dostavka", 1.5), ("yetkazib berish", 1.5), ("optom", 1.5),
    ("kurs", 1.2), ("kurslarimiz", 1.5), ("kurs sotiladi", 2.0),
    ("murojaat uchun", 1.5), ("lichka", 1.2), ("dm ga", 1.5),
    ("admin ga yozing", 1.8), ("adminga", 1.2), ("bog'lanish", 1.2),
]

PROMO_FINANCE_KEYWORDS = [
    ("pul ishlash", 2.5), ("daromad", 2.0), ("investitsiya", 2.0),
    ("kripto", 2.0), ("bitcoin", 2.0), ("referal", 2.5), ("bonus", 1.8),
    ("100% kafolat", 2.5), ("obuna bo'ling", 2.0), ("kanalga a'zo", 2.2),
    ("kanalimizga", 1.5), ("gruppamizga", 1.5), ("kanal linki", 2.0),
    ("reklama", 1.5), ("prays", 1.5), ("reklama narxi", 2.0),
]

CTA_KEYWORDS = [
    ("bosing", 1.0), ("ulaning", 1.2), ("kirib ko'ring", 1.2),
    ("start bosing", 2.0), ("ko'rish uchun", 1.0), ("obuna", 1.2),
]

# Homoglyphs mapping: Cyrillic to Latin equivalents
HOMOGLYPHS: Dict[str, str] = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'x', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh', 'ъ': '',
    'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Common accented/lookalike latin letters
    'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'é': 'e', 'è': 'e', 'ë': 'e',
    'ê': 'e', 'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i', 'ó': 'o', 'ò': 'o',
    'ö': 'o', 'ô': 'o', 'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u', 'ñ': 'n',
    'ç': 'c',
}

# Leetspeak mappings
LEETSPEAK: Dict[str, str] = {
    '0': 'o', '1': 'i', '3': 'e', '4': 'a', '@': 'a', '$': 's', '7': 't',
    '8': 'b', '5': 's', '!': 'i',
}

# Default allowed domains
DEFAULT_ALLOWED_DOMAINS = [
    "youtube.com", "youtu.be", "instagram.com", "github.com",
    "google.com", "wikipedia.org", "t.me/c/",
]


class SpamService:
    def __init__(self):
        # Tracking recent messages for duplicate detection
        # (chat_id, user_id) -> list of (message_hash, timestamp)
        self._user_msg_history: Dict[Tuple[int, int], List[Tuple[int, float]]] = {}
        # chat_id -> list of (message_hash, user_id, timestamp)
        self._chat_cross_user_history: Dict[int, List[Tuple[int, int, float]]] = {}

    def extract_urls(self, message: Message) -> List[str]:
        """Extract all URLs from text, caption, and MessageEntity objects."""
        urls = []
        text = message.text or message.caption or ""

        # 1. Extract from MessageEntity if available
        entities = (message.entities or []) + (message.caption_entities or [])
        for ent in entities:
            if ent.type == "url":
                extracted = text[ent.offset : ent.offset + ent.length]
                if extracted:
                    urls.append(extracted)
            elif ent.type == "text_link" and ent.url:
                urls.append(ent.url)

        # 2. Extract from regex
        for m in URL_REGEX.finditer(text):
            found = m.group(0)
            if found and found not in urls:
                urls.append(found)

        return urls

    def contains_link(
        self,
        message: Message,
        allowed_domains: Optional[List[str]] = None,
        block_telegram_handles: bool = True
    ) -> bool:
        """
        Detects unauthorized links in a message.
        Ignores links matching allowed domains.
        """
        text = message.text or message.caption or ""
        if not text:
            return False

        allowed = allowed_domains or DEFAULT_ALLOWED_DOMAINS
        urls = self.extract_urls(message)

        for url in urls:
            url_clean = url.lower().strip()
            # Check if url belongs to any allowed domain
            is_allowed = False
            for domain in allowed:
                d = domain.lower().strip()
                if d and (d in url_clean):
                    is_allowed = True
                    break
            if not is_allowed:
                return True

        # Telegram invite links are always strictly evaluated
        if INVITE_LINK_REGEX.search(text):
            return True

        # Handle mentions if enabled
        if block_telegram_handles and TELEGRAM_HANDLE_REGEX.search(text):
            # Check if this handle is a link entity
            return True

        return False

    def is_telegram_invite_link(self, text: str) -> bool:
        """Returns True if the message contains a Telegram group/channel invite link."""
        if not text:
            return False
        return bool(INVITE_LINK_REGEX.search(text))

    def evaluate_ads_score(self, message: Message) -> float:
        """
        Evaluates advertisement signals with a multi-signal scoring system.
        Returns a confidence score.
        A score >= 3.0 indicates high-confidence advertisement.
        """
        text = (message.text or message.caption or "").lower()
        if not text:
            return 0.0

        score = 0.0

        # Signal 1: Links or @handles (+1.5 - 2.0)
        has_url = bool(self.extract_urls(message))
        has_handle = bool(TELEGRAM_HANDLE_REGEX.search(text))
        if has_url:
            score += 2.0
        elif has_handle:
            score += 1.2

        # Signal 2: Phone number (+2.0)
        if PHONE_REGEX.search(text):
            score += 2.0

        # Signal 3: Commercial keywords
        for word, weight in COMMERCIAL_KEYWORDS:
            if word in text:
                score += weight
                break  # avoid stacking multiple commercial keywords in same category

        # Signal 4: Promo / Finance / Obuna keywords
        for word, weight in PROMO_FINANCE_KEYWORDS:
            if word in text:
                score += weight
                break

        # Signal 5: Call to action
        for word, weight in CTA_KEYWORDS:
            if word in text:
                score += weight
                break

        return score

    def contains_ads(self, message: Message, threshold: float = 3.0) -> bool:
        """
        Returns True if multi-signal ad score exceeds threshold.
        Prevents false positives on lone keywords in ordinary conversation.
        """
        return self.evaluate_ads_score(message) >= threshold

    def normalize_text_for_bad_words(self, text: str) -> str:
        """
        Deep normalization:
        - Lowercase & Unicode NFKD
        - Homoglyphs (Cyrillic -> Latin)
        - Leetspeak numbers -> letters
        - Remove non-alphabetic separators (dots, underscores, dashes, spaces)
        - Collapse elongated letters (e.g. jallllaaap -> jalap)
        """
        if not text:
            return ""

        # Normalize unicode
        text = unicodedata.normalize('NFKD', text.lower())

        # Homoglyphs replacement
        chars = []
        for ch in text:
            chars.append(HOMOGLYPHS.get(ch, ch))
        norm = "".join(chars)

        # Leetspeak replacement
        leet_chars = []
        for ch in norm:
            leet_chars.append(LEETSPEAK.get(ch, ch))
        norm = "".join(leet_chars)

        return norm

    def contains_bad_words(
        self,
        text: str,
        bad_words: List[str],
        whitelist: Optional[List[str]] = None
    ) -> bool:
        """
        Fuzzy bad words detector resilient to character spacing,
        symbols, leetspeak, and Cyrillic/Latin substitutions.
        """
        if not text or not bad_words:
            return False

        # Whitelist check
        if whitelist:
            for wl in whitelist:
                wl_clean = wl.strip().lower()
                if wl_clean and wl_clean in text.lower():
                    return False

        norm = self.normalize_text_for_bad_words(text)
        # Stripped of all non-alphabetics
        no_separators = re.sub(r"[^a-z]", "", norm)
        # Collapsed repetitions (e.g. jalaaaap -> jalap)
        collapsed = re.sub(r"(.)\1{2,}", r"\1", no_separators)
        collapsed_double = re.sub(r"(.)\1{2,}", r"\1\1", no_separators)

        # Tokenized words with spaces
        spaced_tokens = set(re.findall(r"[a-z]+", norm))

        for bw in bad_words:
            bw_norm = self.normalize_text_for_bad_words(bw.strip())
            bw_clean = re.sub(r"[^a-z]", "", bw_norm)
            if not bw_clean:
                continue

            # Exact token match
            if bw_clean in spaced_tokens:
                return True

            # Substring match if bad word length is at least 4 letters
            if len(bw_clean) >= 4:
                if (bw_clean in no_separators or
                    bw_clean in collapsed or
                    bw_clean in collapsed_double):
                    return True

        return False

    def is_excessive_repeated_text(self, text: str) -> bool:
        """Detects single character repeated excessively (e.g. aaaaaaaaaaaaaa)."""
        if not text:
            return False
        return bool(re.search(r"(.)\1{14,}", text))

    def is_excessive_mentions(self, message: Message, limit: int = 5) -> bool:
        """Detects messages with too many mentions in a single message."""
        text = message.text or message.caption or ""
        entities = (message.entities or []) + (message.caption_entities or [])
        mention_entities = sum(1 for e in entities if e.type in ("mention", "text_mention"))
        regex_mentions = len(TELEGRAM_HANDLE_REGEX.findall(text))
        return max(mention_entities, regex_mentions) >= limit

    def is_excessive_emojis(self, text: str, limit: int = 15) -> bool:
        """Detects messages with excessive emoji count."""
        if not text:
            return False
        # Simple emoji range matcher
        emoji_count = len(re.findall(
            r"[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]",
            text
        ))
        return emoji_count >= limit

    def check_user_duplicate(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        window: float = 60.0,
        max_repeats: int = 3
    ) -> bool:
        """
        Tracks if the same user repeats the exact same message >= max_repeats within window.
        """
        if not text or len(text.strip()) < 3:
            return False

        now = time.time()
        msg_hash = hash(text.strip().lower())
        key = (chat_id, user_id)

        history = self._user_msg_history.get(key, [])
        fresh = [(h, t) for (h, t) in history if now - t <= window]
        fresh.append((msg_hash, now))
        self._user_msg_history[key] = fresh

        repeats = sum(1 for (h, t) in fresh if h == msg_hash)
        return repeats >= max_repeats

    def check_cross_user_duplicate_spam(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        window: float = 30.0,
        unique_users_threshold: int = 3
    ) -> bool:
        """
        Detects coordinated bot-net spam: multiple distinct users
        sending the identical text within `window` seconds.
        """
        if not text or len(text.strip()) < 10:
            return False

        now = time.time()
        msg_hash = hash(text.strip().lower())

        history = self._chat_cross_user_history.get(chat_id, [])
        fresh = [(h, u, t) for (h, u, t) in history if now - t <= window]
        fresh.append((msg_hash, user_id, now))
        self._chat_cross_user_history[chat_id] = fresh

        # Count distinct users with same message hash
        senders = {u for (h, u, t) in fresh if h == msg_hash}
        return len(senders) >= unique_users_threshold


spam_service = SpamService()
