"""
Quick setup wizard keyboards.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_close_button, get_back_button


def get_setup_wizard_keyboard(group_id: int) -> InlineKeyboardMarkup:
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(text="⚡️ Standart himoyani yoqish", callback_data=f"setup:preset:default:{gid}"),
        ],
        [
            InlineKeyboardButton(text="🔒 Qat'iy himoyani yoqish", callback_data=f"setup:preset:strict:{gid}"),
        ],
        [
            InlineKeyboardButton(text="🎛 Maxsus sozlash", callback_data=f"guard:menu:{gid}"),
        ],
        [
            get_back_button(f"admin:panel:{gid}"),
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Alias for backward compatibility
get_setup_keyboard = get_setup_wizard_keyboard
