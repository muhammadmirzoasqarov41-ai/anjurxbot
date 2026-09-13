"""
Admin and Settings keyboards for Group Admins and Super Admin.
"""
from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_close_button, get_back_button


def get_admin_panel_keyboard(group_id: int = 0) -> InlineKeyboardMarkup:
    """Group Settings main menu keyboard."""
    gid_str = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(text="🛡 Qorovul Himoyasi", callback_data=f"guard:menu:{gid_str}"),
            InlineKeyboardButton(text="⚠️ Ogohlantirishlar (Warn)", callback_data=f"admin:warns:{gid_str}"),
        ],
        [
            InlineKeyboardButton(text="📊 Guruh statistikasi", callback_data=f"admin:stats:{gid_str}"),
            InlineKeyboardButton(text="⚡️ Tezkor sozlash", callback_data=f"setup:menu:{gid_str}"),
        ],
        [
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Alias for clarity
get_group_settings_keyboard = get_admin_panel_keyboard


def get_back_to_settings_keyboard(group_id: int = 0) -> InlineKeyboardMarkup:
    """Simple Back button keyboard returning to group settings."""
    gid_str = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"admin:panel:{gid_str}"),
            get_close_button(),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_global_admin_keyboard() -> InlineKeyboardMarkup:
    """Super Admin Panel main keyboard (accessible only by Super Admin ID)."""
    keyboard = [
        [
            InlineKeyboardButton(text="📊 Umumiy statistika", callback_data="global:stats"),
            InlineKeyboardButton(text="👥 Guruhlar", callback_data="global:groups:1"),
        ],
        [
            InlineKeyboardButton(text="👤 Foydalanuvchilar", callback_data="global:users:1"),
            InlineKeyboardButton(text="🛠 Texnik holat", callback_data="global:health"),
        ],
        [
            InlineKeyboardButton(text="🗄 Firebase holati", callback_data="global:firebase"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="global:broadcast"),
        ],
        [
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_global_keyboard() -> InlineKeyboardMarkup:
    """Simple Back button keyboard returning to Super Admin Panel."""
    keyboard = [
        [
            InlineKeyboardButton(text="◀️ Orqaga", callback_data="global:menu"),
            get_close_button(),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

