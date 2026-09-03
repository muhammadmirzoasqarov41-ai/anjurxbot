"""
Common inline keyboards used across multiple handlers.

Each function returns a ready-to-send :class:`aiogram.types.InlineKeyboardMarkup`.
Add new keyboard builders here as new features are introduced.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Placeholder main-menu keyboard.

    Will be populated with real buttons when the admin panel is implemented.
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⚙️ Sozlamalar (tez orada)",
            callback_data="settings_soon",
        )
    )
    return builder.as_markup()
