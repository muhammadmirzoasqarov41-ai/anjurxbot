"""Inline keyboards for the group setup wizard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def setup_keyboard(group_id: int, user_id: int) -> InlineKeyboardMarkup:
    prefix = f"setup:{group_id}:{user_id}"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔐 Permissionlarni tekshirish", callback_data=f"{prefix}:perm"))
    builder.row(
        InlineKeyboardButton(text="📢 Majburiy obunani sozlash", callback_data=f"{prefix}:fsub"),
        InlineKeyboardButton(text="🛡 Qorovulni sozlash", callback_data=f"{prefix}:guard"),
    )
    builder.row(InlineKeyboardButton(text="🧪 Tizimni test qilish", callback_data=f"{prefix}:test"))
    builder.row(
        InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"{prefix}:refresh"),
        InlineKeyboardButton(text="✅ Tayyor", callback_data=f"{prefix}:done"),
    )
    return builder.as_markup()