"""
Telegram Moderation Actions Service.
Safely handles message deletion, user muting, kicking, and banning.
"""
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Bot
from aiogram.types import ChatPermissions
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger("anjurxbot.moderation")


class ModerationService:
    async def delete_message(self, bot: Bot, chat_id: int, message_id: int) -> bool:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.debug(f"Could not delete message {message_id} in {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=delete_message chat_id={chat_id}")
            return False

    async def mute_user(
        self,
        bot: Bot,
        chat_id: int,
        user_id: int,
        duration_seconds: int = 900
    ) -> bool:
        """Restricts a user from sending messages for duration_seconds (default 15 mins)."""
        try:
            until_date = datetime.now() + timedelta(seconds=duration_seconds)
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
                until_date=until_date,
            )
            return True
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.warning(f"Could not mute user {user_id} in {chat_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=mute_user chat_id={chat_id} user_id={user_id}")
            return False

    async def unmute_user(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """Restores standard chatting permissions to a user."""
        try:
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions,
            )
            return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=unmute_user chat_id={chat_id} user_id={user_id}")
            return False

    async def kick_user(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """Kicks user by banning and immediately unbanning."""
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
            return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=kick_user chat_id={chat_id} user_id={user_id}")
            return False

    async def ban_user(self, bot: Bot, chat_id: int, user_id: int) -> bool:
        """Bans user from group permanently."""
        try:
            await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=ban_user chat_id={chat_id} user_id={user_id}")
            return False


moderation_service = ModerationService()
