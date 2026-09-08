"""
Admin helper utilities for callback authorization and validation.
"""
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import CallbackQuery
from app.services.permission_service import permission_service
from app.config import config


async def verify_admin_callback(
    callback: CallbackQuery,
    bot: Bot,
    group_id: int
) -> bool:
    """
    Ensures that the user pressing the button is an authorized group admin or bot superadmin.
    Strictly verifies Telegram numeric user_id.
    """
    user_id = callback.from_user.id if callback.from_user else 0
    if not user_id:
        await callback.answer("❌ Foydalanuvchi aniqlanmadi.", show_alert=True)
        return False

    # Super Admin has global override strictly by ID
    if config.is_super_admin(user_id):
        return True

    chat = callback.message.chat if callback.message else None
    is_admin = await permission_service.is_user_admin(
        bot,
        group_id,
        user_id,
        chat=chat
    )
    if not is_admin:
        await callback.answer(
            "⛔ Bu bo‘lim faqat guruh egasi va administratorlari uchun ruxsat etilgan.",
            show_alert=True
        )
        return False

    return True


def extract_group_id_from_callback(callback_data: str, default: int = 0) -> int:
    try:
        parts = callback_data.split(":")
        # Find numeric part
        for part in reversed(parts):
            if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
                return int(part)
    except Exception:
        pass
    return default
