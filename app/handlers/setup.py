"""
Setup Wizard and Preset configurations for AnjurXBot Qorovul.
Provides quick-start toggleable guard setup directly from /setup.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.keyboards.setup import get_setup_wizard_keyboard
from app.keyboards.help import get_private_group_redirect_keyboard
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback
from app.config import config

router = Router(name="setup_router")

GUARD_KEY_LABELS = {
    "anti_spam": "Anti-Spam",
    "anti_flood": "Anti-Flood",
    "anti_link": "Anti-Link",
    "anti_ads": "Anti-Ads",
    "bad_words_filter": "So'kish filtri",
    "raid_protection": "Raid himoyasi",
    "new_member_protection": "Yangi a'zolar nazorati",
}


@router.message(Command("setup"))
async def cmd_setup(message: Message, bot: Bot):
    # Contextual check for private chat
    if message.chat.type not in ("group", "supergroup"):
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username or "AnjurXBot"
        await message.reply(
            "⚙️ <b>/setup faqat guruh ichida ishlaydi.</b>\n\n"
            "Botni guruhingizga qo‘shing, unga administrator huquqini bering "
            "va guruh ichida <code>/setup</code> buyrug‘ini yuboring.",
            reply_markup=get_private_group_redirect_keyboard(bot_username),
            parse_mode="HTML"
        )
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None

    # Register/sync group data safely (preserves existing settings)
    group_data = await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
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
        chat=message.chat,
        force_fresh=True,
    )
    if not is_admin:
        await message.reply(
            "⛔ <b>Sizda bu sozlamalarni boshqarish huquqi yo‘q.</b>\n"
            "Bu buyruq faqat guruh egasi va administratorlari uchun mo‘ljallangan.",
            parse_mode="HTML"
        )
        return

    guard = group_data.get("guard_settings", {})
    keyboard = get_setup_wizard_keyboard(chat_id, guard)
    await message.reply(
        "🛡 <b>QOROVUL — Tezkor Sozlash</b>\n\n"
        "Guruhingizni himoyalash uchun kerakli filtrlarni tanlang:\n"
        "<i>Har bir tugmani bosish orqali himoyani yoqishingiz yoki o‘chirishingiz mumkin.</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setup:menu:"))
async def cb_setup_menu(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_data = await group_service.get_or_register_group(group_id, bot=bot)
    guard = group_data.get("guard_settings", {})
    keyboard = get_setup_wizard_keyboard(group_id, guard)
    try:
        await callback.message.edit_text(
            "🛡 <b>QOROVUL — Tezkor Sozlash</b>\n\n"
            "Guruhingizni himoyalash uchun kerakli filtrlarni tanlang:\n"
            "<i>Har bir tugmani bosish orqali himoyani yoqishingiz yoki o‘chirishingiz mumkin.</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("setup:toggle:"))
async def cb_setup_toggle(callback: CallbackQuery, bot: Bot):
    """Handles direct ON/OFF toggling of guard protections in /setup."""
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Xatolik yuz berdi", show_alert=True)
        return

    group_id = int(parts[2])
    setting_key = parts[3]

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_data = await group_service.get_or_register_group(group_id, bot=bot)
    guard = group_data.get("guard_settings", {})
    cur_val = bool(guard.get(setting_key, True))
    new_val = not cur_val

    await group_service.update_guard_setting(group_id, setting_key, new_val)
    guard[setting_key] = new_val

    label = GUARD_KEY_LABELS.get(setting_key, setting_key)
    notification = f"🟢 {label} yoqildi" if new_val else f"🔴 {label} o‘chirildi"

    new_kb = get_setup_wizard_keyboard(group_id, guard)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass

    await callback.answer(notification)


@router.callback_query(F.data.startswith("setup:preset:default:"))
async def cb_preset_default(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    default_settings = {
        "anti_link": True,
        "anti_spam": True,
        "anti_flood": True,
        "anti_ads": True,
        "anti_repeat": True,
        "bad_words_filter": False,
        "raid_protection": True,
        "new_member_protection": True,
        "delete_service_messages": True,
        "flood_limit": 5,
        "warn_limit": 3,
        "punishment": "mute"
    }

    for k, v in default_settings.items():
        await group_service.update_guard_setting(group_id, k, v)

    text = (
        "✅ <b>Standart himoya rejimi faollashtirildi!</b>\n\n"
        "• Anti-Link, Anti-Spam, Anti-Ads: 🟢 Yoqilgan\n"
        "• Anti-Flood: 5 xabar / 5 soniya\n"
        "• Yangi a'zolar nazorati & Kirdi/Chiqdi tozalash: 🟢 Yoqilgan\n"
        "• Jazo turi: Mute (3 ta ogohlantirishdan so‘ng)\n\n"
        "Barcha sozlamalarni ko'rish uchun: /settings"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data=f"settings:menu:{group_id}"),
                InlineKeyboardButton(text="◀️ Qorovulga qaytish", callback_data=f"setup:menu:{group_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Yopish", callback_data="common:close"),
            ]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.reply(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("🟢 Standart rejim yoqildi!")


@router.callback_query(F.data.startswith("setup:preset:strict:"))
async def cb_preset_strict(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    strict_settings = {
        "anti_link": True,
        "anti_spam": True,
        "anti_flood": True,
        "anti_ads": True,
        "anti_repeat": True,
        "bad_words_filter": True,
        "raid_protection": True,
        "new_member_protection": True,
        "delete_service_messages": True,
        "flood_limit": 3,
        "warn_limit": 2,
        "punishment": "mute"
    }

    for k, v in strict_settings.items():
        await group_service.update_guard_setting(group_id, k, v)

    text = (
        "🛡 <b>Qat'iy (Strict) himoya rejimi faollashtirildi!</b>\n\n"
        "• Barcha havolalar, spam va reklamalar bloklanadi\n"
        "• Qaytariluvchi xabarlar va so‘kinish filtri yoqildi\n"
        "• Raid va bot hujumlaridan himoya faollashtirildi\n"
        "• Anti-Flood: 3 xabar / 5 soniya\n"
        "• Jazo: 2 ta ogohlantirishdan so‘ng Mute!\n\n"
        "Barcha sozlamalarni ko'rish uchun: /settings"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data=f"settings:menu:{group_id}"),
                InlineKeyboardButton(text="◀️ Qorovulga qaytish", callback_data=f"setup:menu:{group_id}"),
            ],
            [
                InlineKeyboardButton(text="❌ Yopish", callback_data="common:close"),
            ]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.reply(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("🟢 Qat'iy rejim yoqildi!")
