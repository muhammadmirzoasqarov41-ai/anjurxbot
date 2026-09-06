"""
Setup Wizard and Preset configurations.
Provides quick-start setup for newly created or configured groups.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.keyboards.setup import get_setup_wizard_keyboard
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback

router = Router(name="setup_router")


@router.message(Command("setup"))
async def cmd_setup(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    sender_chat_id = message.sender_chat.id if message.sender_chat else None

    await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
        chat=message.chat,
        bot=bot
    )

    if not await permission_service.is_user_admin(bot, chat_id, user_id, sender_chat_id=sender_chat_id):
        await message.reply("❌ Bu amal faqat guruh adminlari uchun ruxsat etilgan.")
        return

    keyboard = get_setup_wizard_keyboard(chat_id)
    await message.reply(
        "🚀 <b>AnjurXBot Tezkor Sozlash Ustasi:</b>\n\n"
        "Guruh himoyasini bir marta bosish orqali eng maqbul rejimda sozlang:\n\n"
        "• <b>Oddiy rejim:</b> Reklama va spamga qarshi asosiy himoya.\n"
        "• <b>Qattiq rejim:</b> Barcha filtrlar, qattiq flood cheklovi va so'kinish filtri faollashtiriladi.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setup:menu:"))
async def cb_setup_menu(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    keyboard = get_setup_wizard_keyboard(group_id)
    try:
        await callback.message.edit_text(
            "🚀 <b>AnjurXBot Tezkor Sozlash Ustasi:</b>\n\n"
            "Guruh himoyasini bir marta bosish orqali sozlang:\n\n"
            "• <b>Standart:</b> Reklama va spamga qarshi asosiy himoya.\n"
            "• <b>Qat'iy:</b> Barcha filtrlar va so'kinish filtri faol.",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


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
        "bad_words_filter": False,
        "flood_limit": 5,
        "warn_limit": 3,
        "punishment": "mute"
    }

    for k, v in default_settings.items():
        await group_service.update_guard_setting(group_id, k, v)

    await callback.message.reply(
        "✅ <b>Oddiy himoya rejimi yoqildi!</b>\n\n"
        "• Reklama va havolalar: O'chiriladi\n"
        "• Anti-Flood: 5 xabar / 5 soniya\n"
        "• Jazo turi: Mute (3 ta ogohlantirishdan so'ng)",
        parse_mode="HTML"
    )
    await callback.answer("Oddiy rejim qo'llandi!")


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
        "flood_limit": 3,
        "warn_limit": 2,
        "punishment": "mute"
    }

    for k, v in strict_settings.items():
        await group_service.update_guard_setting(group_id, k, v)

    await callback.message.reply(
        "🛡 <b>Qattiq (Strict) himoya rejimi yoqildi!</b>\n\n"
        "• Barcha havolalar, spam va reklamalar bloklanadi\n"
        "• Qaytariluvchi xabarlar va so'kinish filtri yoqildi\n"
        "• Anti-Flood: 3 xabar / 5 soniya\n"
        "• Jazo: 2 ta ogohlantirishdan so'ng darhol Mute!",
        parse_mode="HTML"
    )
    await callback.answer("Qattiq rejim qo'llandi!")
