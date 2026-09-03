"""
Guard inline keyboards.

Provides the /guard panel keyboard and toggle helpers.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Map of feature key -> display label
GUARD_FEATURES: dict[str, str] = {
    "anti_spam": "🛡 Spam",
    "anti_flood": "🌊 Flood",
    "anti_link": "🔗 Link",
    "anti_ads": "📢 Reklama",
    "anti_repeat": "🔁 Takroriy xabar",
    "bad_words": "🚫 So'z filtri",
    "new_member_protection": "👤 Yangi a'zolar",
}


def guard_panel_keyboard(
    guard: dict,
    chat_id: int,
) -> InlineKeyboardMarkup:
    """
    Build the /guard inline panel.

    Each feature gets a toggle button showing current ON/OFF status.
    Buttons are laid out in pairs (2 per row) except the last row.
    """
    builder = InlineKeyboardBuilder()

    items = list(GUARD_FEATURES.items())
    for i in range(0, len(items), 2):
        row_buttons: list[InlineKeyboardButton] = []
        for key, label in items[i : i + 2]:
            is_on = guard.get(key, False)
            status = "✅" if is_on else "❌"
            row_buttons.append(
                InlineKeyboardButton(
                    text=f"{label}: {status}",
                    callback_data=f"guard_toggle:{chat_id}:{key}",
                )
            )
        builder.row(*row_buttons)

    # Master ON/OFF toggle
    master = guard.get("enabled", False)
    master_label = "🟢 Qorovulni O'CHIRISH" if master else "🔴 Qorovulni YOQISH"
    builder.row(
        InlineKeyboardButton(
            text=master_label,
            callback_data=f"guard_master:{chat_id}:{'off' if master else 'on'}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="❌ Yopish", callback_data="guard_close")
    )

    return builder.as_markup()
