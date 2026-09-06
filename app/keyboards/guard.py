"""
Guard settings keyboards for group protection.
"""
from typing import Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_back_button


def get_guard_settings_keyboard(group_id: int, settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    gid = str(group_id)

    def status_icon(key: str, default: bool = True) -> str:
        return "✅" if settings.get(key, default) else "❌"

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{status_icon('anti_link', True)} Havolalar (Link)",
                callback_data=f"guard:toggle:{gid}:anti_link",
            ),
            InlineKeyboardButton(
                text=f"{status_icon('anti_spam', True)} Spam",
                callback_data=f"guard:toggle:{gid}:anti_spam",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{status_icon('anti_flood', True)} Flood",
                callback_data=f"guard:toggle:{gid}:anti_flood",
            ),
            InlineKeyboardButton(
                text=f"{status_icon('anti_ads', True)} Reklama (Ads)",
                callback_data=f"guard:toggle:{gid}:anti_ads",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{status_icon('anti_repeat', True)} Qayta xabar",
                callback_data=f"guard:toggle:{gid}:anti_repeat",
            ),
            InlineKeyboardButton(
                text=f"{status_icon('bad_words_filter', True)} So'kish filtri",
                callback_data=f"guard:toggle:{gid}:bad_words_filter",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔢 Flood chegarasi: {settings.get('flood_limit', 5)}/{settings.get('flood_window', 5)}s",
                callback_data=f"guard:threshold:{gid}:flood",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"⚠️ Ogohlantirish chegarasi: {settings.get('warn_limit', 3)}",
                callback_data=f"guard:threshold:{gid}:warn",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🚫 Jazo turi: {settings.get('punishment', 'mute').upper()}",
                callback_data=f"guard:cycle_punishment:{gid}",
            ),
        ],
        [
            InlineKeyboardButton(text="📝 Taqiqlangan so'zlar", callback_data=f"guard:words:{gid}"),
            get_back_button(f"admin:panel:{gid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
