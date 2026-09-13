"""
Inline keyboards for /settings (Group Settings UX).
Built for AnjurXBot Qorovul: intuitive, clean, fast, and easy to use.
"""
from typing import Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def _status_icon(value: bool) -> str:
    return "🟢 Yoqilgan" if value else "🔴 O'chirilgan"


def get_group_settings_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """
    Main clean, high-level menu for /settings command matching:
    [ 🛡 Umumiy himoya ]
    [ 🚫 Spam ] [ 🌊 Flood ]
    [ 🔗 Link ] [ 📢 Reklama ]
    [ 🤬 Yomon so‘zlar ] [ 🤖 Raid himoyasi ]
    [ ⚠️ Warn tizimi ] [ 🔇 Mute ]
    [ 🔨 Ban ] [ 📊 Statistika ]
    [ ⚡️ Tezkor sozlash ] [ ❌ Yopish ]
    """
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(
                text="🛡 Umumiy himoya",
                callback_data=f"settings:general:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🚫 Spam",
                callback_data=f"settings:spam:{gid}"
            ),
            InlineKeyboardButton(
                text="🌊 Flood",
                callback_data=f"settings:flood:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔗 Link",
                callback_data=f"settings:link:{gid}"
            ),
            InlineKeyboardButton(
                text="📢 Reklama",
                callback_data=f"settings:ads:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🤬 Yomon so‘zlar",
                callback_data=f"settings:badwords:{gid}"
            ),
            InlineKeyboardButton(
                text="🤖 Raid himoyasi",
                callback_data=f"settings:raid:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚠️ Warn tizimi",
                callback_data=f"settings:warns:{gid}"
            ),
            InlineKeyboardButton(
                text="🔇 Mute",
                callback_data=f"settings:mute:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔨 Ban",
                callback_data=f"settings:ban:{gid}"
            ),
            InlineKeyboardButton(
                text="📊 Statistika",
                callback_data=f"settings:stats:{gid}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⚡️ Tezkor sozlash",
                callback_data=f"settings:presets:{gid}"
            ),
            InlineKeyboardButton(
                text="❌ Yopish",
                callback_data="common:close"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_general_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """General guard settings sub-menu."""
    gid = str(group_id)
    new_member = bool(guard.get("new_member_protection", True))
    delete_service = bool(guard.get("delete_service_messages", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Yangi a'zolar nazorati: {_status_icon(new_member)}",
                callback_data=f"guard:toggle:{gid}:new_member_protection:general"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Kirdi/Chiqdi xabarlari: {_status_icon(delete_service)}",
                callback_data=f"guard:toggle:{gid}:delete_service_messages:general"
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


def get_settings_spam_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Anti-spam sub-menu."""
    gid = str(group_id)
    anti_spam = bool(guard.get("anti_spam", True))
    anti_repeat = bool(guard.get("anti_repeat", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Spam xabarlarini bloklash: {_status_icon(anti_spam)}",
                callback_data=f"guard:toggle:{gid}:anti_spam:spam"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Bir xil xabarni qaytarish (Anti-Repeat): {_status_icon(anti_repeat)}",
                callback_data=f"guard:toggle:{gid}:anti_repeat:spam"
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


def get_settings_flood_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Anti-flood sub-menu."""
    gid = str(group_id)
    anti_flood = bool(guard.get("anti_flood", True))
    flood_limit = guard.get("flood_limit", 5)
    flood_window = guard.get("flood_window", 5)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Anti-Flood himoyasi: {_status_icon(anti_flood)}",
                callback_data=f"guard:toggle:{gid}:anti_flood:flood"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Nechta xabardan keyin? ({flood_limit} ta / {flood_window}s)",
                callback_data=f"guard:cycle_flood:{gid}:flood"
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


def get_settings_link_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Anti-link sub-menu."""
    gid = str(group_id)
    anti_link = bool(guard.get("anti_link", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Linklarni bloklash: {_status_icon(anti_link)}",
                callback_data=f"guard:toggle:{gid}:anti_link:link"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌐 Ruxsat etilgan saytlar (YouTube, Insta...)",
                callback_data=f"guard:allowed_domains:{gid}:link"
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


def get_settings_ads_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Anti-ads sub-menu."""
    gid = str(group_id)
    anti_ads = bool(guard.get("anti_ads", True))

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Reklama xabarlarini bloklash: {_status_icon(anti_ads)}",
                callback_data=f"guard:toggle:{gid}:anti_ads:ads"
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


def get_settings_badwords_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Bad words sub-menu."""
    gid = str(group_id)
    bad_words_filter = bool(guard.get("bad_words_filter", True))
    action = guard.get("bad_words_action", "delete")
    action_labels = {
        "delete": "🗑 O'chirish",
        "warn": "⚠️ Ogohlantirish",
        "mute": "🔇 Ovozni o'chirish (Mute)",
    }
    action_text = action_labels.get(action, "🗑 O'chirish")

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"So'kish va 18+ filtri: {_status_icon(bad_words_filter)}",
                callback_data=f"guard:toggle:{gid}:bad_words_filter:badwords"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Qoidani buzsa: {action_text}",
                callback_data=f"guard:cycle_bad_action:{gid}:badwords"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📝 Taqiqlangan so'zlar ro'yxati",
                callback_data=f"guard:words:{gid}:badwords"
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


def get_settings_raid_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Raid protection sub-menu."""
    gid = str(group_id)
    raid_protection = bool(guard.get("raid_protection", True))
    thresh = guard.get("raid_threshold", 10)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Raid himoyasi: {_status_icon(raid_protection)}",
                callback_data=f"guard:toggle:{gid}:raid_protection:raid"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"Sezgirlik: {thresh} a'zo / 30 soniya",
                callback_data=f"guard:cycle_raid_thresh:{gid}:raid"
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


def get_settings_mute_keyboard(group_id: int, guard: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Mute configuration sub-menu."""
    gid = str(group_id)
    dur = guard.get("mute_duration", 900)
    mins = max(1, dur // 60)

    keyboard = [
        [
            InlineKeyboardButton(
                text=f"Standart Mute muddati: {mins} daqiqa",
                callback_data=f"guard:cycle_mute_dur:{gid}:mute"
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


def get_settings_ban_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Ban management sub-menu."""
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(
                text="◀️ Orqaga",
                callback_data=f"settings:menu:{gid}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_settings_stats_keyboard(group_id: int) -> InlineKeyboardMarkup:
    """Stats sub-menu."""
    gid = str(group_id)
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔄 Yangilash",
                callback_data=f"settings:stats:{gid}"
            ),
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
                text="⚡️ Standart rejim (Link, Spam, Reklama, Flood faol)",
                callback_data=f"setup:preset:default:{gid}:presets"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔒 Qat'iy rejim (Barcha filtrlar + So'kish filtri + Raid)",
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


# Legacy backward-compatibility aliases
get_settings_guard_keyboard = get_settings_link_keyboard
get_settings_sec_keyboard = get_settings_badwords_keyboard
get_settings_srv_keyboard = get_settings_general_keyboard
