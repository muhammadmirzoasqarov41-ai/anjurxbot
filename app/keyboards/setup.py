"""
Quick setup wizard keyboards.
Provides one-touch preset configuration and fast jumping to granular settings.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_close_button


def get_setup_wizard_keyboard(group_id: int) -> InlineKeyboardMarkup:
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(text="⚡️ Standart rejim (Tavsiya etiladi)", callback_data=f"setup:preset:default:{gid}"),
        ],
        [
            InlineKeyboardButton(text="🔒 Qat'iy rejim (Maksimal himoya)", callback_data=f"setup:preset:strict:{gid}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Barcha sozlamalar (/settings)", callback_data=f"settings:menu:{gid}"),
        ],
        [
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Alias for backward compatibility
get_setup_keyboard = get_setup_wizard_keyboard
