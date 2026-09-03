"""
Force Subscribe admin commands.

All /fsub* and /addchannel / /delchannel / /channels commands live here.

Access control:
  - Telegram group admins/creators can use these commands inside the group.
  - Global bot admins (ADMIN_IDS in .env) can use them anywhere.

Commands implemented:
  /fsub         — show current fsub status for this group
  /fsub_on      — enable force subscribe
  /fsub_off     — disable force subscribe
  /addchannel   — interactive: ask for channel username/ID and add it
  /delchannel   — show list of channels with inline remove buttons
  /channels     — list all configured channels
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.services import group_service, subscription_service
from app.utils.logger import logger

router = Router(name="fsub_admin")

# ------------------------------------------------------------------ #
# FSM states for /addchannel interactive flow
# ------------------------------------------------------------------ #


class AddChannelStates(StatesGroup):
    waiting_for_channel = State()


# ------------------------------------------------------------------ #
# Guards
# ------------------------------------------------------------------ #

_GROUP_TYPES = {"group", "supergroup"}


async def _is_authorized(message: Message) -> bool:
    """
    Return True if the message sender is allowed to use admin commands.

    Allowed:
      - Global bot admins (ADMIN_IDS in .env) in any chat.
      - Group admins / creators in their own group.
    """
    if message.from_user is None:
        return False

    user_id = message.from_user.id

    # Global bot admin — always allowed
    if settings.is_admin(user_id):
        return True

    # Group admin check (only in group chats)
    if message.chat.type in _GROUP_TYPES:
        bot = message.bot  # type: ignore[union-attr]
        status = await subscription_service.get_member_status(
            bot, message.chat.id, user_id
        )
        if status in ("administrator", "creator"):
            return True

    return False


async def _require_group(message: Message) -> bool:
    """Return True if the command is used inside a group/supergroup."""
    if message.chat.type not in _GROUP_TYPES:
        await message.answer(
            "⚠️ Bu buyruq faqat guruh ichida ishlaydi.\n"
            "Botni guruhga qo'shib, u yerda ishlating."
        )
        return False
    return True


# ------------------------------------------------------------------ #
# /fsub — show status
# ------------------------------------------------------------------ #


@router.message(Command("fsub"))
async def cmd_fsub_status(message: Message) -> None:
    """Show the current force subscribe status for this group."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    try:
        fsub = await group_service.get_fsub_settings(chat_id)
    except Exception as exc:
        logger.error("Error fetching fsub for %s: %s", chat_id, exc)
        await message.answer("❌ Ma'lumotlarni olishda xatolik yuz berdi.")
        return

    enabled = fsub.get("enabled", False)
    channels: list[dict] = fsub.get("channels", [])

    status_text = "✅ Yoqilgan" if enabled else "❌ O'chirilgan"
    unknown = "Noma'lum"
    ch_lines = "\n".join(
        f"  • {ch.get('title') or unknown} ({ch.get('username') or ch['channel_id']})"
        for ch in channels
    ) or "  (hech qanday kanal qo'shilmagan)"

    await message.answer(
        f"🛡 <b>Majburiy obuna holati</b>\n\n"
        f"Holat: {status_text}\n"
        f"Kanallar:\n{ch_lines}\n\n"
        f"Yoqish: /fsub_on\n"
        f"O'chirish: /fsub_off\n"
        f"Kanal qo'shish: /addchannel\n"
        f"Kanal o'chirish: /delchannel",
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
# /fsub_on — enable
# ------------------------------------------------------------------ #


@router.message(Command("fsub_on"))
async def cmd_fsub_on(message: Message) -> None:
    """Enable force subscribe for this group."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id

    # Warn if no channels configured
    channels = await group_service.get_channels(chat_id)
    if not channels:
        await message.answer(
            "⚠️ Hech qanday kanal qo'shilmagan.\n\n"
            "Avval /addchannel orqali kanal qo'shing, so'ng yoqing."
        )
        return

    try:
        await group_service.set_fsub_enabled(chat_id, enabled=True)
    except Exception as exc:
        logger.error("Error enabling fsub for %s: %s", chat_id, exc)
        await message.answer("❌ Yoqishda xatolik yuz berdi.")
        return

    await message.answer(
        "✅ Majburiy obuna <b>yoqildi</b>.\n\n"
        f"Kanallar soni: {len(channels)} ta",
        parse_mode="HTML",
    )
    logger.info("Force subscribe enabled for group %s by user %s.", chat_id, message.from_user.id)  # type: ignore


# ------------------------------------------------------------------ #
# /fsub_off — disable
# ------------------------------------------------------------------ #


@router.message(Command("fsub_off"))
async def cmd_fsub_off(message: Message) -> None:
    """Disable force subscribe for this group."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    try:
        await group_service.set_fsub_enabled(chat_id, enabled=False)
    except Exception as exc:
        logger.error("Error disabling fsub for %s: %s", chat_id, exc)
        await message.answer("❌ O'chirishda xatolik yuz berdi.")
        return

    await message.answer(
        "❌ Majburiy obuna <b>o'chirildi</b>.\n\n"
        "Yana yoqish uchun: /fsub_on",
        parse_mode="HTML",
    )
    logger.info("Force subscribe disabled for group %s by user %s.", chat_id, message.from_user.id)  # type: ignore


# ------------------------------------------------------------------ #
# /channels — list
# ------------------------------------------------------------------ #


@router.message(Command("channels"))
async def cmd_channels(message: Message) -> None:
    """List all configured force-subscribe channels for this group."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    try:
        channels = await group_service.get_channels(chat_id)
    except Exception as exc:
        logger.error("Error fetching channels for %s: %s", chat_id, exc)
        await message.answer("❌ Ma'lumotlarni olishda xatolik yuz berdi.")
        return

    if not channels:
        await message.answer(
            "📭 Hech qanday majburiy kanal qo'shilmagan.\n\n"
            "Kanal qo'shish uchun: /addchannel"
        )
        return

    lines = [f"📢 <b>Majburiy kanallar</b> ({len(channels)} ta):\n"]
    for i, ch in enumerate(channels, 1):
        title = ch.get("title") or "Noma'lum"
        username = ch.get("username") or ""
        ch_id = ch["channel_id"]
        display = username if username else str(ch_id)
        lines.append(f"{i}. {title} — <code>{display}</code>")

    lines.append("\nKanal o'chirish: /delchannel")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ------------------------------------------------------------------ #
# /addchannel — interactive flow
# ------------------------------------------------------------------ #


@router.message(Command("addchannel"))
async def cmd_addchannel_start(message: Message, state: FSMContext) -> None:
    """Start the interactive add-channel flow."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    await state.set_state(AddChannelStates.waiting_for_channel)
    await state.update_data(group_id=message.chat.id)

    await message.answer(
        "📢 <b>Majburiy kanalni qo'shamiz.</b>\n\n"
        "Kanal username yoki ID sini yuboring.\n\n"
        "Masalan:\n"
        "<code>@mychannel</code>\n"
        "<code>-1001234567890</code>\n\n"
        "Bekor qilish: /cancel",
        parse_mode="HTML",
    )


@router.message(Command("cancel"), AddChannelStates.waiting_for_channel)
async def cmd_addchannel_cancel(message: Message, state: FSMContext) -> None:
    """Cancel the add-channel flow."""
    await state.clear()
    await message.answer("❌ Bekor qilindi.")


@router.message(AddChannelStates.waiting_for_channel)
async def cmd_addchannel_receive(message: Message, state: FSMContext) -> None:
    """
    Receive the channel username/ID from the admin, validate it, and save.
    """
    if message.text is None:
        await message.answer("⚠️ Iltimos, kanal username yoki ID sini matn ko'rinishida yuboring.")
        return

    raw = message.text.strip()
    bot = message.bot  # type: ignore[union-attr]
    state_data = await state.get_data()
    group_id: int = state_data["group_id"]

    # ---- Resolve channel ----
    channel_id, channel_info = await _resolve_channel(bot, raw)

    if channel_id is None:
        await message.answer(
            "❌ Kanal topilmadi yoki botga ushbu kanalga kirish huquqi yo'q.\n\n"
            "Iltimos, botni kanalga <b>admin</b> qilib qo'ying va qaytadan urinib ko'ring.\n\n"
            "Bekor qilish: /cancel",
            parse_mode="HTML",
        )
        return

    # ---- Check bot has getChatMember permission ----
    permission_ok = await _verify_bot_channel_access(bot, channel_id)
    if not permission_ok:
        await message.answer(
            "⚠️ Bot kanalda a'zolik tekshirishga ruxsati yo'q.\n\n"
            "Botni kanalga <b>administrator</b> qilib qo'ying va qaytadan urinib ko'ring.\n\n"
            "Kerakli ruxsatlar:\n"
            "• A'zolarni boshqarish (Manage Members) yoki\n"
            "• Imtiyozli a'zolarni ko'rish (See Members)\n\n"
            "Bekor qilish: /cancel",
            parse_mode="HTML",
        )
        return

    # ---- Save to Firestore ----
    channel_data = {
        "channel_id": channel_id,
        "username": channel_info.get("username", ""),
        "invite_link": channel_info.get("invite_link", ""),
        "title": channel_info.get("title", ""),
    }

    try:
        added = await group_service.add_channel(group_id, channel_data)
    except Exception as exc:
        logger.error("Error adding channel %s to group %s: %s", channel_id, group_id, exc)
        await state.clear()
        await message.answer("❌ Saqlashda xatolik yuz berdi. Keyinroq urinib ko'ring.")
        return

    await state.clear()

    if not added:
        await message.answer(
            f"⚠️ Bu kanal allaqachon ro'yxatda mavjud.\n"
            f"Mavjud kanallarni ko'rish: /channels"
        )
        return

    title = channel_info.get("title", str(channel_id))
    await message.answer(
        f"✅ <b>{title}</b> kanali muvaffaqiyatli qo'shildi!\n\n"
        f"Majburiy obunani yoqish: /fsub_on\n"
        f"Barcha kanallar: /channels",
        parse_mode="HTML",
    )
    logger.info(
        "Channel %s added to group %s by user %s.",
        channel_id, group_id, message.from_user.id,  # type: ignore
    )


# ------------------------------------------------------------------ #
# /delchannel — remove channel
# ------------------------------------------------------------------ #


@router.message(Command("delchannel"))
async def cmd_delchannel(message: Message) -> None:
    """Show inline buttons to remove a channel."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    try:
        channels = await group_service.get_channels(chat_id)
    except Exception as exc:
        logger.error("Error fetching channels for %s: %s", chat_id, exc)
        await message.answer("❌ Ma'lumotlarni olishda xatolik yuz berdi.")
        return

    if not channels:
        await message.answer("📭 O'chirish uchun kanal mavjud emas.")
        return

    builder = InlineKeyboardBuilder()
    for ch in channels:
        title = ch.get("title") or str(ch["channel_id"])
        ch_id = ch["channel_id"]
        builder.row(
            InlineKeyboardButton(
                text=f"🗑 {title}",
                callback_data=f"del_channel:{chat_id}:{ch_id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="del_channel_cancel")
    )

    await message.answer(
        "🗑 <b>Qaysi kanalni o'chirmoqchisiz?</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("del_channel:"))
async def cb_del_channel(callback: CallbackQuery) -> None:
    """Handle the delete-channel inline button."""
    if callback.from_user is None:
        await callback.answer()
        return

    try:
        _, cid_str, ch_id_str = callback.data.split(":")  # type: ignore[union-attr]
        chat_id = int(cid_str)
        channel_id = int(ch_id_str)
    except (ValueError, AttributeError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return

    # Re-check authorization
    bot = callback.bot  # type: ignore[union-attr]
    user_id = callback.from_user.id
    is_global_admin = settings.is_admin(user_id)
    status = await subscription_service.get_member_status(bot, chat_id, user_id)
    if not is_global_admin and status not in ("administrator", "creator"):
        await callback.answer("⛔ Sizda bu amal uchun ruxsat yo'q.", show_alert=True)
        return

    try:
        removed = await group_service.remove_channel(chat_id, channel_id)
    except Exception as exc:
        logger.error("Error removing channel %s from group %s: %s", channel_id, chat_id, exc)
        await callback.answer("❌ O'chirishda xatolik yuz berdi.", show_alert=True)
        return

    if not removed:
        await callback.answer("⚠️ Kanal topilmadi.", show_alert=True)
        return

    await callback.answer("✅ Kanal o'chirildi.", show_alert=False)
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"✅ Kanal muvaffaqiyatli o'chirildi.\n\nBarcha kanallar: /channels",
            parse_mode="HTML",
        )
    except Exception:
        pass
    logger.info("Channel %s removed from group %s by user %s.", channel_id, chat_id, user_id)


@router.callback_query(F.data == "del_channel_cancel")
async def cb_del_channel_cancel(callback: CallbackQuery) -> None:
    """Handle the cancel button on the delete-channel menu."""
    try:
        await callback.message.delete()  # type: ignore[union-attr]
    except Exception:
        pass
    await callback.answer()


# ------------------------------------------------------------------ #
# Private helpers
# ------------------------------------------------------------------ #


async def _resolve_channel(
    bot,
    raw: str,
) -> tuple[int | None, dict]:
    """
    Resolve a channel username or numeric ID to (channel_id, info_dict).

    Returns (None, {}) if the channel cannot be found or bot has no access.
    """
    from aiogram.exceptions import TelegramAPIError

    # Normalize
    identifier: str | int = raw
    if raw.lstrip("-").isdigit():
        identifier = int(raw)
    else:
        identifier = raw if raw.startswith("@") else f"@{raw}"

    try:
        chat = await bot.get_chat(identifier)
        info = {
            "title": chat.title or "",
            "username": f"@{chat.username}" if chat.username else "",
            "invite_link": getattr(chat, "invite_link", "") or "",
        }
        return chat.id, info
    except TelegramAPIError as exc:
        logger.warning("Cannot resolve channel '%s': %s", raw, exc)
        return None, {}


async def _verify_bot_channel_access(bot, channel_id: int) -> bool:
    """
    Check that the bot can call getChatMember on *channel_id*.

    We do this by checking the bot's own membership in the channel.
    """
    from aiogram.exceptions import TelegramAPIError

    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id=channel_id, user_id=me.id)
        # Bot must be administrator to call getChatMember on private channels
        return member.status.value in ("administrator", "creator", "member")
    except TelegramAPIError as exc:
        logger.warning("Bot access check failed for channel %s: %s", channel_id, exc)
        return False
