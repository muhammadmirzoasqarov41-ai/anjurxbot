"""
Gemini Translation Service Bridge for AnjurX | Rss Bot.
Unified delegate to app.services.gemini_translator.
Ensures 100% backward compatibility with all existing imports while using
the modernized google-genai SDK, deterministic Firestore caching, and news prompts.
"""
from app.services.gemini_translator import (
    GeminiTranslator,
    gemini_translator,
    TranslatedContent,
    TranslationNotConfiguredError,
    TranslationTemporaryError,
    SUPPORTED_POST_LANGUAGES,
    DEFAULT_POST_LANGUAGE,
    LANGUAGE_LABELS,
    LANGUAGE_NAMES,
)

# Compatibility aliases
GeminiTranslationService = GeminiTranslator
gemini_translation = gemini_translator

__all__ = [
    "GeminiTranslationService",
    "gemini_translation",
    "gemini_translator",
    "TranslatedContent",
    "TranslationNotConfiguredError",
    "TranslationTemporaryError",
    "SUPPORTED_POST_LANGUAGES",
    "DEFAULT_POST_LANGUAGE",
    "LANGUAGE_LABELS",
    "LANGUAGE_NAMES",
]
