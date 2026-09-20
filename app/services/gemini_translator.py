"""
Gemini Translation Service for AnjurX | Rss Bot.
Handles professional journalistic news translation using Google's google-genai SDK,
deterministic Firestore/in-memory caching, strict prompt boundaries, and exponential backoff retry.
"""
import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger("anjurxbot.gemini_translator")

# Try to import Google's official google-genai SDK
try:
    from google import genai
    from google.genai import types
    HAS_GENAI_SDK = True
except ImportError:
    HAS_GENAI_SDK = False

SUPPORTED_POST_LANGUAGES = {"uz", "uz_cyrl", "ru", "en", "auto"}
DEFAULT_POST_LANGUAGE = "uz"

LANGUAGE_NAMES = {
    "uz": "Uzbek (Latin alphabet)",
    "uz_cyrl": "Uzbek using the Uzbek Cyrillic alphabet (Ўзбек тили — кирилл алифбоси)",
    "ru": "Russian (Русский язык)",
    "en": "English",
    "auto": "Original",
}

LANGUAGE_LABELS = {
    "uz": "🇺🇿 O‘zbekcha",
    "uz_cyrl": "🇺🇿 O‘zbekcha — Kirill",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "auto": "🔄 Avtomatik",
}

# Retry backoff schedule for transient errors (seconds)
RETRY_SCHEDULE = [30, 60, 120, 300]


class TranslationNotConfiguredError(Exception):
    """Raised when Gemini translation is requested but GEMINI_API_KEY is not configured."""
    pass


class TranslationTemporaryError(Exception):
    """Raised when Gemini returns a temporary error (rate limit, timeout, 503)."""
    def __init__(self, message: str, retry_after: int = 30):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class TranslatedContent:
    title: str
    description: str
    target_language: str
    is_translated: bool
    model_used: Optional[str] = None
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GeminiTranslator:
    """
    Production-ready news translation engine using Gemini API.
    Features:
    - google-genai SDK with safe fallback
    - Strict news accuracy & formatting preservation prompts
    - In-memory bounded cache + deterministic Firestore document cache (translations/{post_id}_{lang})
    - Zero full-collection scans on Firestore
    - Exponential backoff retry for transient errors
    - Never leaks API keys to logs, UI, or databases
    """

    def __init__(self):
        self._cache: Dict[str, TranslatedContent] = {}
        self._cache_lock = asyncio.Lock()
        self._post_retry_state: Dict[str, Tuple[int, float]] = {}  # key -> (attempt_count, next_retry_timestamp)
        
        # Operational diagnostics
        self.last_success_at: Optional[str] = None
        self.last_error_at: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.total_translated: int = 0
        self.total_cached: int = 0
        self.total_errors: int = 0

    @property
    def model_name(self) -> str:
        """Retrieves configured Gemini translation model from environment variable."""
        return (os.getenv("GEMINI_TRANSLATION_MODEL") or "gemini-flash-latest").strip() or "gemini-flash-latest"

    def _get_candidate_models(self) -> list:
        """Returns ordered list of candidate models for resilience across API tiers."""
        configured = self.model_name
        fallback_models = [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-3.8-flash",
            "gemini-3.5-flash",
            "gemini-pro-latest",
        ]
        models = [configured]
        for m in fallback_models:
            if m not in models:
                models.append(m)
        return models

    def get_api_key(self) -> str:
        """Retrieves API key securely from environment variable without logging or storing it."""
        key = (os.getenv("GEMINI_API_KEY") or "").strip()
        # Ensure it's not a placeholder
        if key.startswith("YOUR_") or "placeholder" in key.lower() or len(key) < 8:
            return ""
        return key

    def is_configured(self) -> bool:
        """Checks if a valid Gemini API key is configured."""
        return bool(self.get_api_key())

    def get_status(self) -> Dict[str, Any]:
        """Provides status and diagnostics without exposing secrets."""
        configured = self.is_configured()
        return {
            "configured": configured,
            "model": self.model_name,
            "cache_enabled": True,
            "sdk_available": HAS_GENAI_SDK,
            "supported_languages": list(SUPPORTED_POST_LANGUAGES),
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "total_translated": self.total_translated,
            "total_cached": self.total_cached,
            "total_errors": self.total_errors,
            "message": "Gemini Translator tayyor" if configured else "Gemini API key sozlanmagan",
        }

    def _get_cache_key(self, post_id: str, target_language: str) -> str:
        return f"{post_id}_{target_language.lower().strip()}"

    async def get_cached(self, post_id: str, target_language: str) -> Optional[TranslatedContent]:
        """
        Two-tier cache lookup:
        1. Fast In-memory bounded cache
        2. Firestore deterministic document: translations/{post_id}_{target_lang}
        NEVER performs full collection scans.
        """
        cache_key = self._get_cache_key(post_id, target_language)

        # 1. In-memory check
        async with self._cache_lock:
            if cache_key in self._cache:
                self.total_cached += 1
                return self._cache[cache_key]

        # 2. Firestore deterministic document check
        try:
            from app.database.firestore import db
            doc_id = cache_key
            fs_data = await db.get_document("translations", doc_id)
            if fs_data and fs_data.get("translated_title"):
                cached_item = TranslatedContent(
                    title=str(fs_data.get("translated_title", "")),
                    description=str(fs_data.get("translated_content", "")),
                    target_language=target_language,
                    is_translated=True,
                    model_used=fs_data.get("model_used", self.model_name),
                    cached=True,
                )
                # Store in memory for sub-millisecond future hits
                async with self._cache_lock:
                    self._cache[cache_key] = cached_item
                self.total_cached += 1
                logger.debug(f"[TRANSLATOR] Cache hit from Firestore for post {post_id} [{target_language}]")
                return cached_item
        except Exception as e:
            # Firestore read failure is non-fatal for caching
            logger.debug(f"[TRANSLATOR] Cache check error: {e}")

        return None

    async def put_cache(self, post_id: str, target_language: str, item: TranslatedContent):
        """
        Persists translation in memory and asynchronously saves deterministic Firestore document.
        """
        cache_key = self._get_cache_key(post_id, target_language)
        now_iso = datetime.utcnow().isoformat()

        # 1. Update in-memory cache with bounding
        async with self._cache_lock:
            if len(self._cache) > 1000:
                # Evict oldest 200 items to prevent memory bloat
                for k in list(self._cache.keys())[:200]:
                    del self._cache[k]
            self._cache[cache_key] = item

        # 2. Write to Firestore deterministic document (translations/{post_id}_{lang})
        try:
            from app.database.firestore import db
            doc_id = cache_key
            fs_data = {
                "post_id": post_id,
                "target_language": target_language,
                "translated_title": item.title,
                "translated_content": item.description,
                "model_used": item.model_used or self.model_name,
                "updated_at": now_iso,
            }
            # Only set created_at on initial insertion
            await db.set_document("translations", doc_id, fs_data, merge=True)
        except Exception as e:
            logger.debug(f"[TRANSLATOR] Failed saving translation cache to Firestore: {e}")

    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
    ) -> str:
        """
        Translates arbitrary text into target_language ('uz', 'ru', 'en').
        If target_language == 'auto' or matches source_language: returns original text.
        """
        if not text or not text.strip():
            return text

        lang = (target_language or DEFAULT_POST_LANGUAGE).lower().strip()
        if lang not in SUPPORTED_POST_LANGUAGES:
            lang = DEFAULT_POST_LANGUAGE

        if lang == "auto" or (source_language and source_language.lower().strip() == lang):
            return text

        api_key = self.get_api_key()
        if not api_key:
            logger.warning("[TRANSLATOR] Gemini translator: API key not configured")
            raise TranslationNotConfiguredError("Gemini translator: API key not configured")

        loop = asyncio.get_running_loop()
        translated_text = await loop.run_in_executor(
            None,
            self._call_gemini_raw_text_sync,
            text,
            lang,
            api_key,
        )
        return translated_text

    async def translate_post(
        self,
        post_id: str,
        title: str,
        description: str,
        target_language: str,
        channel_id: Optional[int] = None,
        source_language: Optional[str] = None,
    ) -> TranslatedContent:
        """
        Translates post title and description according to target_language.
        - target_language == 'auto': returns original immediately without AI call.
        - source_language matches target_language: returns original immediately.
        - checks two-tier cache (memory + Firestore).
        - if not cached, calls Gemini with backoff retry protection.
        """
        lang = (target_language or DEFAULT_POST_LANGUAGE).lower().strip()
        if lang not in SUPPORTED_POST_LANGUAGES:
            lang = DEFAULT_POST_LANGUAGE

        # 1. If 'auto', keep original
        if lang == "auto":
            return TranslatedContent(
                title=title,
                description=description,
                target_language="auto",
                is_translated=False,
            )

        # 2. If source language matches target language, no translation needed
        if source_language and source_language.lower().strip() == lang:
            return TranslatedContent(
                title=title,
                description=description,
                target_language=lang,
                is_translated=False,
            )

        # 3. Check two-tier cache
        cached = await self.get_cached(post_id, lang)
        if cached:
            logger.info(f"[TRANSLATOR] Cache hit for post {post_id} [{lang}]")
            return cached

        # 4. Check if API key is configured
        api_key = self.get_api_key()
        if not api_key:
            logger.warning("[TRANSLATOR] Gemini translator: API key not configured")
            raise TranslationNotConfiguredError("Gemini translator: API key not configured")

        # 5. Check retry backoff for this specific post+lang
        cache_key = self._get_cache_key(post_id, lang)
        now_ts = asyncio.get_event_loop().time()
        attempt_count, next_retry_time = self._post_retry_state.get(cache_key, (0, 0.0))
        if now_ts < next_retry_time:
            wait_sec = int(next_retry_time - now_ts)
            logger.warning(
                f"[TRANSLATOR] Post {post_id} [{lang}] in retry backoff. Will retry after {wait_sec}s"
            )
            raise TranslationTemporaryError(
                f"Translation in retry backoff. Retry after {wait_sec}s",
                retry_after=wait_sec,
            )

        logger.info(f"[TRANSLATOR] Translating post {post_id} to {lang}")

        # 6. Execute translation in executor thread
        loop = asyncio.get_running_loop()
        try:
            translated = await loop.run_in_executor(
                None,
                self._call_gemini_post_sync,
                title,
                description,
                lang,
                api_key,
                post_id,
            )
            # Reset retry backoff on success
            self._post_retry_state.pop(cache_key, None)
            
            # Record diagnostics
            self.last_success_at = datetime.utcnow().isoformat()
            self.total_translated += 1

            # Save to memory and Firestore cache
            await self.put_cache(post_id, lang, translated)
            logger.info(
                f"[TRANSLATOR] Translation successful for post {post_id} [{lang}] using {translated.model_used}"
            )
            return translated

        except Exception as e:
            self.last_error_at = datetime.utcnow().isoformat()
            self.last_error_message = str(e)
            self.total_errors += 1

            # Increment backoff attempt
            next_attempt = attempt_count + 1
            delay_sec = RETRY_SCHEDULE[min(attempt_count, len(RETRY_SCHEDULE) - 1)]
            self._post_retry_state[cache_key] = (next_attempt, now_ts + delay_sec)

            logger.error(
                f"[TRANSLATOR] Translation failed for post {post_id} [{lang}]: {e}. "
                f"Scheduled retry in {delay_sec}s (attempt {next_attempt})."
            )
            raise

    def _build_news_prompt(self, title: str, description: str, target_lang: str) -> str:
        """Constructs a strict, journalistic news translation prompt."""
        if target_lang == "uz_cyrl":
            lang_directive = (
                "Translate this text into Uzbek using the Uzbek Cyrillic alphabet (Ўзбек тили — кирилл алифбоси).\n"
                "CRITICAL ALPHABET INSTRUCTION:\n"
                "- Write EXCLUSIVELY in the Uzbek Cyrillic script (Ўзбек кирилл алифбоси: а, б, в, г, д, е, ё, ж, з, и, й, к, л, м, н, о, п, р, с, т, у, ф, х, ц, ч, ш, ъ, ь, э, ю, я, ў, қ, ғ, ҳ).\n"
                "- Do NOT use the Latin Uzbek alphabet.\n"
            )
        elif target_lang == "uz":
            lang_directive = (
                "Translate the following news headline and summary into Uzbek (using the standard Latin alphabet: O‘zbek tili).\n"
            )
        else:
            target_name = LANGUAGE_NAMES.get(target_lang, "Uzbek")
            lang_directive = f"Translate the following news headline and summary into {target_name}.\n"

        return (
            f"You are a professional, senior journalistic news translator.\n"
            f"{lang_directive}\n"
            "STRICT FACTUAL & PROFESSIONAL RULES:\n"
            "1. ACCURACY: Preserve exact facts, dates, numbers, named entities, people, locations, organizations, and currencies without alteration.\n"
            "2. NO INVENTIONS: Do NOT invent, assume, or add new facts. Do NOT omit existing factual context.\n"
            "3. NO CLICKBAIT: Maintain an objective, professional, matter-of-fact news reporting tone. Avoid hyperbole or sensationalism.\n"
            "4. FORMATTING: Preserve any HTML tags (e.g., <b>, <i>, <code>, <a>) or Telegram formatting exactly as provided.\n"
            "5. NO URL TRANSLATION: Do NOT translate or modify URLs, links, or domain names.\n"
            "6. HASHTAGS & EMOJIS: Preserve original hashtags and emojis intact.\n"
            "7. NO COMMENTARY: Return ONLY the translated content. Do NOT include preambles, conversational filler, or explanations (e.g. do NOT write 'Here is the translation:').\n"
            "8. OUTPUT FORMAT: Return strictly a valid JSON object with exactly two string fields: \"title\" and \"summary\".\n\n"
            f"ORIGINAL HEADLINE:\n{title}\n\n"
            f"ORIGINAL SUMMARY:\n{description or ''}"
        )

    def _call_gemini_post_sync(
        self,
        title: str,
        description: str,
        target_lang: str,
        api_key: str,
        post_id: str,
    ) -> TranslatedContent:
        """
        Synchronous call using official google-genai SDK if available,
        with HTTP REST fallback to ensure resilience.
        """
        prompt = self._build_news_prompt(title, description, target_lang)
        model_name = self.model_name

        # Method 1: Use google-genai SDK
        if HAS_GENAI_SDK:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = response.text or ""
                return self._parse_json_translation(raw_text, title, description, target_lang, model_name)
            except Exception as sdk_err:
                err_str = str(sdk_err).lower()
                # If authentication or quota error, re-raise directly
                if any(x in err_str for x in ["api_key_invalid", "permission_denied", "unauthenticated", "401", "403"]):
                    raise RuntimeError(f"Gemini authentication failed: {sdk_err}")
                if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                    raise TranslationTemporaryError(f"Gemini quota exceeded: {sdk_err}", retry_after=60)
                logger.warning(f"[TRANSLATOR] SDK call failed with {sdk_err}. Falling back to REST API...")

        # Method 2: REST API fallback
        return self._call_gemini_rest_api_sync(prompt, title, description, target_lang, api_key, model_name)

    def _call_gemini_rest_api_sync(
        self,
        prompt: str,
        title: str,
        description: str,
        target_lang: str,
        api_key: str,
        preferred_model: str,
    ) -> TranslatedContent:
        """Direct HTTPS REST call to Gemini endpoint with candidate model fallback."""
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        candidate_models = self._get_candidate_models()
        last_err: Optional[Exception] = None

        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        continue

                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if not content_parts:
                        continue

                    raw_text = content_parts[0].get("text", "").strip()
                    return self._parse_json_translation(raw_text, title, description, target_lang, model_name)

            except urllib.error.HTTPError as he:
                last_err = he
                if he.code in (401, 403):
                    raise RuntimeError(f"Gemini authentication error HTTP {he.code}")
                if he.code in (404, 429, 503):
                    # Try next candidate model before giving up
                    logger.debug(f"[TRANSLATOR] Model {model_name} returned {he.code}, trying fallback candidate...")
                    continue
                raise RuntimeError(f"Gemini HTTP error {he.code}: {he.reason}")
            except Exception as e:
                last_err = e
                continue

        if last_err:
            if isinstance(last_err, urllib.error.HTTPError) and last_err.code == 429:
                raise TranslationTemporaryError("Gemini quota limit exceeded HTTP 429 across candidate models", retry_after=60)
            raise last_err
        raise RuntimeError("No candidate Gemini model succeeded")

    def _parse_json_translation(
        self,
        raw_text: str,
        original_title: str,
        original_desc: str,
        target_lang: str,
        model_name: str,
    ) -> TranslatedContent:
        """Parses and sanitizes Gemini JSON output."""
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            parsed = json.loads(clean_text)
            trans_title = str(parsed.get("title") or original_title).strip()
            trans_desc = str(parsed.get("summary") or original_desc).strip()
            
            # Guard against empty translation
            if not trans_title:
                trans_title = original_title

            return TranslatedContent(
                title=trans_title,
                description=trans_desc,
                target_language=target_lang,
                is_translated=True,
                model_used=model_name,
            )
        except Exception as json_err:
            logger.warning(f"[TRANSLATOR] JSON decode error: {json_err}. Raw text: {raw_text[:100]}")
            # If valid text was returned but not formatted as JSON, treat raw text as translation if reasonable
            if clean_text and not clean_text.startswith("{"):
                return TranslatedContent(
                    title=clean_text[:120],
                    description=clean_text,
                    target_language=target_lang,
                    is_translated=True,
                    model_used=model_name,
                )
            raise ValueError(f"Malformed translation response from Gemini: {json_err}")

    def _call_gemini_raw_text_sync(
        self,
        text: str,
        target_lang: str,
        api_key: str,
    ) -> str:
        """Translates arbitrary single text block."""
        if target_lang == "uz_cyrl":
            lang_directive = (
                "Translate this text into Uzbek using the Uzbek Cyrillic alphabet (Ўзбек тили — кирилл алифбоси).\n"
                "CRITICAL: Write EXCLUSIVELY in the Uzbek Cyrillic alphabet. Do NOT use the Latin alphabet."
            )
        elif target_lang == "uz":
            lang_directive = "Translate the following text into Uzbek (using the standard Latin alphabet)."
        else:
            target_name = LANGUAGE_NAMES.get(target_lang, "Uzbek")
            lang_directive = f"Translate the following text into {target_name}."

        prompt = (
            f"You are a professional journalistic translator.\n"
            f"{lang_directive}\n"
            "STRICT RULES:\n"
            "- Preserve exact facts, numbers, dates, named entities, and currencies.\n"
            "- Do NOT alter meaning, do NOT add or omit facts.\n"
            "- Preserve HTML tags, URLs, hashtags, and emojis.\n"
            "- Return ONLY the translated text without commentary or preamble.\n\n"
            f"TEXT TO TRANSLATE:\n{text}"
        )
        model_name = self.model_name

        if HAS_GENAI_SDK:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2),
                )
                if response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"[TRANSLATOR] SDK call failed for raw text: {e}")

        # REST fallback
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        candidate_models = self._get_candidate_models()

        for candidate_model in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "").strip()
            except Exception as e:
                logger.debug(f"[TRANSLATOR] Raw text fallback model {candidate_model} failed: {e}")
                continue

        return text


# Global singleton instance
gemini_translator = GeminiTranslator()
