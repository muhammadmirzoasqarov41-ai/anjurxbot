"""
Gemini Translation Service for AnjurX | Rss Bot.
Handles professional news translation with Gemini AI models, in-memory caching,
fallbacks, and strict prompt guidelines.
"""
import os
import json
import logging
import asyncio
import urllib.request
import urllib.error
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger("anjurxbot.gemini_translation")

SUPPORTED_POST_LANGUAGES = {"uz", "ru", "en", "auto"}
DEFAULT_POST_LANGUAGE = "uz"

LANGUAGE_LABELS = {
    "uz": "🇺🇿 O‘zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
    "auto": "🔄 Avtomatik",
}

# Preferred models in priority order
CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]


@dataclass
class TranslatedContent:
    title: str
    description: str
    target_language: str
    is_translated: bool
    model_used: Optional[str] = None


class GeminiTranslationService:
    """
    Translates news title and summary for Telegram channels using Gemini API.
    Provides memory cache (post_id:target_language) to avoid redundant AI calls.
    """

    def __init__(self):
        self._cache: Dict[str, TranslatedContent] = {}
        self._cache_lock = asyncio.Lock()

    def get_api_key(self) -> str:
        """Retrieves Gemini API key from environment without hardcoding or logging it."""
        return (os.getenv("GEMINI_API_KEY") or "").strip()

    def _get_cache_key(self, post_id: str, target_language: str) -> str:
        return f"{post_id}:{target_language}"

    async def get_cached(self, post_id: str, target_language: str) -> Optional[TranslatedContent]:
        async with self._cache_lock:
            return self._cache.get(self._get_cache_key(post_id, target_language))

    async def put_cache(self, post_id: str, target_language: str, item: TranslatedContent):
        async with self._cache_lock:
            # Keep cache bounded to 1000 items
            if len(self._cache) > 1000:
                # Remove oldest keys
                for k in list(self._cache.keys())[:200]:
                    del self._cache[k]
            self._cache[self._get_cache_key(post_id, target_language)] = item

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
        - target_language == 'auto': returns original immediately, no translation.
        - target_language matches source_language (e.g. en == en): returns original immediately.
        - otherwise: checks cache, or invokes Gemini API.
        """
        lang = (target_language or DEFAULT_POST_LANGUAGE).lower()
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

        # 2. If source language matches target language (e.g. en == en, or uz == uz), no translation needed
        if source_language and source_language.lower().strip() == lang:
            return TranslatedContent(
                title=title,
                description=description,
                target_language=lang,
                is_translated=False,
            )

        # 3. Check cache
        cached = await self.get_cached(post_id, lang)
        if cached:
            return cached

        # 4. Perform translation via Gemini API
        api_key = self.get_api_key()
        if not api_key:
            err_msg = "GEMINI_API_KEY environment variable is not configured"
            logger.error(
                f"translation_failed channel_id={channel_id} post_id={post_id} target_language={lang} error={err_msg}"
            )
            raise RuntimeError(err_msg)

        # Run synchronous HTTP request in thread pool
        loop = asyncio.get_running_loop()
        try:
            translated = await loop.run_in_executor(
                None,
                self._call_gemini_api_sync,
                title,
                description,
                lang,
                api_key,
                post_id,
                channel_id,
            )
            await self.put_cache(post_id, lang, translated)
            return translated
        except Exception as e:
            logger.error(
                f"translation_failed channel_id={channel_id} post_id={post_id} target_language={lang} error={str(e)}"
            )
            raise

    def _call_gemini_api_sync(
        self,
        title: str,
        description: str,
        target_lang: str,
        api_key: str,
        post_id: str,
        channel_id: Optional[int],
    ) -> TranslatedContent:
        """Synchronous HTTP call to Gemini API with model fallback."""
        target_lang_name = {
            "uz": "Uzbek (O'zbek tili)",
            "ru": "Russian (Русский язык)",
            "en": "English",
        }.get(target_lang, "Uzbek")

        prompt = (
            f"You are a professional news translator. Translate the following news headline and summary into {target_lang_name}.\n\n"
            "STRICT RULES:\n"
            "- Preserve exact facts, dates, numbers, named entities, organizations, and currencies.\n"
            "- Do NOT alter the core meaning or invent new details.\n"
            "- Keep URLs, links, and hashtags untranslated and intact.\n"
            "- Produce natural, fluent journalistic news style for headlines and summaries in the target language.\n"
            "- Do NOT include conversational preambles, meta comments, or explanations (e.g., do NOT write 'Here is the translation:').\n"
            "- Keep the summary concise and suitable for Telegram news posts.\n"
            "- Return strictly a valid JSON object with exactly two string fields: \"title\" and \"summary\".\n\n"
            f"ORIGINAL HEADLINE:\n{title}\n\n"
            f"ORIGINAL SUMMARY:\n{description or ''}"
        )

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

        last_error: Optional[Exception] = None

        for model_name in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            req = urllib.request.Request(
                url,
                data=payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini returned empty candidates")

                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if not content_parts:
                        raise ValueError("Gemini returned empty parts")

                    raw_text = content_parts[0].get("text", "").strip()

                    # Parse JSON output
                    try:
                        parsed_json = json.loads(raw_text)
                    except json.JSONDecodeError:
                        # Fallback if markdown blocks were returned
                        clean_text = raw_text
                        if clean_text.startswith("```json"):
                            clean_text = clean_text[7:]
                        if clean_text.startswith("```"):
                            clean_text = clean_text[3:]
                        if clean_text.endswith("```"):
                            clean_text = clean_text[:-3]
                        parsed_json = json.loads(clean_text.strip())

                    trans_title = str(parsed_json.get("title") or title).strip()
                    trans_summary = str(parsed_json.get("summary") or description).strip()

                    return TranslatedContent(
                        title=trans_title,
                        description=trans_summary,
                        target_language=target_lang,
                        is_translated=True,
                        model_used=model_name,
                    )
            except urllib.error.HTTPError as he:
                error_body = ""
                try:
                    error_body = he.read().decode("utf-8")[:200]
                except Exception:
                    pass
                # If 503 or 429 or 404, try next candidate model
                logger.warning(
                    f"Gemini model {model_name} HTTP {he.code}: {error_body}. Trying fallback..."
                )
                last_error = he
                continue
            except Exception as e:
                logger.warning(f"Gemini model {model_name} failed: {e}. Trying fallback...")
                last_error = e
                continue

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")


gemini_translation = GeminiTranslationService()
