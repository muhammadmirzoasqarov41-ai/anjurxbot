"""
Start and Help Command Handlers for AnjurXBot.
Provides professional, clear, and actionable onboarding and help UX.
"""
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from app.services.firebase import firebase_service
from app.keyboards.help import (
    get_start_keyboard,
    get_help_menu_keyboard,
    get_help_sub_keyboard,
)
from app.config import config

router = Router(name="start_router")


def _get_start_text(user_name: str) -> str:
    """Returns the primary concise and professional welcome message."""
    clean_name = user_name.replace("<", "&lt;").replace(">", "&gt;") if user_name else "Foydalanuvchi"
    return (
        f"Assalomu alaykum, <b>{clean_name}</b>! 👋\n\n"
        f"🤖 <b>AnjurXBot</b>\n"
        f"Telegram guruhingizni spam, reklama, flood, havolalar va taqiqlangan so‘zlardan himoya qiladi.\n\n"
        f"🚀 <b>Boshlash uchun:</b>\n"
        f"1️⃣ Botni guruhga qo‘shing\n"
        f"2️⃣ Botga administrator huquqi bering\n"
        f"3️⃣ Guruhda /setup buyrug‘ini yuboring\n\n"
        f"⚡️ <b>Tezkor buyruqlar:</b>\n"
        f"• /setup — guruhni sozlash\n"
        f"• /settings — sozlamalar\n"
        f"• /status — himoya holati\n"
        f"• /help — yordam"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    if not user:
        return

    # Record/update user in database silently
    await firebase_service.save_or_update_user(
        user_id=user.id,
        user_data={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_bot": user.is_bot,
        }
    )

    # 1. Group chat /start check (Requirement #7: brief and contextual)
    if message.chat.type in ("group", "supergroup"):
        await message.reply(
            "⚡️ <b>AnjurXBot faol!</b>\n\n"
            "Guruhni boshqarish uchun buyruqlar:\n"
            "• /settings — barcha sozlamalar paneli\n"
            "• /setup — tezkor sozlash ustasi\n"
            "• /status — joriy himoya holati",
            parse_mode="HTML"
        )
        return

    # 2. Private chat welcome (Requirement #1: concise, actionable UI)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"
    keyboard = get_start_keyboard(bot_username)
    welcome_text = _get_start_text(user.first_name or "")

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    """
    Help command entrypoint (Requirement #5: concise with interactive submenus).
    """
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    help_text = (
        "🤖 <b>AnjurXBot yordam markazi</b>\n\n"
        "⚙️ Guruhni sozlash: <code>/setup</code>\n"
        "🛡 Himoya sozlamalari: <code>/settings</code>\n"
        "📊 Himoya holati: <code>/status</code>\n\n"
        "❓ <b>Batafsil qo‘llanma:</b>\n"
        "Kerakli bo‘limni ko‘rish uchun quyidagi tugmalardan birini tanlang:"
    )
    keyboard = get_help_menu_keyboard(bot_username)
    await message.reply(help_text, reply_markup=keyboard, parse_mode="HTML")


# =====================================================================
# Help & Guide Submenu Callbacks (Requirement #3)
# =====================================================================

@router.callback_query(F.data.in_(["help:menu", "common:help"]))
async def cb_help_menu(callback: CallbackQuery, bot: Bot):
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "📖 <b>AnjurXBot Yordam va Qo‘llanma Markazi</b>\n\n"
        "Kerakli mavzuni tanlang:"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_menu_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:start")
async def cb_help_start(callback: CallbackQuery, bot: Bot):
    """Guide: How to add and activate bot (Requirement #3.1 & #11)."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "🚀 <b>Boshlash — Botni guruhga ulash:</b>\n\n"
        "1️⃣ <b>Guruhga qo‘shing:</b> Pastdagi «➕ Guruhga qo‘shish» tugmasini bosing yoki botni guruh a'zolariga qo‘shing.\n"
        "2️⃣ <b>Admin huquqi bering:</b> Bot xabarlarni o‘chirishi va jazo qo‘llashi uchun unga administrator vakolatlarini bering.\n"
        "3️⃣ <b>Sozlang:</b> Guruh ichida <code>/setup</code> yozing va Standart yoki Qat'iy rejimni tanlang.\n\n"
        "Shundan so‘ng bot guruhni avtomatik ravishda 24/7 himoya qiladi."
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_sub_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:setup")
async def cb_help_setup(callback: CallbackQuery, bot: Bot):
    """Guide: Difference between /setup and /settings (Requirement #3.2 & #6)."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "⚙️ <b>/setup va /settings farqi:</b>\n\n"
        "• <b>/setup</b> — Guruhni birinchi marta tezkor sozlash ustasi.\n"
        "Guruh himoyasini 1 bosish orqali Standart yoki Qat'iy rejimda ishga tushiradi.\n\n"
        "• <b>/settings</b> — Guruhning to‘liq boshqaruv paneli.\n"
        "Anti-Link, Anti-Flood, So‘kish filtri, Mute/Warn va Majburiy obunani alohida yoqish/o‘chirish imkonini beradi.\n\n"
        "<i>Eslatma: Har ikki buyruq xavfsizlik yuzasidan faqat guruh adminlari uchun ishlaydi.</i>"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_sub_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:guard")
async def cb_help_guard(callback: CallbackQuery, bot: Bot):
    """Guide: Guard and moderation filters explained simply (Requirement #3.3 & #14)."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "🛡 <b>Himoya va Moderatsiya tizimi:</b>\n\n"
        "• <b>Anti-Link:</b> Telegram kanallari va har qanday begona havolalarni darhol o‘chiradi.\n"
        "• <b>Anti-Ads:</b> Reklama xabarlari va bot havolalarini tozalaydi.\n"
        "• <b>Anti-Flood:</b> Guruhda juda tez-tez ketma-ket xabar yuborishni cheklaydi.\n"
        "• <b>Anti-Repeat:</b> Bir xil matnni qayta-qayta yuborishni to‘xtatadi.\n"
        "• <b>So‘kish filtri:</b> Haqoratli so‘zlar va 18+ xabarlarni avtomatik o‘chiradi.\n"
        "• <b>Ogohlantirish (Warn):</b> Qoidabuzarlarga ogohlantirish beradi va limit to‘lganda jazolaydi (Mute / Kick / Ban)."
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_sub_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:fsub")
async def cb_help_fsub(callback: CallbackQuery, bot: Bot):
    """Guide: Force Subscribe system (Requirement #3.4)."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "📢 <b>Majburiy Obuna (Force Subscribe):</b>\n\n"
        "Guruh a'zolarini sizning kanallaringizga obuna bo‘lishga undaydi:\n\n"
        "1. Botni kanalingizga administrator etib tayinlang.\n"
        "2. Guruhda <code>/settings</code> → <b>Majburiy obuna</b> bo‘limiga kiring.\n"
        "3. Kanal qo‘shish tugmasini bosib, kanal havolasini yuboring.\n\n"
        "Obuna bo‘lmagan foydalanuvchilar kanallarga a'zo bo‘lmaguncha guruhda xabar yoza olmaydi."
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_sub_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:support")
async def cb_help_support(callback: CallbackQuery, bot: Bot):
    """Guide: Support and Super Admin info (Requirement #3.5)."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "🆘 <b>Yordam va Aloqa markazi:</b>\n\n"
        "Savollar, takliflar yoki texnik nosozliklar bo‘yicha murojaat qilishingiz mumkin:\n\n"
        "👤 <b>Super Administrator:</b> @usafes [8157452043]\n"
        "🛡 <b>Bot yadrosi:</b> AnjurXBot Guard Engine 2026\n"
        "🌐 <b>Veb Boshqaruv:</b> Faol"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_help_sub_keyboard(bot_username),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "help:back_start")
async def cb_help_back_start(callback: CallbackQuery, bot: Bot):
    """Returns to the primary start message."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    user = callback.from_user
    welcome_text = _get_start_text(user.first_name or "")
    keyboard = get_start_keyboard(bot_username)
    try:
        await callback.message.edit_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.message(Command("id", "myid"))
async def cmd_my_id(message: Message):
    """Returns the caller's numeric user ID and current chat ID."""
    user = message.from_user
    if not user:
        return
    un = f"@{user.username}" if user.username else "mavjud emas"
    text = (
        f"🆔 <b>Sizning Telegram ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Username:</b> {un}\n"
        f"💬 <b>Chat ID:</b> <code>{message.chat.id}</code> ({message.chat.type})"
    )
    await message.reply(text, parse_mode="HTML")
