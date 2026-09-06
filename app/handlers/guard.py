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

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})
    current_val = guard_settings.get(setting_key, True)
    new_val = not current_val

    await group_service.update_guard_setting(group_id, setting_key, new_val)
    guard_settings[setting_key] = new_val

    keyboard = get_guard_settings_keyboard(group_id, guard_settings)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    status_text = "yoqildi ✅" if new_val else "o'chirildi ❌"
    await callback.answer(f"Sozlama {status_text}")


@router.callback_query(F.data.startswith("guard:cycle_punishment:"))
async def cb_cycle_punishment(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard_settings = group_config.get("guard_settings", {})
    current_punish = guard_settings.get("punishment", "mute").lower()

    cycle = {"mute": "kick", "kick": "ban", "ban": "mute"}
    new_punish = cycle.get(current_punish, "mute")

    await group_service.update_guard_setting(group_id, "punishment", new_punish)
    guard_settings["punishment"] = new_punish

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
    words = group_config.get("guard_settings", {}).get("bad_words", [])

    text = (
        "📝 <b>Taqiqlangan so'zlar ro'yxati:</b>\n\n"
        + (", ".join(f"<code>{w}</code>" for w in words) if words else "Hozircha taqiqlangan so'zlar kiritilmagan.")
        + "\n\nYangi so'z qo'shish uchun shunchaki shu guruhga yoki botga so'zni yuboring.\n"
        "Bekor qilish uchun /cancel deb yozing."
    )
    await state.set_state(BadWordsState.waiting_for_word)
    await state.update_data(group_id=group_id)
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()


@router.message(BadWordsState.waiting_for_word)
async def process_new_bad_word(message: Message, state: FSMContext):
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.reply("Amal bekor qilindi.")
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    word = (message.text or "").strip().lower()

    if not word or len(word) < 2:
        await message.reply("So'z juda qisqa. Kamida 2 ta belgidan iborat bo'lishi kerak.")
        return

    if group_id:
        group_config = await group_service.get_or_register_group(group_id)
        words = list(group_config.get("guard_settings", {}).get("bad_words", []))
        if word not in words:
            words.append(word)
            await group_service.update_guard_setting(group_id, "bad_words", words)
            await message.reply(f"✅ <code>{word}</code> taqiqlangan so'zlar ro'yxatiga qo'shildi!", parse_mode="HTML")
        else:
            await message.reply(f"ℹ️ <code>{word}</code> allaqachon ro'yxatda mavjud.", parse_mode="HTML")

    await state.clear()
