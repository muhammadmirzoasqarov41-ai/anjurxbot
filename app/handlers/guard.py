"""
Guard settings and configuration handlers.
Allows group admins to toggle filters and adjust thresholds.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.keyboards.guard import get_guard_settings_keyboard
from app.keyboards.settings import (
    get_settings_guard_keyboard,
    get_settings_sec_keyboard,
    get_settings_warns_keyboard,
    get_settings_srv_keyboard,
)
from app.states.admin_states import BadWordsState, FloodThresholdState, WarningLimitState
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback

router = Router(name="guard_router")


@router.message(Command("guard"))
async def cmd_guard(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None

    group_config = await group_service.get_or_register_group(
        chat_id,
        message.chat.title or "",
        chat=message.chat,
        bot=bot
    )

    is_admin = await permission_service.is_user_admin(
        bot,
        chat_id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat
    )
    if not is_admin:
        await message.reply("❌ Bu sozlama faqat guruh adminlari uchun ruxsat etilgan.")
        return
    guard_settings = group_config.get("guard_settings", {})
    keyboard = get_guard_settings_keyboard(chat_id, guard_settings)

    await message.reply(
        "🛡 <b>Guruh Himoyasi Sozlamalari:</b>\n\n"
        "Tugmalar orqali filtrlarni yoqishingiz yoki o'chirishingiz mumkin:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("guard:menu:"))
async def cb_guard_menu(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not group_id and callback.message and callback.message.chat:
        group_id = callback.message.chat.id

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})
    keyboard = get_guard_settings_keyboard(group_id, guard_settings)

    try:
        await callback.message.edit_text(
            "🛡 <b>Guruh Himoyasi Sozlamalari:</b>\n\n"
            "Tugmalar orqali filtrlarni yoqishingiz yoki o'chirishingiz mumkin:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("guard:toggle:"))
async def cb_guard_toggle(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Xatolik yuz berdi.")
        return

    group_id = int(parts[2])
    setting_key = parts[3]
    subview = parts[4] if len(parts) > 4 else None

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})
    current_val = guard_settings.get(setting_key, True)
    new_val = not current_val

    await group_service.update_guard_setting(group_id, setting_key, new_val)
    guard_settings[setting_key] = new_val

    if subview == "guard":
        keyboard = get_settings_guard_keyboard(group_id, guard_settings)
    elif subview == "sec":
        keyboard = get_settings_sec_keyboard(group_id, guard_settings)
    elif subview == "srv":
        keyboard = get_settings_srv_keyboard(group_id, guard_settings)
    elif subview == "warns":
        keyboard = get_settings_warns_keyboard(group_id, guard_settings)
    else:
        keyboard = get_guard_settings_keyboard(group_id, guard_settings)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    name_map = {
        "anti_link": "Anti-Link",
        "anti_spam": "Anti-Spam",
        "anti_ads": "Anti-Ads",
        "anti_flood": "Anti-Flood",
        "anti_repeat": "Anti-Repeat",
        "bad_words_filter": "So'kish filtri",
        "delete_service_messages": "Kirdi/Chiqdi tozalash",
    }
    label = name_map.get(setting_key, setting_key.replace('_', ' ').capitalize())
    notification = f"🟢 {label} yoqildi" if new_val else f"🔴 {label} o'chirildi"
    await callback.answer(notification)


@router.callback_query(F.data.startswith("guard:cycle_punishment:"))
async def cb_cycle_punishment(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    group_id = int(parts[2]) if len(parts) > 2 and (parts[2].isdigit() or (parts[2].startswith("-") and parts[2][1:].isdigit())) else extract_group_id_from_callback(callback.data)
    subview = parts[3] if len(parts) > 3 else None

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})
    current_punish = guard_settings.get("punishment", "mute").lower()

    cycle = {"mute": "kick", "kick": "ban", "ban": "mute"}
    new_punish = cycle.get(current_punish, "mute")

    await group_service.update_guard_setting(group_id, "punishment", new_punish)
    guard_settings["punishment"] = new_punish

    if subview == "warns":
        keyboard = get_settings_warns_keyboard(group_id, guard_settings)
    else:
        keyboard = get_guard_settings_keyboard(group_id, guard_settings)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    await callback.answer(f"Jazo turi o'zgartirildi: {new_punish.upper()}")


@router.callback_query(F.data.startswith("guard:threshold:"))
async def cb_guard_threshold(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Xatolik.")
        return

    group_id = int(parts[2])
    target_type = parts[3]
    subview = parts[4] if len(parts) > 4 else None

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})

    if target_type == "flood":
        current = int(guard_settings.get("flood_limit", 5))
        flood_cycle = {3: 5, 5: 7, 7: 10, 10: 3}
        new_val = flood_cycle.get(current, 5)
        await group_service.update_guard_setting(group_id, "flood_limit", new_val)
        guard_settings["flood_limit"] = new_val
        msg = f"Flood chegarasi: {new_val} ta xabar"
    elif target_type == "warn":
        current = int(guard_settings.get("warn_limit", 3))
        warn_cycle = {2: 3, 3: 5, 5: 2}
        new_val = warn_cycle.get(current, 3)
        await group_service.update_guard_setting(group_id, "warn_limit", new_val)
        guard_settings["warn_limit"] = new_val
        msg = f"Ogohlantirish chegarasi: {new_val} ta"
    else:
        await callback.answer()
        return

    if subview == "sec":
        keyboard = get_settings_sec_keyboard(group_id, guard_settings)
    elif subview == "warns":
        keyboard = get_settings_warns_keyboard(group_id, guard_settings)
    else:
        keyboard = get_guard_settings_keyboard(group_id, guard_settings)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    await callback.answer(msg)


@router.callback_query(F.data.startswith("guard:words:"))
async def cb_guard_words(callback: CallbackQuery, bot: Bot, state: FSMContext):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    words = list(group_config.get("guard_settings", {}).get("bad_words", []))

    total = len(words)
    # Display preview formatted cleanly within Telegram's message limits
    if not words:
        words_display = "<i>Hozircha taqiqlangan so'zlar ro'yxati bo'sh.</i>"
    else:
        # Show words cleanly
        words_display = ", ".join(f"<code>{w}</code>" for w in words[:120])
        if total > 120:
            words_display += f"\n<i>... va yana {total - 120} ta so'z</i>"

    text = (
        f"📝 <b>Taqiqlangan so'zlar ro'yxati (Jami: {total} ta):</b>\n\n"
        f"{words_display}\n\n"
        "➕ <b>Yangi so'z(lar) qo'shish:</b>\n"
        "Shunchaki shu yerga so'zni (yoki vergul bilan ajratib bir nechta so'zlarni) yuboring.\n"
        "❌ Bekor qilish uchun: <code>/cancel</code>"
    )
    await state.set_state(BadWordsState.waiting_for_word)
    await state.update_data(group_id=group_id)
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()


@router.message(BadWordsState.waiting_for_word)
async def process_new_bad_word(message: Message, state: FSMContext):
    raw_text = (message.text or "").strip()
    if raw_text.lower() == "/cancel":
        await state.clear()
        await message.reply("Amal bekor qilindi.")
        return

    data = await state.get_data()
    group_id = data.get("group_id")

    if not group_id:
        await state.clear()
        return

    # Parse single or comma/newline-separated words
    items = [item.strip().lower() for item in raw_text.replace("\n", ",").split(",") if item.strip()]
    valid_new_words = [w for w in items if len(w) >= 2]

    if not valid_new_words:
        await message.reply("⚠️ Hech qanday to'g'ri so'z topilmadi. Har bir so'z kamida 2 ta harfdan iborat bo'lishi kerak.")
        return

    group_config = await group_service.get_or_register_group(group_id)
    existing_words = list(group_config.get("guard_settings", {}).get("bad_words", []))
    added = []

    for word in valid_new_words:
        if word not in existing_words:
            existing_words.append(word)
            added.append(word)

    if added:
        await group_service.update_guard_setting(group_id, "bad_words", existing_words)
        added_str = ", ".join(f"<code>{w}</code>" for w in added[:30])
        if len(added) > 30:
            added_str += f" va yana {len(added) - 30} ta"
        await message.reply(
            f"✅ <b>{len(added)} ta so'z</b> taqiqlangan so'zlar ro'yxatiga muvaffaqiyatli qo'shildi:\n{added_str}\n\n"
            f"📊 <i>Ro'yxatdagi jami so'zlar: {len(existing_words)} ta.</i>",
            parse_mode="HTML"
        )
    else:
        await message.reply("ℹ️ Kiritilgan barcha so'zlar allaqachon ro'yxatda mavjud edi.")

    await state.clear()
