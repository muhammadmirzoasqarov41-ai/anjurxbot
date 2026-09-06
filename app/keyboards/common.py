"""
Common inline keyboards and utility buttons.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_back_button(callback_data: str = "admin:menu") -> InlineKeyboardButton:
    return InlineKeyboardButton(text="◀️ Orqaga", callback_data=callback_data)


def get_close_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text="❌ Yopish", callback_data="common:close")


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str,
    extra_buttons: list = None
) -> InlineKeyboardMarkup:
    buttons = []
    nav_row = []

    if current_page > 1:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"{prefix}:page:{current_page - 1}")
        )
    
    nav_row.append(
        InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data=f"{prefix}:current")
    )

    if current_page < total_pages:
        nav_row.append(
            InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"{prefix}:page:{current_page + 1}")
        )

    if nav_row:
        buttons.append(nav_row)

    if extra_buttons:
        for row in extra_buttons:
            buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)
