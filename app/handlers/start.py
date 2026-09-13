"""
Start and Help command handlers for AnjurX | Rss Bot.
"""
import logging
from aiogram import Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.config import config
from app.keyboards.rss import get_start_keyboard

logger = logging.getLogger("anjurxbot.start")
router = Router(name="start_router")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    """Welcomes the user and presents AnjurX | Rss Bot commands and features."""
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"
    keyboard = get_start_keyboard(bot_username)

    welcome_text = (
        f"👋 Assalomu alaykum! Men <b>AnjurX | Rss Bot</b>man.\n\n"
        f"Men siz yoqtirgan saytlar, bloglar, yangiliklar va portallardan yangi "
        f"maqolalarni Telegram'ga tezkor va qulay yetkazib beraman.\n\n"
        f"🚀 <b>Asosiy buyruqlar:</b>\n"
        f"• <code>/sub &lt;url&gt;</code> — Yangi RSS/Atom/JSON feedga obuna bo'lish\n"
        f"• <code>/unsub</code> — Obunani bekor qilish (yoki tanlash menyusi)\n"
        f"• <code>/rss</code> — Faol obunalar ro'yxatini ko'rish\n"
        f"• <code>/rss raw</code> — Obunalar havolalarini xom ko'rinishda olish\n"
        f"• <code>/export</code> — Obunalarni OPML fayl sifatida yuklab olish\n"
        f"• <code>/allunsub</code> — Ushbu chatdagi barcha obunalarni o'chirish\n\n"
        f"💡 <b>Qo'shimcha imkoniyatlar:</b>\n"
        f"• Sayt linkini yuborsangiz, RSS feed avtomatik aniqlanadi.\n"
        f"• Botni <b>Guruhlar</b> va <b>Kanallar</b>ga qo'shib, yangiliklarni ularga avtomatik joylab borishingiz mumkin!\n"
        f"• .OPML fayl yuborib, o'nlab feedlarga bir zumda ommaviy obuna bo'lishingiz mumkin."
    )

    await message.answer(
        welcome_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    """Provides detailed help about bot usage."""
    await cmd_start(message, bot)
