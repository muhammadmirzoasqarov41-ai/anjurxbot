"""
Member events handler.
Handles new chat members, user status changes, bot addition/removal and promotion in groups.
"""
import logging
import time
from aiogram import Router, Bot, F
from aiogram.types import Message, ChatMemberUpdated

from app.services.group_service import group_service
from app.services.firebase import firebase_service
from app.services.moderation import moderation_service
from app.services.permission_service import permission_service
from app.keyboards.setup import get_setup_wizard_keyboard

logger = logging.getLogger("anjurxbot.member")
router = Router(name="member_router")


@router.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated, bot: Bot):
    """Triggered when bot status changes (added as member, promoted to admin, demoted, removed)."""
    chat = event.chat
    if chat.type not in ("group", "supergroup"):
        return

    new_status = event.new_chat_member.status

    # Invalidate cache for the group
    permission_service.invalidate_group_cache(chat.id)

    if new_status in ("administrator", "creator"):
        # Bot added as admin or promoted to admin
        group_doc = await group_service.get_or_register_group(
            chat.id,
            title=chat.title or "",
            chat=chat,
            bot=bot,
            force_refresh=True
        )
        if event.from_user and not event.from_user.is_bot:
            permission_service._role_cache[(chat.id, event.from_user.id)] = ("ADMIN", time.time())
            if event.from_user.id not in group_doc.get("admin_ids", []):
                group_doc.setdefault("admin_ids", []).append(event.from_user.id)
        try:
            await bot.send_message(
                chat_id=chat.id,
                text="✅ <b>AnjurXBot</b> administrator etib tayinlandi! Barcha himoya filtrlari faollashtirildi.\n\n"
                     "🛡 Himoya sozlamalari: /guard\n"
                     "📢 Majburiy obuna: /fsub\n"
                     "⚙️ Boshqaruv paneli: /panel",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send admin greeting to group {chat.id}: {e}")

    elif new_status == "member":
        # Bot added as regular member
        group_doc = await group_service.get_or_register_group(
            chat.id,
            title=chat.title or "",
            chat=chat,
            bot=bot,
            force_refresh=True
        )
        try:
            await bot.send_message(
                chat_id=chat.id,
                text="👋 Assalomu alaykum! Men <b>AnjurXBot</b>man.\n"
                     "Guruhni xavfsiz va toza saqlashda yordam beraman.\n\n"
                     "To'liq ishlashim uchun menga guruhda <b>Administrator</b> huquqlarini bering va "
                     "/setup buyrug'i orqali tezkor sozlashni bajaring!",
                reply_markup=get_setup_wizard_keyboard(chat.id),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send member greeting to group {chat.id}: {e}")

    elif new_status in ("left", "kicked"):
        # Bot removed from group
        await group_service.mark_group_status(chat.id, is_active=False, bot_status=new_status)
        logger.info(f"BOT REMOVED FROM GROUP chat_id={chat.id} title='{chat.title}' status={new_status}")


@router.chat_member()
async def on_chat_member_updated(event: ChatMemberUpdated, bot: Bot):
    """Triggered when another user is promoted, demoted, leaves, or ownership changes."""
    chat = event.chat
    if chat.type not in ("group", "supergroup"):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    target_user_id = event.new_chat_member.user.id

    # Invalidate cached role of the target user
    permission_service.invalidate_user_cache(chat.id, target_user_id)

    # If an admin or owner changed status, re-sync group administrators in Firestore
    if old_status in ("creator", "administrator") or new_status in ("creator", "administrator"):
        logger.info(
            f"Admin status change detected in chat {chat.id} for user {target_user_id}: "
            f"{old_status} -> {new_status}. Resyncing administrators..."
        )
        await group_service.sync_and_save_administrators(bot, chat.id, chat=chat)


@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot):
    """Triggered when new members or bots join the group via message event."""
    chat_id = message.chat.id
    bot_info = await bot.get_me()

    is_bot_added = any(u.id == bot_info.id for u in message.new_chat_members)
    group_config = await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
        chat=message.chat,
        bot=bot,
        force_refresh=is_bot_added
    )

    for new_user in message.new_chat_members:
        if new_user.id == bot_info.id:
            try:
                await message.reply(
                    f"👋 Assalomu alaykum! Men <b>{bot_info.first_name}</b>man.\n"
                    f"Guruhni xavfsiz va toza saqlashda yordam beraman.\n\n"
                    f"To'liq ishlashim uchun menga guruhda <b>Administrator</b> huquqlarini bering va "
                    f"/setup buyrug'i orqali tezkor sozlashni bajaring!",
                    reply_markup=get_setup_wizard_keyboard(chat_id),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            continue

        # Register human user in database
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
    """Triggered when a member leaves the group via message event."""
    chat_id = message.chat.id
    bot_info = await bot.get_me()

    if message.left_chat_member and message.left_chat_member.id == bot_info.id:
        await group_service.mark_group_status(chat_id, is_active=False, bot_status="left")
        return

    group_config = await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
        chat=message.chat,
        bot=bot
    )

    if group_config.get("guard_settings", {}).get("delete_service_messages", True):
        await moderation_service.delete_message(bot, chat_id, message.message_id)
