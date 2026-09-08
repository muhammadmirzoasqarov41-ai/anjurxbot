"""
Spam, Links, Ads, and Bad Words Detection Service.
"""
import re
from typing import List, Optional

# Regular expressions for link and username detection
LINK_REGEX = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+)",
    re.IGNORECASE,
)
TELEGRAM_HANDLE_REGEX = re.compile(r"(?<!\w)@([a-zA-Z0-9_]{4,32})")

# Common spam / advertisement keywords
ADS_KEYWORDS = [
    "pul ishlash", "daromad", "investitsiya", "kripto", "bitcoin",
    "referal", "bonus", "aksiya", "chegirma", "obuna bo'ling",
    "kanalga a'zo", "100% kafolat", "kurs sotiladi", "reklama"
]


class SpamService:
    def contains_link(self, text: str) -> bool:
        if not text:
            return False
        if LINK_REGEX.search(text):
            return True
        if TELEGRAM_HANDLE_REGEX.search(text):
            return True
        return False

    def contains_ads(self, text: str) -> bool:
        if not text:
            return False
        lower = text.lower()
        for kw in ADS_KEYWORDS:
            if kw in lower:
                return True
        return False

    def contains_bad_words(self, text: str, bad_words: List[str]) -> bool:
        if not text or not bad_words:
            return False
        # Normalize text: keep alphanumeric and spaces
        cleaned = re.sub(r"[^\w\s]", "", text.lower())
        # Collapse elongated characters (e.g. jalaaaap -> jalap, fuuuuck -> fuck)
        collapsed = re.sub(r"(.)\1{2,}", r"\1", cleaned)
        collapsed_double = re.sub(r"(.)\1{2,}", r"\1\1", cleaned)

        words = set(cleaned.split()) | set(collapsed.split()) | set(collapsed_double.split())
        for bw in bad_words:
            bw_clean = bw.strip().lower()
            if not bw_clean:
                continue
            if bw_clean in words:
                return True
            # Substring check for bad words with length >= 4
            if len(bw_clean) >= 4 and (bw_clean in cleaned or bw_clean in collapsed or bw_clean in collapsed_double):
                return True
        return False

    def is_excessive_repeated_text(self, text: str) -> bool:
        if not text:
            return False
        # Repeated same character > 15 times (e.g. aaaaaaaaaaaaaa)
        if re.search(r"(.)\1{14,}", text):
            return True
        return False


spam_service = SpamService()
