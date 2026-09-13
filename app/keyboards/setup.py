"""
Quick setup wizard keyboards for AnjurXBot Qorovul.
Provides direct ON/OFF toggles for core guard filters and preset modes.
"""
from typing import Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_close_button


def _st(val: bool) -> str:
    return "🟢 Yoqilgan" if val else "🔴 O'chirilgan"


def get_setup_wizard_keyboard(group_id: int, guard: Optional[Dict[str, Any]] = None) -> InlineKeyboardMarkup:
    gid = str(group_id)
    g = guard or {}
    
    anti_spam = bool(g.get("anti_spam", True))
    anti_flood = bool(g.get("anti_flood", True))
    anti_link = bool(g.get("anti_link", True))
    anti_ads = bool(g.get("anti_ads", True))
    bad_words = bool(g.get("bad_words_filter", True))
    raid = bool(g.get("raid_protection", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"🛡 Anti-Spam — {_st(anti_spam)}",
                callback_data=f"setup:toggle:{gid}:anti_spam"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"⚡ Anti-Flood — {_st(anti_flood)}",
                callback_data=f"setup:toggle:{gid}:anti_flood"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔗 Anti-Link — {_st(anti_link)}",
                callback_data=f"setup:toggle:{gid}:anti_link"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"📢 Anti-Ads — {_st(anti_ads)}",
                callback_data=f"setup:toggle:{gid}:anti_ads"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🤬 So'kish filtri — {_st(bad_words)}",
                callback_data=f"setup:toggle:{gid}:bad_words_filter"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🤖 Raid himoyasi — {_st(raid)}",
                callback_data=f"setup:toggle:{gid}:raid_protection"
            ),
        ],
        [
            InlineKeyboardButton(text="⚡️ Standart rejim", callback_data=f"setup:preset:default:{gid}"),
            InlineKeyboardButton(text="🔒 Qat'iy rejim", callback_data=f"setup:preset:strict:{gid}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ To'liq sozlamalar (/settings)", callback_data=f"settings:menu:{gid}"),
            get_close_button(),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# Alias for backward compatibility
get_setup_keyboard = get_setup_wizard_keyboard
