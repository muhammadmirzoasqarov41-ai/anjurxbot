"""
New Member Management and Probation Service.
Handles welcoming, service message removal, join tracking,
and new-member probation protection.
"""
import time
import logging
from typing import Dict, Tuple, Optional
from aiogram import Bot
from aiogram.types import Message
from app.services.moderation import moderation_service
from app.services.raid_service import raid_service

logger = logging.getLogger("anjurxbot.new_member")


class NewMemberService:
    def __init__(self):
        # (chat_id, user_id) -> join timestamp
        self._join_times: Dict[Tuple[int, int], float] = {}

    def record_join(self, chat_id: int, user_id: int) -> None:
        self._join_times[(chat_id, user_id)] = time.time()

    def is_in_probation(self, chat_id: int, user_id: int, duration_seconds: int = 300) -> bool:
        """Returns True if the user joined less than duration_seconds ago."""
        join_ts = self._join_times.get((chat_id, user_id))
        if not join_ts:
            return False
        return (time.time() - join_ts) < duration_seconds

    async def handle_new_chat_members(self, bot: Bot, message: Message, group_config: Optional[dict] = None) -> None:
        """Process new members joined to the group."""
        if not message.new_chat_members or not message.chat:
            return

        chat_id = message.chat.id
        guard_settings = (group_config or {}).get("guard_settings", {})
        delete_service = guard_settings.get("delete_service_messages", True)
        raid_protection = guard_settings.get("raid_protection", True)
        raid_thresh = guard_settings.get("raid_threshold", 10)

        # 1. Clean service message if enabled
        if delete_service:
            await moderation_service.delete_message(bot, chat_id, message.message_id)

        # 2. Record joins and test for raid
        for member in message.new_chat_members:
            if member.id == bot.id:
                continue

            self.record_join(chat_id, member.id)

            if raid_protection:
                raid_triggered = raid_service.record_join(
                    chat_id=chat_id,
                    user_id=member.id,
                    window=30.0,
                    threshold=raid_thresh,
                    cooldown_duration=300.0
                )
                if raid_triggered:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=(
                                "🚨 <b>RAID OGOHLANTIRISHI!</b>\n\n"
                                "Guruhga qisqa vaqt ichida ko‘plab a'zolar qo‘shildi.\n"
                                "Guruh xavfsizligini ta'minlash uchun vaqtinchalik <b>Qat'iy Himoya</b> faollashtirildi!\n"
                                "<i>Yangi a'zolarning havolalari va spam xabarlari qat'iy bloklanadi.</i>"
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.debug(f"Could not send raid alert in {chat_id}: {e}")

    async def handle_left_chat_member(self, bot: Bot, message: Message, group_config: Optional[dict] = None) -> None:
        """Clean service message when someone leaves."""
        if not message.left_chat_member or not message.chat:
            return

        guard_settings = (group_config or {}).get("guard_settings", {})
        delete_service = guard_settings.get("delete_service_messages", True)
        if delete_service:
            await moderation_service.delete_message(bot, message.chat.id, message.message_id)


new_member_service = NewMemberService()
