"""
Destination Channels & Telegram Source Channel Handlers for AnjurX | Rss Bot.
Handles:
- my_chat_member: Automatic bot admin status detection and posting permission verification
- channel_post: Real-time Telegram channel aggregation and clean copyMessage delivery
- Channel connection wizard and destination management
"""
import logging
from typing import Optional
from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, ADMINISTRATOR, KICKED, LEFT
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.config import config
from app.services.permission_service import permission_service, is_super_admin
from app.services.rss_storage import rss_storage
from app.keyboards.rss import (
    get_connect_channel_guide_keyboard,
    get_main_menu_keyboard,
    get_cancel_keyboard,
)
from app.states.rss import ConnectChannelState

logger = logging.getLogger("anjurxbot.channels")
router = Router(name="channels_router")


# --------------------------------------------------------------------------
# 1. Automatic Bot Admin & Permission Detection (my_chat_member)
# --------------------------------------------------------------------------
@router.my_chat_member()
async def on_my_chat_member_updated(event: ChatMemberUpdated, bot: Bot):
    """
    Triggers automatically when the bot is added to a channel/group or its permissions change.
    Verifies 'can_post_messages' permission and notifies the user who promoted the bot.
    """
    chat = event.chat
    new_member = event.new_chat_member
    from_user = event.from_user

    # Only process channels and supergroups/groups
    if chat.type not in ("channel", "supergroup", "group"):
        return

    is_admin = new_member.status in ("administrator", "creator")
    can_post = False

    if is_admin:
        if chat.type == "channel":
            # For channels, can_post_messages is critical
            can_post = getattr(new_member, "can_post_messages", False) is True
        else:
            can_post = True

        # Save or update destination in storage
        await rss_storage.save_destination(
            chat_id=chat.id,
            title=chat.title or f"Chat {chat.id}",
            username=chat.username,
            chat_type=chat.type,
            can_post=can_post,
            added_by=from_user.id if from_user else 0,
        )

        logger.info(
            f"Bot status updated in {chat.type} '{chat.title}' ({chat.id}): "
            f"is_admin={is_admin}, can_post={can_post}, by={from_user.id if from_user else 0}"
        )

        # Notify the user who added the bot in their private chat
        if from_user and from_user.id > 0:
            try:
                if can_post:
                    notify_text = (
                        "✅ <b>Kanal muvaffaqiyatli ulandi!</b>\n\n"
                        f"📢 <b>{chat.title}</b>\n\n"
                        "Endi ushbu kanalga saytlar (RSS) yoki boshqa Telegram kanallardan "
                        "postlarni avtomatik yetkazishingiz mumkin."
                    )
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(text="🌐 Sayt/RSS qo‘shish", callback_data="menu_add_rss"),
                                InlineKeyboardButton(text="📢 Telegram kanal qo‘shish", callback_data="menu_add_tg_source"),
                            ],
                            [
                                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
                            ],
                        ]
                    )
                else:
                    notify_text = (
                        "❌ <b>Bot kanalda post yubora olmaydi.</b>\n\n"
                        f"📢 <b>{chat.title}</b>\n\n"
                        "Botni kanalga administrator qilib qo‘shing va <b>Post Messages</b> "
                        "(Xabarlar yozish) huquqini yoqing."
                    )
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(text="🔄 Qayta tekshirish", callback_data="refresh_channels"),
                                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
                            ]
                        ]
                    )
                await bot.send_message(
                    chat_id=from_user.id,
                    text=notify_text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.debug(f"Could not send private notification to user {from_user.id}: {e}")

    elif new_member.status in ("left", "kicked"):
        # Bot was removed from channel
        await rss_storage.save_destination(
            chat_id=chat.id,
            title=chat.title or f"Chat {chat.id}",
            username=chat.username,
            chat_type=chat.type,
            can_post=False,
            added_by=from_user.id if from_user else 0,
        )
        logger.info(f"Bot was removed from {chat.type} '{chat.title}' ({chat.id})")


# --------------------------------------------------------------------------
# 2. Telegram Channel Post Aggregation & Clean Copy (channel_post)
# --------------------------------------------------------------------------
@router.channel_post()
async def on_channel_post(message: Message, bot: Bot):
    """
    Listens to new posts in Telegram channels where the bot is present.
    If the channel is registered as a source, copies the post to all linked destination channels
    using copyMessage to guarantee NO 'Forwarded from' attribution or author headers.
    """
    source_chat_id = message.chat.id
    source_title = message.chat.title or f"Kanal {source_chat_id}"
    msg_id = message.message_id

    # Look up sources configured for this source channel
    sources = await rss_storage.get_sources_by_telegram_chat_id(source_chat_id)
    if not sources:
        return

    logger.info(f"Processing new channel_post msg_id={msg_id} from source '{source_title}' ({source_chat_id})")

    # Deliver to each connected destination channel
    for source in sources:
        for dest_id in source.destinations:
            # 1. Duplicate check (O(1))
            if await rss_storage.is_post_delivered(str(source_chat_id), msg_id, dest_id):
                logger.debug(f"Skipping duplicate post {msg_id} to destination {dest_id}")
                continue

            # 2. Check destination channel permissions
            dest_item = await rss_storage.get_destination(dest_id)
            dest_title = dest_item.title if dest_item else f"Chat {dest_id}"

            try:
                # 3. Clean copy of the message without forward headers
                copied = await bot.copy_message(
                    chat_id=dest_id,
                    from_chat_id=source_chat_id,
                    message_id=msg_id,
                )

                # 4. Record successful delivery for persistent duplicate protection
                caption = message.caption or message.text or f"Post #{msg_id}"
                first_line = caption.strip().split("\n")[0][:80]
                post_link = f"https://t.me/{message.chat.username}/{msg_id}" if message.chat.username else ""

                await rss_storage.record_channel_delivery(
                    source_id=str(source_chat_id),
                    source_title=source_title,
                    message_id=msg_id,
                    destination_id=dest_id,
                    destination_title=dest_title,
                    title=first_line,
                    link=post_link,
                )
                logger.info(f"Copied post {msg_id} from '{source_title}' -> '{dest_title}' ({dest_id})")

            except (TelegramForbiddenError, TelegramBadRequest) as te:
                err_str = str(te).lower()
                logger.error(
                    f"Could not deliver post {msg_id} to destination {dest_id} ({dest_title}): {te}"
                )
                # If bot lacks post permission, record it
                if "post" in err_str or "admin" in err_str or "forbidden" in err_str:
                    logger.warning(f"Bot lacks post permissions in destination {dest_id}")
                    if dest_item:
                        dest_item.can_post = False
                        await rss_storage.save_destination(
                            chat_id=dest_item.chat_id,
                            title=dest_item.title,
                            username=dest_item.username,
                            chat_type=dest_item.type,
                            can_post=False,
                            added_by=dest_item.added_by,
                        )
            except Exception as ex:
                logger.error(f"Unexpected error copying post {msg_id} to {dest_id}: {ex}")


# --------------------------------------------------------------------------
# 3. Destination Channels Wizard & Management UI
# --------------------------------------------------------------------------
@router.callback_query(F.data == "menu_connect_channel")
async def cb_connect_channel_menu(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Shows channel connection guide and list of currently connected channels."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    destinations = await rss_storage.get_destinations_for_user(user_id)

    text_parts = [
        "📢 <b>Kanal ulash bo‘limi</b>\n\n",
        "Bot yangiliklarni avtomatik yetkazishi uchun uni Telegram kanalingizga bog‘lang.\n\n",
        "<b>Qanday ulanadi:</b>\n",
        "1. Botni kanalingizga <b>Administrator</b> qilib qo‘shing;\n",
        "2. <b>Post Messages</b> (Xabarlar yozish) huquqini yoqing;\n",
        "3. Bot kanalni avtomatik ravishda taniydi va ushbu ro‘yxatga qo‘shadi!\n\n",
    ]

    if destinations:
        text_parts.append("📋 <b>Sizning ulangan kanallaringiz:</b>\n")
        for d in destinations:
            icon = "📢" if d.type == "channel" else "👥"
            status = "✅ Faol (Post yuborish ochiq)" if d.can_post else "❌ Bot kanalda post yubora olmaydi"
            user_part = f" (@{d.username})" if d.username else ""
            text_parts.append(f"• {icon} <b>{d.title}</b>{user_part}\n   Holat: {status}\n")
    else:
        text_parts.append("<i>Sizda hali ulangan kanallar mavjud emas.</i>\n")

    keyboard = get_connect_channel_guide_keyboard(bot_username)
    try:
        await callback.message.edit_text(
            "".join(text_parts),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer(
            "".join(text_parts),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data == "refresh_channels")
async def cb_refresh_channels(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Refreshes and checks permissions for user's connected destination channels."""
    user_id = callback.from_user.id if callback.from_user else 0
    destinations = await rss_storage.get_destinations_for_user(user_id)

    # Re-verify permissions for each channel
    for d in destinations:
        if d.chat_id < 0:
            perm_check = await permission_service.check_bot_channel_permissions(bot, d.chat_id)
            if perm_check.get("can_post") != d.can_post or perm_check.get("title") != d.title:
                await rss_storage.save_destination(
                    chat_id=d.chat_id,
                    title=perm_check.get("title") or d.title,
                    username=perm_check.get("username") or d.username,
                    chat_type=perm_check.get("type") or d.type,
                    can_post=perm_check.get("can_post", False),
                    added_by=d.added_by,
                )

    await cb_connect_channel_menu(callback, bot, state)
