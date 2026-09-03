"""
Admin panel inline keyboards.

All callbacks use the 'ap:' prefix namespace to avoid conflicts with
existing guard/fsub callbacks.

Callback data format (max 64 bytes each):
  ap:mn              — main menu
  ap:gs              — groups list
  ap:g:{gid}         — group detail
  ap:gu:{gid}        — guard panel
  ap:fs:{gid}        — force subscribe panel
  ap:st:{gid}        — stats panel
  ap:cf:{gid}        — config / flood+badwords panel
  ap:gt:{gid}:{feat} — guard toggle feature
  ap:gm:{gid}:{v}    — guard master (v = on | off)
  ap:fw:{gid}        — flood settings sub-panel
  ap:bw:{gid}        — bad words sub-panel
  ap:bwT:{gid}:{v}   — bad words filter toggle (v = on | off)
  ap:fsT:{gid}:{v}   — fsub toggle (v = on | off)
  ap:fa:{gid}        — fsub add channel (FSM trigger)
  ap:fdl:{gid}       — fsub delete channel list
  ap:fdc:{gid}:{cid} — fsub delete specific channel
  ap:fl:{gid}        — change flood limit  (FSM)
  ap:fwc:{gid}       — change flood window (FSM)
  ap:mu:{gid}        — change mute duration (FSM)
  ap:bwa:{gid}       — bad word add  (FSM)
  ap:bwd:{gid}       — bad word del  (FSM)
  ap:bwl:{gid}       — bad word list view
"""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _cb(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _url(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


# ------------------------------------------------------------------ #
# Main menu
# ------------------------------------------------------------------ #

def admin_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_cb("👥 Guruhlarim", "ap:gs"))
    builder.row(
        _cb("🛡 Qorovul", "ap:gs:guard"),
        _cb("📢 Majburiy obuna", "ap:gs:fsub"),
    )
    builder.row(
        _cb("📊 Statistika", "ap:gs:stats"),
        _cb("⚙️ Sozlamalar", "ap:gs:config"),
    )
    builder.row(_cb("ℹ️ Yordam", "ap:help"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Groups list
# ------------------------------------------------------------------ #

def groups_list_keyboard(groups: list[dict[str, Any]], section: str = "") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for g in groups:
        gid = g.get("chat_id") or g.get("_id", "")
        title = g.get("title") or str(gid)
        suffix = f":{section}" if section in {"guard", "fsub", "stats", "config"} else ""
        builder.row(_cb(f"👥 {title}", f"ap:g:{gid}{suffix}"))
    builder.row(_cb("🏠 Bosh menyu", "ap:mn"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Group detail
# ------------------------------------------------------------------ #

def group_detail_keyboard(group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    builder = InlineKeyboardBuilder()
    builder.row(_cb("📢 Majburiy obuna", f"ap:fs:{gid}"))
    builder.row(_cb("🛡 Qorovul", f"ap:gu:{gid}"))
    builder.row(
        _cb("📊 Statistika", f"ap:st:{gid}"),
        _cb("⚙️ Sozlamalar", f"ap:cf:{gid}"),
    )
    builder.row(
        _cb("📋 Qorovul loglari", f"ap:lg:{gid}:0"),
        _cb("👮 Admin loglari", f"ap:la:{gid}:0"),
    )
    builder.row(_cb("🔄 Permissionlarni tekshirish", f"ap:pv:{gid}"))
    builder.row(_cb("⬅️ Orqaga", "ap:gs"), _cb("🏠 Bosh menyu", "ap:mn"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Guard panel
# ------------------------------------------------------------------ #

GUARD_FEATURE_LABELS: dict[str, str] = {
    "anti_spam":              "🛡 Anti-Spam",
    "anti_flood":             "🌊 Anti-Flood",
    "anti_link":              "🔗 Anti-Link",
    "anti_ads":               "📢 Anti-Reklama",
    "anti_repeat":            "🔁 Anti-Repeat",
    "bad_words":              "🚫 So'z filtri",
    "new_member_protection":  "👤 Yangi a'zolar",
}


def guard_panel_keyboard(guard: dict[str, Any], group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    builder = InlineKeyboardBuilder()

    for feat, label in GUARD_FEATURE_LABELS.items():
        is_on = guard.get(feat, False)
        mark = "✅" if is_on else "❌"
        builder.row(_cb(f"{label}: {mark}", f"ap:gt:{gid}:{feat}"))

    # Master toggle
    master = guard.get("enabled", False)
    if master:
        builder.row(_cb("🔴 Qorovulni o'chirish", f"ap:gm:{gid}:off"))
    else:
        builder.row(_cb("🟢 Qorovulni yoqish", f"ap:gm:{gid}:on"))

    builder.row(_cb("⚙️ Flood sozlamalari", f"ap:fw:{gid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:g:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# FSub panel
# ------------------------------------------------------------------ #

def fsub_panel_keyboard(fsub: dict[str, Any], group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    enabled = fsub.get("enabled", False)
    builder = InlineKeyboardBuilder()

    if enabled:
        builder.row(_cb("🔴 O'chirish", f"ap:fsT:{gid}:off"))
    else:
        builder.row(_cb("🟢 Yoqish", f"ap:fsT:{gid}:on"))

    builder.row(
        _cb("➕ Kanal qo'shish", f"ap:fa:{gid}"),
        _cb("🗑 Kanal o'chirish", f"ap:fdl:{gid}"),
    )
    builder.row(_cb("📋 Kanallar ro'yxati", f"ap:fdl:{gid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:g:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# FSub channel delete list
# ------------------------------------------------------------------ #

def fsub_del_keyboard(channels: list[dict], group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    builder = InlineKeyboardBuilder()
    for ch in channels:
        cid = ch["channel_id"]
        title = ch.get("title") or str(cid)
        builder.row(_cb(f"🗑 {title}", f"ap:fdc:{gid}:{cid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:fs:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Flood settings panel
# ------------------------------------------------------------------ #

def flood_settings_keyboard(group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    builder = InlineKeyboardBuilder()
    builder.row(_cb("🔢 Limitni o'zgartirish", f"ap:fl:{gid}"))
    builder.row(_cb("⏱ Vaqt oynasini o'zgartirish", f"ap:fwc:{gid}"))
    builder.row(_cb("🔇 Mute vaqtini o'zgartirish", f"ap:mu:{gid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:gu:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Config / Settings panel
# ------------------------------------------------------------------ #

def config_panel_keyboard(group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    builder = InlineKeyboardBuilder()
    builder.row(_cb("🚫 So'z filtri", f"ap:bw:{gid}"))
    builder.row(_cb("🌊 Flood sozlamalari", f"ap:fw:{gid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:g:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Bad words panel
# ------------------------------------------------------------------ #

def bad_words_keyboard(guard: dict[str, Any], group_id: int) -> InlineKeyboardMarkup:
    gid = group_id
    enabled = guard.get("bad_words", False)
    builder = InlineKeyboardBuilder()

    if enabled:
        builder.row(_cb("🔴 O'chirish", f"ap:bwT:{gid}:off"))
    else:
        builder.row(_cb("🟢 Yoqish", f"ap:bwT:{gid}:on"))

    builder.row(
        _cb("➕ So'z qo'shish", f"ap:bwa:{gid}"),
        _cb("🗑 So'z o'chirish", f"ap:bwd:{gid}"),
    )
    builder.row(_cb("📋 Ro'yxat", f"ap:bwl:{gid}"))
    builder.row(_cb("◀️ Orqaga", f"ap:cf:{gid}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Stats panel (no interactive buttons, just back)
# ------------------------------------------------------------------ #

def stats_keyboard(group_id: int, show_daily_button: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_daily_button:
        builder.row(_cb("📅 Bugungi statistika", f"ap:td:{group_id}"))
    else:
        builder.row(_cb("📊 Umumiy statistika", f"ap:st:{group_id}"))
    builder.row(_cb("◀️ Orqaga", f"ap:g:{group_id}"))
    return builder.as_markup()

def logs_pagination_keyboard(group_id: int, prefix: str, page: int, has_next: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row = []
    if page > 0:
        row.append(_cb("◀️ Oldingi", f"ap:{prefix}:{group_id}:{page-1}"))
    if has_next:
        row.append(_cb("Keyingi ▶️", f"ap:{prefix}:{group_id}:{page+1}"))
    if row:
        builder.row(*row)
    builder.row(_cb("◀️ Orqaga", f"ap:g:{group_id}"))
    return builder.as_markup()


# ------------------------------------------------------------------ #
# Cancel FSM input
# ------------------------------------------------------------------ #

def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_cb("❌ Bekor qilish", "ap:cancel"))
    return builder.as_markup()
