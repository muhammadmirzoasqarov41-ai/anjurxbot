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
    """
    user_id = callback.from_user.id
    if config.is_admin(user_id):
        return True

    is_admin = await permission_service.is_user_admin(bot, group_id, user_id)
    if not is_admin:
        await callback.answer("❌ Bu amal faqat guruh adminlari uchun ruxsat etilgan!", show_alert=True)
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
