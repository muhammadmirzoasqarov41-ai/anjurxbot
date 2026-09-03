"""
Admin panel FSM handlers.

Handles interactive input flows:
  - Flood limit / window / mute duration change
  - Bad word add / remove
  - FSub channel add
"""
from __future__ import annotations

from html import escape
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.admin_helpers import (
    build_flood_text, build_badwords_text, build_fsub_text, is_global_admin,
)
from app.keyboards.admin import (
    flood_settings_keyboard, bad_words_keyboard, fsub_panel_keyboard, cancel_keyboard,
)
from app.services import group_service, guard_service, log_service
from app.services.permission_service import permission_service
from app.states.admin_states import (
    FloodSettingsStates, BadWordStates, FsubChannelStates,
)
from app.utils.logger import logger

router = Router(name="admin_fsm")

_PRIVATE = {"private"}


async def _admin_only(user_id: int | None, state: FSMContext, bot) -> bool:
    if user_id is None:
        return False
    if is_global_admin(user_id):
        return True
    data = await state.get_data()
    group_id = data.get("group_id")
    return group_id is not None and await permission_service.is_group_admin(
        bot, int(group_id), user_id
    )


async def _deny_cb(callback: CallbackQuery) -> None:
    await callback.answer("❌ Sizda ruxsat yo'q.", show_alert=True)


# ------------------------------------------------------------------ #
# Flood limit
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:fl:"))
async def cb_flood_limit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await state.set_state(FloodSettingsStates.waiting_limit)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "🔢 <b>Yangi flood limitini kiriting.</b>\n\n"
        "Masalan: <code>5</code> (5 ta xabar / oyna)\n\n"
        "Qiymat 1–100 orasida bo'lishi kerak.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(FloodSettingsStates.waiting_limit)
async def fsm_flood_limit(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 100):
        await message.answer(
            "❌ Noto'g'ri qiymat.\n\nIltimos, 1–100 orasidagi raqam yuboring.",
            reply_markup=cancel_keyboard(),
        )
        return
    data = await state.get_data()
    group_id: int = data["group_id"]
    await guard_service.update_guard_param(group_id, "flood_limit", int(raw))

    admin_id = message.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "Flood limit", raw))

    await state.clear()
    text = await build_flood_text(group_id)
    await message.answer(
        f"✅ Flood limit <b>{raw}</b> ga o'zgartirildi.\n\n" + text,
        reply_markup=flood_settings_keyboard(group_id),
        parse_mode="HTML",
    )
    logger.info("Flood limit set to %s for group %s.", raw, group_id)


# ------------------------------------------------------------------ #
# Flood window
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:fwc:"))
async def cb_flood_window_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await state.set_state(FloodSettingsStates.waiting_window)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "⏱ <b>Yangi vaqt oynasini kiriting (soniyalarda).</b>\n\n"
        "Masalan: <code>5</code> (5 soniya)\n\nQiymat 1–60 orasida bo'lishi kerak.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(FloodSettingsStates.waiting_window)
async def fsm_flood_window(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 60):
        await message.answer(
            "❌ Noto'g'ri qiymat.\n\nIltimos, 1–60 orasidagi raqam yuboring.",
            reply_markup=cancel_keyboard(),
        )
        return
    data = await state.get_data()
    group_id: int = data["group_id"]
    await guard_service.update_guard_param(group_id, "flood_window", int(raw))

    admin_id = message.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "Flood window", f"{raw}s"))

    await state.clear()
    text = await build_flood_text(group_id)
    await message.answer(
        f"✅ Vaqt oynasi <b>{raw} soniya</b> ga o'zgartirildi.\n\n" + text,
        reply_markup=flood_settings_keyboard(group_id),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
# Mute duration
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:mu:"))
async def cb_mute_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await state.set_state(FloodSettingsStates.waiting_mute)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "🔇 <b>Yangi mute muddatini kiriting (daqiqalarda).</b>\n\n"
        "Masalan: <code>5</code> (5 daqiqa)\n\nQiymat 1–1440 orasida bo'lishi kerak.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(FloodSettingsStates.waiting_mute)
async def fsm_mute_duration(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= 1440):
        await message.answer(
            "❌ Noto'g'ri qiymat.\n\nIltimos, 1–1440 orasidagi raqam (daqiqa) yuboring.",
            reply_markup=cancel_keyboard(),
        )
        return
    data = await state.get_data()
    group_id: int = data["group_id"]
    seconds = int(raw) * 60
    await guard_service.update_guard_param(group_id, "mute_duration", seconds)

    admin_id = message.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "Mute muddati", f"{raw}m"))

    await state.clear()
    text = await build_flood_text(group_id)
    await message.answer(
        f"✅ Mute muddati <b>{raw} daqiqa</b> ga o'zgartirildi.\n\n" + text,
        reply_markup=flood_settings_keyboard(group_id),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
# Bad word add
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:bwa:"))
async def cb_badword_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await state.set_state(BadWordStates.waiting_add)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Taqiqlash uchun so'z yuboring.</b>\n\n"
        "Masalan: <code>spam</code>",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(BadWordStates.waiting_add)
async def fsm_badword_add(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    word = (message.text or "").strip().lower()
    if len(word) < 2:
        await message.answer(
            "❌ So'z kamida 2 ta harf bo'lishi kerak.",
            reply_markup=cancel_keyboard(),
        )
        return
    data = await state.get_data()
    group_id: int = data["group_id"]
    added = await guard_service.add_bad_word(group_id, word)
    await state.clear()

    if added:
        admin_id = message.from_user.id
        import asyncio
        asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "So'z qo'shildi", word))
        reply = f"✅ <code>{escape(word)}</code> ro'yxatga qo'shildi."
    else:
        reply = f"⚠️ <code>{escape(word)}</code> allaqachon ro'yxatda."
    guard = await guard_service.get_guard_settings(group_id)
    text = await build_badwords_text(group_id)
    await message.answer(
        reply + "\n\n" + text,
        reply_markup=bad_words_keyboard(guard, group_id),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
# Bad word remove
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:bwd:"))
async def cb_badword_del_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    words = await guard_service.get_bad_words(group_id)
    if not words:
        await callback.answer("📭 Ro'yxat bo'sh.", show_alert=True)
        return
    await state.set_state(BadWordStates.waiting_del)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "🗑 <b>O'chirish uchun so'z yuboring.</b>\n\n"
        "Mavjud so'zlar: " + ", ".join(f"<code>{escape(w)}</code>" for w in words[:20]),
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(BadWordStates.waiting_del)
async def fsm_badword_del(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    word = (message.text or "").strip().lower()
    data = await state.get_data()
    group_id: int = data["group_id"]
    removed = await guard_service.remove_bad_word(group_id, word)
    await state.clear()

    if removed:
        admin_id = message.from_user.id
        import asyncio
        asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "So'z o'chirildi", word))
        reply = f"✅ <code>{escape(word)}</code> ro'yxatdan o'chirildi."
    else:
        reply = f"⚠️ <code>{escape(word)}</code> topilmadi."
    guard = await guard_service.get_guard_settings(group_id)
    text = await build_badwords_text(group_id)
    await message.answer(
        reply + "\n\n" + text,
        reply_markup=bad_words_keyboard(guard, group_id),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
# FSub channel add
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:fa:"))
async def cb_fsub_add_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _admin_only(callback.from_user.id if callback.from_user else None, state, callback.bot):
        await _deny_cb(callback)
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await state.set_state(FsubChannelStates.waiting_add)
    await state.update_data(group_id=group_id)
    await callback.answer()
    await callback.message.answer(
        "📢 <b>Kanal username yoki ID sini yuboring.</b>\n\n"
        "Masalan:\n<code>@mychannel</code>\n<code>-1001234567890</code>\n\n"
        "Bot kanalda administrator bo'lishi kerak.",
        reply_markup=cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(FsubChannelStates.waiting_add)
async def fsm_fsub_add(message: Message, state: FSMContext) -> None:
    if not await _admin_only(message.from_user.id if message.from_user else None, state, message.bot):
        return
    raw = (message.text or "").strip()
    bot = message.bot
    data = await state.get_data()
    group_id: int = data["group_id"]

    # Resolve channel
    identifier: str | int = int(raw) if raw.lstrip("-").isdigit() else (
        raw if raw.startswith("@") else f"@{raw}"
    )
    try:
        chat = await bot.get_chat(identifier)
        channel_id = chat.id
        title = chat.title or ""
        username = f"@{chat.username}" if chat.username else ""
        invite_link = getattr(chat, "invite_link", "") or ""
    except Exception as exc:
        logger.warning("Cannot resolve channel '%s': %s", raw, exc)
        await message.answer(
            "❌ Kanal topilmadi yoki botga kirish huquqi yo'q.\n\n"
            "Botni kanalga admin qilib qo'ying.",
            reply_markup=cancel_keyboard(),
        )
        return

    channel_data = {
        "channel_id": channel_id,
        "username": username,
        "invite_link": invite_link,
        "title": title,
    }
    added = await group_service.add_channel(group_id, channel_data)
    await state.clear()

    if added:
        admin_id = message.from_user.id
        import asyncio
        asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "FSub kanal qo'shildi", title or username))
        reply = f"✅ <b>{title or username}</b> kanali qo'shildi."
    else:
        reply = "⚠️ Bu kanal allaqachon ro'yxatda."

    fsub = await group_service.get_fsub_settings(group_id)
    text = await build_fsub_text(group_id)
    await message.answer(
        reply + "\n\n" + text,
        reply_markup=fsub_panel_keyboard(fsub, group_id),
        parse_mode="HTML",
    )
