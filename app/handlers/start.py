"""
Start and Help Command Handlers.
"""
from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.firebase import firebase_service
from app.config import config

router = Router(name="start_router")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    user = message.from_user
    if not user:
        return

    # Record user in database
    await firebase_service.save_or_update_user(
        user_id=user.id,
        user_data={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_bot": user.is_bot,
        }
    )

    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    if message.chat.type in ("group", "supergroup"):
        await message.reply(
            f"🛡 <b>{bot_info.first_name}</b> guruhda faol!\n\n"
            f"Bot to'liq ishlashi uchun unga guruhda <b>Administrator</b> huquqlarini bering.\n"
            f"Sozlamalar paneli uchun: /panel yoki /guard buyrug'ini yuboring.",
            parse_mode="HTML"
        )
        return

    # Private chat welcome
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=f"https://t.me/{bot_username}?startgroup=true"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆘 Yordam va Qo'llanma",
                    callback_data="common:help"
                )
            ]
        ]
    )

    welcome_text = (
        f"Assalomu alaykum, <b>{user.first_name}</b>!\n\n"
        f"🤖 <b>AnjurXBot</b> — Telegram guruhlarini spam, reklama, flood, havolalar "
        f"va haqoratlardan himoya qiluvchi, shuningdek majburiy obuna (Force Subscribe) "
        f"tizimini ta'minlovchi professional botdir.\n\n"
        f"⚡️ <b>Asosiy imkoniyatlar:</b>\n"
        f"• Anti-Link & Anti-Ads (Havola va reklamalarni tozalash)\n"
        f"• Anti-Flood (Tez-tez yozishdan himoya)\n"
        f"• Majburiy kanallarga obunani nazorat qilish\n"
        f"• So'kinish va taqiqlangan so'zlar filtri\n"
        f"• Avtomatik ogohlantirish (warn) va mute/ban tizimi\n\n"
        f"Guruhga qo'shib, admin qiling va /setup buyrug'ini bosing!"
    )

    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 <b>AnjurXBot Buyruqlar Qo'llanmasi:</b>\n\n"
        "<b>Guruh adminlari uchun:</b>\n"
        "• /panel — Asosiy boshqaruv paneli\n"
        "• /guard — Himoya va filtr sozlamalari\n"
        "• /fsub — Majburiy obuna sozlamalari\n"
        "• /setup — Tezkor sozlash ustasi\n"
        "• /warn — Foydalanuvchiga ogohlantirish berish (reply orqali)\n"
        "• /mute — Foydalanuvchini vaqtincha ovozini o'chirish (reply orqali)\n"
        "• /unmute — Ovoz cheklovini bekor qilish (reply orqali)\n\n"
        "<b>Bot boshqaruvchilari uchun:</b>\n"
        "• /admin — Global statistikalar va tizim holati"
    )
    await message.reply(help_text, parse_mode="HTML")
