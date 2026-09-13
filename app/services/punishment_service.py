"""
Punishment Orchestration Service for AnjurXBot Qorovul.
Coordinates severity-based escalations (LOW, MEDIUM, HIGH, CRITICAL),
warnings, deletions, mutes, kicks, bans, audit logging, and group-level Firebase stats.
"""
import logging
from typing import Dict, Any, Optional
from aiogram import Bot
from aiogram.types import Message

from app.services.moderation import moderation_service
from app.services.warning import warning_service
from app.services.firebase import firebase_service
from app.services.stats_service import stats_service
from app.services.group_service import group_service
from app.services.log_service import log_service

logger = logging.getLogger("anjurxbot.punishment")


class PunishmentService:
    async def apply_violation(
        self,
        bot: Bot,
        message: Message,
        group_settings: Dict[str, Any],
        violation_type: str,
        reason: str,
        severity: str = "MEDIUM",
        custom_duration: Optional[int] = None
    ) -> None:
        """
        Processes a violation according to its severity level:
        - LOW: Delete message, non-intrusive warning
        - MEDIUM: Delete message, issue warning, punish when threshold is reached
        - HIGH: Delete message, direct temporary mute
        - CRITICAL: Delete message, direct ban or long mute
        """
        if not message.chat or not message.from_user:
            return

        chat_id = message.chat.id
        user = message.from_user
        user_id = user.id
        user_name = (user.first_name or "Foydalanuvchi").replace("<", "&lt;").replace(">", "&gt;")
        warn_limit = group_settings.get("warn_limit", 3)
        punishment_type = group_settings.get("punishment", "mute").lower()
        default_mute_dur = group_settings.get("mute_duration", 900)

        # 1. Delete the violating message immediately
        await moderation_service.delete_message(bot, chat_id, message.message_id)
        await stats_service.record_event("messages_checked")

        # Increment specific group metric in Firebase
        stat_key_map = {
            "link": "link",
            "spam": "spam",
            "ads": "ads",
            "flood": "flood",
            "bad_word": "spam",
            "repeat_spam": "spam",
            "raid": "spam",
        }
        mapped_stat = stat_key_map.get(violation_type, "spam")
        await group_service.increment_group_stat(chat_id, mapped_stat)

        # 2. Handle HIGH severity directly (e.g. excessive flood, repeat spam)
        if severity == "HIGH":
            duration = custom_duration or default_mute_dur
            await moderation_service.mute_user(bot, chat_id, user_id, duration)
            await stats_service.record_event("users_muted")
            await group_service.increment_group_stat(chat_id, "mute")

            mins = max(1, duration // 60)
            notify_text = (
                f"🔇 <b>Ovoz o‘chirildi (Mute):</b> {user_name}\n"
                f"Sabab: {reason}\n"
                f"Muddat: <b>{mins} daqiqa</b>"
            )
            log_service.log_moderation(chat_id, user_id, violation_type, f"HIGH severity mute: {reason}")
            await firebase_service.log_moderation_event(
                chat_id, user_id, violation_type, reason, {"action": "mute", "duration": duration, "severity": "HIGH"}
            )
            try:
                await bot.send_message(chat_id=chat_id, text=notify_text, parse_mode="HTML")
            except Exception as e:
                logger.debug(f"Could not send mute notification in {chat_id}: {e}")
            return

        # 3. Handle CRITICAL severity directly (e.g. coordinated raid attack)
        if severity == "CRITICAL":
            await moderation_service.ban_user(bot, chat_id, user_id)
            await group_service.increment_group_stat(chat_id, "ban")
            notify_text = (
                f"🔨 <b>Guruhdan chetlatildi (Ban):</b> {user_name}\n"
                f"Sabab: {reason}"
            )
            log_service.log_moderation(chat_id, user_id, violation_type, f"CRITICAL ban: {reason}")
            await firebase_service.log_moderation_event(
                chat_id, user_id, violation_type, reason, {"action": "ban", "severity": "CRITICAL"}
            )
            try:
                await bot.send_message(chat_id=chat_id, text=notify_text, parse_mode="HTML")
            except Exception as e:
                logger.debug(f"Could not send ban notification in {chat_id}: {e}")
            return

        # 4. Handle LOW severity (clean deletion with optional soft notice)
        if severity == "LOW":
            log_service.log_moderation(chat_id, user_id, violation_type, reason)
            await firebase_service.log_moderation_event(
                chat_id, user_id, violation_type, reason, {"action": "delete", "severity": "LOW"}
            )
            return

        # 5. Handle MEDIUM severity (standard warning escalation)
        new_count, reached = warning_service.add_warning(chat_id, user_id, warn_limit)
        await stats_service.record_event("warnings_issued")
        await group_service.increment_group_stat(chat_id, "warn")

        log_service.log_moderation(chat_id, user_id, violation_type, reason)
        await firebase_service.log_moderation_event(
            chat_id, user_id, violation_type, reason, {"warn_count": new_count, "limit": warn_limit}
        )

        if reached:
            if punishment_type == "mute":
                duration = default_mute_dur
                await moderation_service.mute_user(bot, chat_id, user_id, duration)
                await stats_service.record_event("users_muted")
                await group_service.increment_group_stat(chat_id, "mute")
                mins = max(1, duration // 60)
                notify_text = (
                    f"🚫 <b>Jazo qo‘llanildi:</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni ({warn_limit}/{warn_limit}) to‘ldi.\n"
                    f"Guruhda yozish <b>{mins} daqiqaga</b> cheklandi (Mute)."
                )
            elif punishment_type == "kick":
                await moderation_service.kick_user(bot, chat_id, user_id)
                notify_text = (
                    f"👞 <b>Guruhdan chiqarildi:</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni ({warn_limit}/{warn_limit}) to‘ldi."
                )
            elif punishment_type == "ban":
                await moderation_service.ban_user(bot, chat_id, user_id)
                await group_service.increment_group_stat(chat_id, "ban")
                notify_text = (
                    f"🔨 <b>Guruhdan chetlatildi (Ban):</b> {user_name}\n"
                    f"Sabab: {reason}\n"
                    f"Ogohlantirishlar soni to‘ldi."
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
            await bot.send_message(chat_id=chat_id, text=notify_text, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Could not send punishment notification in {chat_id}: {e}")


punishment_service = PunishmentService()
