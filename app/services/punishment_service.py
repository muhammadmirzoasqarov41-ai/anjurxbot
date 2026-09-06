"""
Punishment Orchestration Service.
Coordinates warnings, deletions, mutes, kicks, bans, and audit logging.
"""
import logging
from typing import Dict, Any, Optional
from aiogram import Bot
from aiogram.types import Message

from app.services.moderation import moderation_service
from app.services.warning import warning_service
from app.services.firebase import firebase_service
from app.services.stats_service import stats_service
from app.services.log_service import log_service

logger = logging.getLogger("anjurxbot.punishment")


class PunishmentService:
    async def apply_violation(
        self,
        bot: Bot,
        message: Message,
        group_settings: Dict[str, Any],
        violation_type: str,
        reason: str
    ) -> None:
        """
        Deletes the violating message, increments warnings, notifies user,
        and applies punishment if warn threshold is reached.
        """
        chat_id = message.chat.id
        user = message.from_user
        if not user:
            return

        user_id = user.id
        user_name = user.first_name or "Foydalanuvchi"
        warn_limit = group_settings.get("warn_limit", 3)
        punishment_type = group_settings.get("punishment", "mute").lower()

        # 1. Delete the violating message immediately
        await moderation_service.delete_message(bot, chat_id, message.message_id)
        await stats_service.record_event("messages_checked")

        # 2. Add warning
        new_count, reached = warning_service.add_warning(chat_id, user_id, warn_limit)
        await stats_service.record_event("warnings_issued")

        # 3. Log event
        log_service.log_moderation(chat_id, user_id, violation_type, reason)
        await firebase_service.log_moderation_event(
            chat_id, user_id, violation_type, reason, {"warn_count": new_count, "limit": warn_limit}
        )

        # 4. Check if limit reached
        if reached:
            if punishment_type == "mute":
                duration = 900  # 15 minutes
                await moderation_service.mute_user(bot, chat_id, user_id, duration)
                await stats_service.record_event("users_muted")
                notify_text = (
                    f"🚫 <b>Jazo qo'llanildi:</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni ({warn_limit}/{warn_limit}) to'ldi.\n"
                    f"Guruhda yozish 15 daqiqaga cheklandi."
                )
            elif punishment_type == "kick":
                await moderation_service.kick_user(bot, chat_id, user_id)
                notify_text = (
                    f"👞 <b>Guruhdan chiqarildi:</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni to'ldi."
                )
            elif punishment_type == "ban":
                await moderation_service.ban_user(bot, chat_id, user_id)
                notify_text = (
                    f"🔨 <b>Guruhdan bloklandi:</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni to'ldi."
                )
            else:
                notify_text = f"⚠️ {user_name} ogohlantirishlar chegarasiga yetdi."
        else:
            notify_text = (
                f"⚠️ <b>Ogohlantirish:</b> {user_name}\n"
                f"Sabab: {reason}\n"
                f"Ogohlantirishlar: <b>{new_count}/{warn_limit}</b>"
            )

        try:
            sent_msg = await bot.send_message(chat_id=chat_id, text=notify_text, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Could not send punishment notification in {chat_id}: {e}")


punishment_service = PunishmentService()
