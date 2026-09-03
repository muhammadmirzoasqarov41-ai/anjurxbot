"""
Guard admin command handlers.

Commands:
  /guard        — Show guard panel (inline toggle keyboard)
  /guard_on     — Enable guard system
  /guard_off    — Disable guard system
  /badwords     — List bad words
  /addword <w>  — Add a bad word
  /delword <w>  — Remove a bad word
  /clearwarns   — Clear warnings (reply or user ID)

Access control: group admin OR global ADMIN_IDS.
Callbacks: guard_toggle, guard_master, guard_close.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.keyboards.guard import GUARD_FEATURES, guard_panel_keyboard
from app.services import guard_service
from app.services.subscription_service import get_member_status
from app.utils.logger import logger

router = Router(name="guard_admin")

_GROUP_TYPES = {"group", "supergroup"}


# ------------------------------------------------------------------ #
# Guards
# ------------------------------------------------------------------ #

async def _is_authorized(message: Message) -> bool:
    if message.from_user is None:
        return False
    user_id = message.from_user.id
    if settings.is_admin(user_id):
        return True
    if message.chat.type in _GROUP_TYPES:
        bot = message.bot  # type: ignore[union-attr]
        status = await get_member_status(bot, message.chat.id, user_id)
        if status in ("administrator", "creator"):
            return True
    return False


async def _require_group(message: Message) -> bool:
    if message.chat.type not in _GROUP_TYPES:
        await message.answer("⚠️ Bu buyruq faqat guruh ichida ishlaydi.")
        return False
    return True


async def _cb_is_authorized(callback: CallbackQuery, chat_id: int) -> bool:
    """Callback-level authorization check."""
    if callback.from_user is None:
        return False
    user_id = callback.from_user.id
    if settings.is_admin(user_id):
        return True
    bot = callback.bot  # type: ignore[union-attr]
    status = await get_member_status(bot, chat_id, user_id)
    return status in ("administrator", "creator")


# ------------------------------------------------------------------ #
# /guard
# ------------------------------------------------------------------ #

@router.message(Command("guard"))
async def cmd_guard(message: Message) -> None:
    """Show the guard settings panel."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    guard = await guard_service.get_guard_settings(chat_id)
    enabled = guard.get("enabled", False)

    status_lines = []
    for key, label in GUARD_FEATURES.items():
        val = "✅ Yoqilgan" if guard.get(key, False) else "❌ O'chirilgan"
        status_lines.append(f"{label}: {val}")

    master_text = "✅ YOQILGAN" if enabled else "❌ O'CHIRILGAN"
    text = (
        f"🛡 <b>QOROVUL</b>\n"
        f"Guruh himoyasi — {master_text}\n\n"
        + "\n".join(status_lines)
    )

    await message.answer(
        text,
        reply_markup=guard_panel_keyboard(guard, chat_id),
        parse_mode="HTML",
    )
    logger.info("/guard opened by user %s in group %s.", message.from_user.id, chat_id)  # type: ignore


# ------------------------------------------------------------------ #
# /guard_on / /guard_off
# ------------------------------------------------------------------ #

@router.message(Command("guard_on"))
async def cmd_guard_on(message: Message) -> None:
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return
    await guard_service.set_guard_enabled(message.chat.id, True)
    await message.answer("✅ Qorovul <b>yoqildi</b>.", parse_mode="HTML")
    logger.info("Guard enabled for group %s by user %s.", message.chat.id, message.from_user.id)  # type: ignore


@router.message(Command("guard_off"))
async def cmd_guard_off(message: Message) -> None:
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return
    await guard_service.set_guard_enabled(message.chat.id, False)
    await message.answer("❌ Qorovul <b>o'chirildi</b>.", parse_mode="HTML")
    logger.info("Guard disabled for group %s by user %s.", message.chat.id, message.from_user.id)  # type: ignore


# ------------------------------------------------------------------ #
# Inline callbacks — guard panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("guard_toggle:"))
async def cb_guard_toggle(callback: CallbackQuery) -> None:
    """Toggle a single guard feature on/off."""
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    try:
        _, cid_str, feature = callback.data.split(":", 2)  # type: ignore[union-attr]
        chat_id = int(cid_str)
    except (ValueError, AttributeError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return

    if not await _cb_is_authorized(callback, chat_id):
        await callback.answer("⛔ Sizda ruxsat yo'q.", show_alert=True)
        return

    if feature not in GUARD_FEATURES:
        await callback.answer("❌ Noma'lum funksiya.", show_alert=True)
        return

    guard = await guard_service.get_guard_settings(chat_id)
    current = guard.get(feature, False)
    new_val = not current

    await guard_service.toggle_guard_feature(chat_id, feature, new_val)

    # Refresh settings for updated keyboard
    guard[feature] = new_val
    label = GUARD_FEATURES[feature]
    status = "yoqildi ✅" if new_val else "o'chirildi ❌"
    await callback.answer(f"{label} {status}")

    # Update the panel message
    guard_updated = await guard_service.get_guard_settings(chat_id)
    enabled = guard_updated.get("enabled", False)
    status_lines = [
        "{}: {}".format(lbl, "✅ Yoqilgan" if guard_updated.get(k, False) else "❌ O'chirilgan")
        for k, lbl in GUARD_FEATURES.items()
    ]
    master_text = "✅ YOQILGAN" if enabled else "❌ O'CHIRILGAN"
    text = (
        "🛡 <b>QOROVUL</b>\n"
        f"Guruh himoyasi — {master_text}\n\n"
        + "\n".join(status_lines)
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=guard_panel_keyboard(guard_updated, chat_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("guard_master:"))
async def cb_guard_master(callback: CallbackQuery) -> None:
    """Toggle the master guard on/off from the panel."""
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    try:
        _, cid_str, action = callback.data.split(":", 2)  # type: ignore[union-attr]
        chat_id = int(cid_str)
    except (ValueError, AttributeError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return

    if not await _cb_is_authorized(callback, chat_id):
        await callback.answer("⛔ Sizda ruxsat yo'q.", show_alert=True)
        return

    enabled = action == "on"
    await guard_service.set_guard_enabled(chat_id, enabled)
    label = "yoqildi ✅" if enabled else "o'chirildi ❌"
    await callback.answer(f"Qorovul {label}")

    guard = await guard_service.get_guard_settings(chat_id)
    status_lines = [
        "{}: {}".format(lbl, "✅ Yoqilgan" if guard.get(k, False) else "❌ O'chirilgan")
        for k, lbl in GUARD_FEATURES.items()
    ]
    master_text = "✅ YOQILGAN" if enabled else "❌ O'CHIRILGAN"
    text = (
        "🛡 <b>QOROVUL</b>\n"
        f"Guruh himoyasi — {master_text}\n\n"
        + "\n".join(status_lines)
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=guard_panel_keyboard(guard, chat_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "guard_close")
async def cb_guard_close(callback: CallbackQuery) -> None:
    """Close the guard panel."""
    try:
        await callback.message.delete()  # type: ignore[union-attr]
    except Exception:
        pass
    await callback.answer()


# ------------------------------------------------------------------ #
# /badwords, /addword, /delword
# ------------------------------------------------------------------ #

@router.message(Command("badwords"))
async def cmd_badwords(message: Message) -> None:
    """List all bad words for this group."""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    chat_id = message.chat.id
    words = await guard_service.get_bad_words(chat_id)

    if not words:
        await message.answer(
            "📭 Taqiqlangan so'zlar ro'yxati bo'sh.\n\n"
            "Qo'shish: <code>/addword so'z</code>",
            parse_mode="HTML",
        )
        return

    word_list = "\n".join(f"  {i}. <code>{w}</code>" for i, w in enumerate(words, 1))
    await message.answer(
        f"🚫 <b>Taqiqlangan so'zlar</b> ({len(words)} ta):\n\n"
        f"{word_list}\n\n"
        f"Qo'shish: <code>/addword so'z</code>\n"
        f"O'chirish: <code>/delword so'z</code>",
        parse_mode="HTML",
    )


@router.message(Command("addword"))
async def cmd_addword(message: Message) -> None:
    """Add a word to the bad-words list. Usage: /addword <word>"""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    # Parse argument
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "⚠️ So'zni kiriting.\n\nMasalan: <code>/addword so'z</code>",
            parse_mode="HTML",
        )
        return

    word = parts[1].strip().lower()
    if len(word) < 2:
        await message.answer("⚠️ So'z kamida 2 ta harf bo'lishi kerak.")
        return

    added = await guard_service.add_bad_word(message.chat.id, word)
    if added:
        await message.answer(
            f"✅ <code>{word}</code> taqiqlangan so'zlar ro'yxatiga qo'shildi.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"⚠️ <code>{word}</code> allaqachon ro'yxatda mavjud.",
            parse_mode="HTML",
        )


@router.message(Command("delword"))
async def cmd_delword(message: Message) -> None:
    """Remove a word from the bad-words list. Usage: /delword <word>"""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "⚠️ So'zni kiriting.\n\nMasalan: <code>/delword so'z</code>",
            parse_mode="HTML",
        )
        return

    word = parts[1].strip().lower()
    removed = await guard_service.remove_bad_word(message.chat.id, word)
    if removed:
        await message.answer(
            f"✅ <code>{word}</code> ro'yxatdan o'chirildi.",
            parse_mode="HTML",
        )
    else:
        await message.answer(
            f"⚠️ <code>{word}</code> ro'yxatda topilmadi.",
            parse_mode="HTML",
        )

# ------------------------------------------------------------------ #
# /clearwarns
# ------------------------------------------------------------------ #

@router.message(Command("clearwarns"))
async def cmd_clearwarns(message: Message) -> None:
    """Clear warnings for a user. Usage: /clearwarns (reply) or /clearwarns <user_id>"""
    if not await _require_group(message):
        return
    if not await _is_authorized(message):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return

    user_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        user_id = message.reply_to_message.from_user.id
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) > 1 and parts[1].isdigit():
            user_id = int(parts[1])

    if not user_id:
        await message.answer(
            "⚠️ Foydalanuvchini aniqlab bo'lmadi.\n\n"
            "Foydalanish: Xabarga reply qiling yoki <code>/clearwarns ID</code> shaklida yozing.",
            parse_mode="HTML"
        )
        return

    chat_id = message.chat.id
    from app.services.punishment_service import reset_warnings
    await reset_warnings(chat_id, user_id)

    admin_id = message.from_user.id if message.from_user else 0
    import asyncio
    from app.services import log_service
    asyncio.create_task(log_service.log_admin_action(chat_id, admin_id, "Warning tozalash", f"User: {user_id}"))

    await message.answer(f"✅ Foydalanuvchi (<code>{user_id}</code>) ning barcha ogohlantirishlari tozalandi.", parse_mode="HTML")
