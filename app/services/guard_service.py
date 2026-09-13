"""
Guard Evaluation Service for AnjurXBot Qorovul.
Coordinates smart protection severity levels (LOW, MEDIUM, HIGH, CRITICAL),
anti-flood, anti-link with allowed domains, multi-signal ad detection,
fuzzy bad word filtering, cross-user duplicate raid detection, and new member probation.
"""
import logging
from typing import Dict, Any, Optional
from aiogram import Bot
from aiogram.types import Message

from app.services.permission_service import permission_service
from app.services.flood_service import flood_service
from app.services.spam_service import spam_service
from app.services.punishment_service import punishment_service
from app.services.stats_service import stats_service
from app.services.raid_service import raid_service
from app.services.new_member_service import new_member_service

logger = logging.getLogger("anjurxbot.guard")


class GuardService:
    async def process_message(self, bot: Bot, message: Message, group_config: Dict[str, Any]) -> bool:
        """
        Processes an incoming group message against all active Qorovul guard rules.
        Returns True if a violation was found and handled (stopping propagation).
        """
        if not message.chat or not message.from_user or message.from_user.is_bot:
            return False

        chat_id = message.chat.id
        user_id = message.from_user.id
        sender_chat_id = message.sender_chat.id if message.sender_chat else None

        # 1. Administrators and Group Owners bypass all guards unconditionally
        if group_config.get("owner_id") == user_id:
            return False

        is_admin = await permission_service.is_user_admin(bot, chat_id, user_id, sender_chat_id=sender_chat_id)
        if is_admin:
            return False

        settings = group_config.get("guard_settings", {})
        text = message.text or message.caption or ""

        # Check if group is currently under active raid mitigation
        is_raid = raid_service.is_raid_active(chat_id)
        # Check if user is in new member probation
        new_member_probation = False
        if settings.get("new_member_protection", True):
            probation_duration = settings.get("new_member_duration", 300)
            new_member_probation = new_member_service.is_in_probation(chat_id, user_id, probation_duration)

        # 2. Check Anti-Flood (Smart sliding window)
        if settings.get("anti_flood", True):
            base_limit = settings.get("flood_limit", 5)
            # Under raid or probation, tighten flood limit
            effective_limit = 2 if is_raid else base_limit
            window = float(settings.get("flood_window", 5))

            if flood_service.check_flood(chat_id, user_id, limit=effective_limit, window=window):
                await stats_service.record_event("flood_stopped")
                # Heavy flood triggers HIGH severity (mute)
                await punishment_service.apply_violation(
                    bot=bot,
                    message=message,
                    group_settings=settings,
                    violation_type="flood",
                    reason="Juda ko‘p xabar yuborish (Flood)",
                    severity="HIGH",
                )
                return True

        # 3. Check Coordinated Cross-User Raid Spam
        if spam_service.check_cross_user_duplicate_spam(chat_id, user_id, text):
            await stats_service.record_event("spam_blocked")
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="repeat_spam",
                reason="Guruhga bir xil xabarlar bilan uyushgan spam hujumi",
                severity="HIGH",
            )
            return True

        # 4. Check Single-User Duplicate Message Spam
        if settings.get("anti_repeat", True) and spam_service.check_user_duplicate(chat_id, user_id, text):
            await stats_service.record_event("spam_blocked")
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="repeat_spam",
                reason="Bir xil xabarni qayta-qayta yuborish (Takroriy spam)",
                severity="HIGH",
            )
            return True

        # 5. Check Links
        if settings.get("anti_link", True):
            allowed_domains = settings.get("allowed_domains", [])
            if spam_service.contains_link(message, allowed_domains=allowed_domains):
                await stats_service.record_event("links_deleted")
                is_invite = spam_service.is_telegram_invite_link(text)
                severity = "HIGH" if (is_invite and (new_member_probation or is_raid)) else "MEDIUM"
                await punishment_service.apply_violation(
                    bot=bot,
                    message=message,
                    group_settings=settings,
                    violation_type="link",
                    reason="Guruhda havola (link) yuborish taqiqlangan",
                    severity=severity,
                )
                return True

        # 6. Check Advertisements (Ads) with multi-signal confidence scoring
        if settings.get("anti_ads", True) and spam_service.contains_ads(message):
            await stats_service.record_event("spam_blocked")
            severity = "HIGH" if (new_member_probation or is_raid) else "MEDIUM"
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="ads",
                reason="Reklama yoki tijoriy xabar tarqatish taqiqlangan",
                severity=severity,
            )
            return True

        # 7. Check Bad Words / Profanity with fuzzy matching
        if settings.get("bad_words_filter", True):
            bad_words = settings.get("bad_words", [])
            whitelist = settings.get("whitelist_words", [])
            if spam_service.contains_bad_words(text, bad_words, whitelist=whitelist):
                await stats_service.record_event("bad_words_blocked")
                action_pref = settings.get("bad_words_action", "delete")
                if action_pref == "mute":
                    severity = "HIGH"
                elif action_pref == "warn":
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                await punishment_service.apply_violation(
                    bot=bot,
                    message=message,
                    group_settings=settings,
                    violation_type="bad_word",
                    reason="Haqoratli yoki taqiqlangan so‘z ishlatildi",
                    severity=severity,
                )
                return True

        # 8. Check Excessive Mentions
        if spam_service.is_excessive_mentions(message, limit=5):
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="spam",
                reason="Bir xabarda juda ko‘p odamni belgilash (@mention)",
                severity="MEDIUM",
            )
            return True

        # 9. Check Excessive Emoji Spam
        if spam_service.is_excessive_emojis(text, limit=15):
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="spam",
                reason="Haddan ortiq ko‘p emojilar yuborish",
                severity="MEDIUM",
            )
            return True

        # 10. Check Repeated Character Text Spam (e.g. aaaaaaaaaaaaaa)
        if settings.get("anti_repeat", True) and spam_service.is_excessive_repeated_text(text):
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="repeat_spam",
                reason="Bir xil belgilarni takrorlab yuborish",
                severity="MEDIUM",
            )
            return True

        return False


guard_service = GuardService()
