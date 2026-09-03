"""
/start command handler.

- Private chat + global admin → show admin panel
- Private chat + regular user → show regular welcome
- Group chat → silent (or minimal response)
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from app.config import settings
from app.utils.logger import logger
from app.services.rate_limit_service import rate_limit_service

router = Router(name="start")

WELCOME_TEXT = (
    "👋 Assalomu alaykum!\n\n"
    "Men guruhlar uchun xavfsizlik va moderatsiya botiman.\n\n"
    "🛡 Qorovul\n"
    "📢 Majburiy obuna\n"
    "🚫 Spam himoyasi\n"
    "🔗 Link nazorati\n"
    "⚠️ Ogohlantirish tizimi\n\n"
    "Botni guruhga administrator qilib qo'shing va /setup orqali sozlang."
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if user_id is not None and not rate_limit_service.allow("start", user_id, 5, 30.0):
        await message.answer("⏳ Juda ko'p so'rov yuborildi. Biroz kuting.")
        return
    chat_type = message.chat.type
    logger.info("/start user_id=%s chat=%s type=%s", user_id, message.chat.id, chat_type)

    if chat_type == "private" and user_id and settings.is_admin(user_id):
        # Show admin panel
        from app.handlers.admin_helpers import build_main_text
        from app.keyboards.admin import admin_main_keyboard
        name = message.from_user.first_name if message.from_user else "Admin"
        text = await build_main_text(name)
        await message.answer(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")
    else:
        await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    from app.handlers.admin_helpers import build_help_text
    await message.answer(await build_help_text(), parse_mode="HTML")
