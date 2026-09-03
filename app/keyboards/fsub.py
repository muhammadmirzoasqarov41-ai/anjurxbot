"""
Inline keyboards for the Force Subscribe feature.

All keyboard builder functions live here.
Handlers import these functions and never build InlineKeyboardMarkup inline.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def fsub_keyboard(
    channels: list[dict],
    user_id: int,
    chat_id: int,
) -> InlineKeyboardMarkup:
    """
    Build the Force Subscribe inline keyboard.

    Layout:
        [ 📢 Channel 1 name ]   ← url button
        [ 📢 Channel 2 name ]   ← url button
        …
        [ ✅ Obunani tekshirish ]  ← callback button

    Args:
        channels: List of channel dicts with keys: channel_id, title,
                  username, invite_link.
        user_id:  Telegram user ID (embedded in callback_data for security).
        chat_id:  Telegram chat ID (embedded in callback_data).
    """
    builder = InlineKeyboardBuilder()

    for ch in channels:
        title = ch.get("title") or "Kanal"
        url = _channel_url(ch)
        if url:
            builder.row(
                InlineKeyboardButton(
                    text=f"📢 {title}",
                    url=url,
                )
            )

    # Verify button — encodes user_id + chat_id so we can validate ownership
    callback_data = f"fsub_check:{user_id}:{chat_id}"
    builder.row(
        InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data=callback_data,
        )
    )

    return builder.as_markup()


def _channel_url(ch: dict) -> str:
    """
    Derive a clickable t.me URL for *ch*.

    Priority: username → invite_link → empty string (button skipped by caller).
    """
    username: str = ch.get("username", "")
    invite_link: str = ch.get("invite_link", "")

    if username:
        username = username.lstrip("@")
        return f"https://t.me/{username}"
    if invite_link:
        return invite_link
    return ""
