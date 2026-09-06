"""
Admin panel keyboards.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_close_button


def get_admin_panel_keyboard(group_id: int = 0) -> InlineKeyboardMarkup:
    gid_str = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(text="🛡 Himoya (Guard)", callback_data=f"guard:menu:{gid_str}"),
            InlineKeyboardButton(text="📢 Majburiy obuna", callback_data=f"fsub:menu:{gid_str}"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data=f"admin:stats:{gid_str}"),
            InlineKeyboardButton(text="⚠️ Ogohlantirishlar", callback_data=f"admin:warns:{gid_str}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data=f"setup:menu:{gid_str}"),
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_global_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Umumiy statistika", callback_data="global:stats"),
            InlineKeyboardButton(text="👥 Guruhlar ro'yxati", callback_data="global:groups:1"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="global:broadcast"),
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
