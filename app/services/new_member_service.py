"""
New Member Management Service.
Handles welcoming, clean service message removal, and spam bot protection on join.
"""
import logging
from typing import Optional
from aiogram import Bot
from aiogram.types import Message, User
from app.services.moderation import moderation_service

logger = logging.getLogger("anjurxbot.new_member")


class NewMemberService:
    async def handle_new_chat_members(self, bot: Bot, message: Message) -> None:
        """Process new members joined to the group."""
        if not message.new_chat_members or not message.chat:
            return

        chat_id = message.chat.id

        # Delete 'user joined' service message to keep group clean
        await moderation_service.delete_message(bot, chat_id, message.message_id)

        for member in message.new_chat_members:
            # If the added member is a bot (and not us), check restrictions or log
            if member.is_bot and member.id != bot.id:
                logger.info(f"Bot {member.id} was added to group {chat_id}")
            else:
                first_name = member.first_name or "Foydalanuvchi"
                logger.info(f"New member {member.id} ({first_name}) joined group {chat_id}")

    async def handle_left_chat_member(self, bot: Bot, message: Message) -> None:
        """Clean service message when someone leaves."""
        if not message.left_chat_member or not message.chat:
            return
        await moderation_service.delete_message(bot, message.chat.id, message.message_id)


new_member_service = NewMemberService()
