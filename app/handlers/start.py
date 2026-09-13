"""
Start and Help Command Handlers for AnjurXBot (Qorovul).
Focused purely on group protection and guard architecture.
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
    """Returns the primary concise and professional welcome message for Qorovul."""
    clean_name = user_name.replace("<", "&lt;").replace(">", "&gt;") if user_name else "Foydalanuvchi"
    return (
        f"Assalomu alaykum, <b>{clean_name}</b>! 👋\n\n"
        f"🛡 <b>AnjurXBot — guruhingizning Qorovuli.</b>\n\n"
        f"Spam, reklama, flood, havola va taqiqlangan so‘zlarni nazorat qiladi hamda guruh tartibini saqlashga yordam beradi.\n\n"
        f"🚀 <b>Boshlash:</b>\n"
        f"1️⃣ Botni guruhga qo‘shing\n"
        f"2️⃣ Administrator qiling\n"
        f"3️⃣ Guruhda /setup buyrug‘ini yuboring\n\n"
        f"⚡️ <b>Tezkor buyruqlar:</b>\n"
        f"• /setup — Qorovulni sozlash\n"
        f"• /settings — Himoya sozlamalari\n"
        f"• /status — Qorovul holati\n"
        f"• /help — Yordam"
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

    # 1. Group chat /start check (brief and contextual)
    if message.chat.type in ("group", "supergroup"):
        await message.reply(
            "⚡️ <b>AnjurXBot — Qorovul faol!</b>\n\n"
            "Guruhni boshqarish uchun buyruqlar:\n"
            "• /setup — Qorovulni sozlash ustasi\n"
            "• /settings — himoya sozlamalari paneli\n"
            "• /status — Qorovul holati",
            parse_mode="HTML"
        )
        return

    # 2. Private chat welcome (clean, focused Qorovul UX)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"
    keyboard = get_start_keyboard(bot_username)
    welcome_text = _get_start_text(user.first_name or "")

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    """
    Help command entrypoint for Qorovul.
    """
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    help_text = (
        "🛡 <b>AnjurXBot Qorovul yordam markazi</b>\n\n"
        "⚙️ Qorovulni sozlash: <code>/setup</code>\n"
        "🛡 Himoya sozlamalari: <code>/settings</code>\n"
        "📊 Qorovul holati: <code>/status</code>\n\n"
        "❓ <b>Batafsil qo‘llanma:</b>\n"
        "Quyidagi bo‘limlardan birini tanlang:"
    )
    keyboard = get_help_menu_keyboard(bot_username)
    await message.reply(help_text, reply_markup=keyboard, parse_mode="HTML")


# =====================================================================
# Qorovul Help & Guide Submenu Callbacks
# =====================================================================

@router.callback_query(F.data.in_(["help:menu", "common:help"]))
async def cb_help_menu(callback: CallbackQuery, bot: Bot):
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "📖 <b>AnjurXBot Qorovul Yordam Markazi</b>\n\n"
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
    """Guide: How to add and activate Qorovul."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "🛡 <b>Qorovul nima va qanday ishlaydi?</b>\n\n"
        "AnjurXBot — Telegram guruhingizni avtomatik ravishda 24/7 himoya qiluvchi xavfsizlik tizimi.\n\n"
        "🚀 <b>Guruhga ulash tartibi:</b>\n"
        "1️⃣ <b>Guruhga qo‘shing:</b> «➕ Guruhga qo‘shish» tugmasini bosing.\n"
        "2️⃣ <b>Admin huquqi bering:</b> Bot xabarlarni o‘chirishi va jazolarni qo‘llashi uchun unga administrator vakolatlarini bering.\n"
        "3️⃣ <b>Sozlang:</b> Guruh ichida <code>/setup</code> yozing va himoya filtrlari faollashtiring.\n\n"
        "Shundan so‘ng bot guruhdagi barcha kirdi-chiqdi, spam, reklama va havolalarni darhol bartaraf etadi."
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
    """Guide: Difference between /setup and /settings."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "⚙️ <b>Guruhni sozlash: /setup va /settings farqi:</b>\n\n"
        "• <b>/setup</b> — Guruhni birinchi marta tezkor sozlash ustasi.\n"
        "Anti-Spam, Anti-Flood, Anti-Link, Anti-Ads va Taqiqlangan so‘zlarni bir bosishda yoqish imkonini beradi.\n\n"
        "• <b>/settings</b> — Qorovulning to‘liq boshqaruv markazi.\n"
        "Har bir filtr chegarasini (flood tezligi, ogohlantirish soni, jazo turi) alohida nozik sozlash imkonini beradi.\n\n"
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


@router.callback_query(F.data == "help:links")
async def cb_help_links(callback: CallbackQuery, bot: Bot):
    """Guide: Links, Spam, Ads protection."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "🔗 <b>Anti-Link, Anti-Spam va Anti-Ads himoyasi:</b>\n\n"
        "• <b>Anti-Link:</b> Telegram kanallari (t.me/...), guruh havolalari va har qanday begona veb-sayt havolalarini darhol o‘chiradi.\n"
        "• <b>Anti-Ads:</b> Reklama xabarlari, referal havolalar va bot havolalarini avtomatik aniqlab tozalaydi.\n"
        "• <b>Anti-Spam:</b> Qaytalanuvchi xabarlar va spam xabarlarni guruhdan yo‘qotadi.\n\n"
        "<i>Sozlash uchun guruhda /settings buyrug‘idan foydalaning.</i>"
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


@router.callback_query(F.data == "help:flood")
async def cb_help_flood(callback: CallbackQuery, bot: Bot):
    """Guide: Anti-flood and Bad words."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "⚡ <b>Anti-Flood va Taqiqlangan So‘zlar:</b>\n\n"
        "• <b>Anti-Flood:</b> Bir foydalanuvchi qisqa vaqt ichida ketma-ket xabar yuborsa (standart: 5 soniyada 5 ta xabar), bot avtomatik cheklov qo‘yadi.\n"
        "• <b>Anti-Repeat:</b> Bir xil matnni qayta-qayta yuboruvchi xabarlarni to‘xtatadi.\n"
        "• <b>Taqiqlangan so‘zlar (Bad Words):</b> Haqoratli so‘zlar, 18+ va odobsiz so‘zlarni avtomatik o‘chiradi.\n"
        "Adminlar o‘z guruhiga xos qo‘shimcha so‘zlar ro‘yxatini ham kiritishlari mumkin."
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


@router.callback_query(F.data == "help:moderation")
async def cb_help_moderation(callback: CallbackQuery, bot: Bot):
    """Guide: Warnings, Mute, Kick, Ban."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "👮 <b>Moderatsiya: Warn, Mute va Ban tizimi:</b>\n\n"
        "• <b>Ogohlantirish (Warn):</b> Qoidabuzarga avtomatik ogohlantirish beriladi. Belgilangan limit (masalan, 3 ta) to‘lganda jazo belgilanadi.\n"
        "• <b>Ovozni o‘chirish (Mute):</b> Qoidabuzar ma'lum muddatga guruhda yozish huquqidan mahrum qilinadi.\n"
        "• <b>Guruhdan haydash (Ban):</b> Eng qat'iy jazo — a'zo guruhdan butunlay chetlatiladi.\n\n"
        "Adminlar quyidagi tezkor buyruqlardan foydalanishi mumkin (xabarga reply qilib):\n"
        "• <code>/warn</code> — ogohlantirish berish\n"
        "• <code>/mute 10m</code> — 10 daqiqaga ovozni o‘chirish\n"
        "• <code>/unmute</code> — ovoz cheklovini bekor qilish"
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
    """Guide: Support and Troubleshooting."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "❓ <b>Muammolarni hal qilish va Aloqa:</b>\n\n"
        "<b>Bot xabarlarni o‘chirmayaptimi?</b>\n"
        "1. Bot guruhda Administrator ekanini tekshiring.\n"
        "2. Botga «Xabarlarni o‘chirish» (Delete messages) va «Foydalanuvchilarni cheklash» (Restrict members) huquqi berilganiga ishonch hosil qiling.\n"
        "3. Guruhda <code>/setup</code> yoki <code>/settings</code> orqali filtrlar yoqilganini tekshiring.\n\n"
        "👤 <b>Super Administrator:</b> @usafes [8157452043]\n"
        "🛡 <b>Qorovul dvigateli:</b> AnjurXBot Guard Engine"
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
