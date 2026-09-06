"""
Member events handler.
Handles new chat members (welcome messages, delete join/left system notifications),
and bot being added to new groups.
"""
from aiogram import Router, Bot, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, KICKED, LEFT, RESTRICTED, ADMINISTRATOR

from app.services.group_service import group_service
from app.services.firebase import firebase_service
from app.services.moderation import moderation_service
from app.services.permission_service import permission_service
from app.keyboards.setup import get_setup_wizard_keyboard

router = Router(name="member_router")


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    chat_id = message.chat.id
    group_config = await group_service.get_or_register_group(chat_id, message.chat.title or "")

    bot_info = await bot.get_me()

    for new_user in message.new_chat_members:
        # Check if bot itself was added
        if new_user.id == bot_info.id:
            await message.reply(
                f"👋 Assalomu alaykum! Men <b>{bot_info.first_name}</b>man.\n"
                f"Guruhni xavfsiz va toza saqlashda yordam beraman.\n\n"
                f"To'liq ishlashim uchun menga guruhda <b>Administrator</b> huquqlarini bering va "
                f"/setup buyrug'i orqali tezkor sozlashni bajaring!",
                reply_markup=get_setup_wizard_keyboard(chat_id),
                parse_mode="HTML"
            )
            continue

        # Register user in database
        await firebase_service.save_or_update_user(
            user_id=new_user.id,
            user_data={
                "username": new_user.username,
                "first_name": new_user.first_name,
                "last_name": new_user.last_name,
                "is_bot": new_user.is_bot,
            }
        )

        # Check delete service message setting
        if group_config.get("guard_settings", {}).get("delete_service_messages", True):
            await moderation_service.delete_message(bot, chat_id, message.message_id)


@router.message(F.left_chat_member)
async def on_left_chat_member(message: Message, bot: Bot):
    chat_id = message.chat.id
    group_config = await group_service.get_or_register_group(chat_id, message.chat.title or "")

    if group_config.get("guard_settings", {}).get("delete_service_messages", True):
        await moderation_service.delete_message(bot, chat_id, message.message_id)


@router.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated, bot: Bot):
    """Triggered when bot admin status changes or bot is removed from chat."""
    chat = event.chat
    new_status = event.new_chat_member.status

    # Invalidate permission cache
    permission_service.invalidate_group_cache(chat.id)

    if new_status in ("administrator", "creator"):
        await group_service.get_or_register_group(chat.id, chat.title or "")
        try:
            await bot.send_message(
                chat_id=chat.id,
                text="✅ <b>AnjurXBot</b> administrator etib tayinlandi! Barcha himoya filtrlari faollashtirildi.\n"
                     "Sozlamalar paneli: /panel\nHimoya filtrlari: /guard\nMajburiy obuna: /fsub",
                parse_mode="HTML"
            )
        except Exception:
            pass
