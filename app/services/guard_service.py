"""
Guard Evaluation Service.
Combines anti-spam, anti-flood, anti-link, anti-ads, and bad words rules.
"""
from typing import Dict, Any, Tuple
from aiogram import Bot
from aiogram.types import Message

from app.services.permission_service import permission_service
from app.services.flood_service import flood_service
from app.services.spam_service import spam_service
from app.services.punishment_service import punishment_service
from app.services.stats_service import stats_service


class GuardService:
    async def process_message(self, bot: Bot, message: Message, group_config: Dict[str, Any]) -> bool:
        """
        Processes an incoming group message against guard rules.
        Returns True if a violation was found and handled (should stop propagation).
        """
        if not message.chat or not message.from_user or message.from_user.is_bot:
            return False

        chat_id = message.chat.id
        user_id = message.from_user.id
        sender_chat_id = message.sender_chat.id if message.sender_chat else None

        # 1. Administrators and Group Owners bypass all guards
        if group_config.get("owner_id") == user_id:
            return False

        is_admin = await permission_service.is_user_admin(bot, chat_id, user_id, sender_chat_id=sender_chat_id)
        if is_admin:
            return False

        settings = group_config.get("guard_settings", {})
        text = message.text or message.caption or ""

        # 2. Check Flood
        if settings.get("anti_flood", True):
            limit = settings.get("flood_limit", 5)
            window = float(settings.get("flood_window", 5))
            if flood_service.check_flood(chat_id, user_id, limit=limit, window=window):
                await stats_service.record_event("flood_stopped")
                await punishment_service.apply_violation(
                    bot=bot,
                    message=message,
                    group_settings=settings,
                    violation_type="flood",
                    reason="Juda tez-tez xabar yozish (Flood)",
                )
                return True

        # 3. Check Links
        if settings.get("anti_link", True) and spam_service.contains_link(text):
            await stats_service.record_event("links_deleted")
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="link",
                reason="Guruhda havola (link) yuborish taqiqlangan",
            )
            return True

        # 4. Check Advertisements (Ads)
        if settings.get("anti_ads", True) and spam_service.contains_ads(text):
            await stats_service.record_event("spam_blocked")
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="ads",
                reason="Reklama xabari tarqatish taqiqlangan",
            )
            return True

        # 5. Check Bad Words / Profanity
        if settings.get("bad_words_filter", True):
            bad_words = settings.get("bad_words", [])
            if spam_service.contains_bad_words(text, bad_words):
                await stats_service.record_event("bad_words_blocked")
                await punishment_service.apply_violation(
                    bot=bot,
                    message=message,
                    group_settings=settings,
                    violation_type="bad_word",
                    reason="Haqoratli yoki taqiqlangan so'z ishlatildi",
                )
                return True

        # 6. Check Repeated Text Spam
        if settings.get("anti_repeat", True) and spam_service.is_excessive_repeated_text(text):
            await punishment_service.apply_violation(
                bot=bot,
                message=message,
                group_settings=settings,
                violation_type="repeat_spam",
                reason="Bir xil belgilarni takrorlab spam qilish",
            )
            return True

        return False


guard_service = GuardService()
