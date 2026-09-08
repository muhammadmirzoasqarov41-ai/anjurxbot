"""
Inline keyboards for /settings (Group Settings UX).
Scoped strictly to group_id for secure, compartmentalized configuration.
"""
from typing import Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _status_icon(value: bool) -> str:
    return "✅ Yoqilgan" if value else "❌ O'chirilgan"


def get_group_settings_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Main clean, high-level menu for /settings command."""
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(
                text="🛡 Moderatsiya (Link, Spam, Reklama)",
                callback_data=f"settings:guard:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔒 Xavfsizlik (Flood, So'kish filtri)",
                callback_data=f"settings:sec:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔔 Ogohlantirish va Jazo tizimi",
                callback_data=f"settings:warns:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📢 Majburiy obuna (Kanallarni ulash)",
                callback_data=f"settings:fsub:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="👋 Xizmat xabarlari (Kirdi/Chiqdi tozalash)",
                callback_data=f"settings:srv:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚡️ Tezkor rejimlar (Standart / Qat'iy)",
                callback_data=f"settings:presets:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data=f"settings:stats:{gid}"
            ),
            InlineKeyboardButton(
                text="❌ Yopish",
                callback_data="common:close"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_guard_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Moderation sub-menu: Links, Spam, Ads."""
    gid = str(group_id)
    anti_link = bool(guard.get("anti_link", True))
    anti_spam = bool(guard.get("anti_spam", True))
    anti_ads = bool(guard.get("anti_ads", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Havolalar (Anti-Link): {_status_icon(anti_link)}",
                callback_data=f"guard:toggle:{gid}:anti_link:guard"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Spam (Anti-Spam): {_status_icon(anti_spam)}",
                callback_data=f"guard:toggle:{gid}:anti_spam:guard"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Reklama (Anti-Ads): {_status_icon(anti_ads)}",
                callback_data=f"guard:toggle:{gid}:anti_ads:guard"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_sec_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Security sub-menu: Flood, Bad words, Anti-repeat."""
    gid = str(group_id)
    anti_flood = bool(guard.get("anti_flood", True))
    anti_repeat = bool(guard.get("anti_repeat", True))
    bad_words_filter = bool(guard.get("bad_words_filter", True))
    flood_limit = guard.get("flood_limit", 5)
    flood_window = guard.get("flood_window", 5)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Flood himoyasi: {_status_icon(anti_flood)}",
                callback_data=f"guard:toggle:{gid}:anti_flood:sec"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Qayta xabar (Anti-Repeat): {_status_icon(anti_repeat)}",
                callback_data=f"guard:toggle:{gid}:anti_repeat:sec"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"So'kish va 18+ filtri: {_status_icon(bad_words_filter)}",
                callback_data=f"guard:toggle:{gid}:bad_words_filter:sec"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🔢 Flood tezligi: {flood_limit} xabar / {flood_window}s",
                callback_data=f"guard:threshold:{gid}:flood:sec"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Taqiqlangan so'zlar ro'yxati",
                callback_data=f"guard:words:{gid}:sec"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_warns_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Warnings and punishment sub-menu."""
    gid = str(group_id)
    warn_limit = guard.get("warn_limit", 3)
    punishment = str(guard.get("punishment", "mute")).upper()

    punish_labels = {
        "MUTE": "Ovozni o'chirish (Mute)",
        "KICK": "Guruhdan chiqarish (Kick)",
        "BAN": "Guruhdan haydash (Ban)",
    }
    punish_str = punish_labels.get(punishment, punishment)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"⚠️ Ogohlantirish chegarasi: {warn_limit} ta",
                callback_data=f"guard:threshold:{gid}:warn:warns"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"🚫 Limit to'lgandagi jazo: {punish_str}",
                callback_data=f"guard:cycle_punishment:{gid}:warns"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_srv_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Service messages sub-menu."""
    gid = str(group_id)
    delete_service = bool(guard.get("delete_service_messages", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Kirdi/Chiqdi xabarlarini tozalash: {_status_icon(delete_service)}",
                callback_data=f"guard:toggle:{gid}:delete_service_messages:srv"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_presets_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Presets sub-menu."""
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(
                text="⚡️ Standart rejim (Link, Spam, Reklama faol)",
                callback_data=f"setup:preset:default:{gid}:presets"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔒 Qat'iy rejim (Barcha filtrlar + So'kish filtri)",
                callback_data=f"setup:preset:strict:{gid}:presets"
            ),
        ],
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
