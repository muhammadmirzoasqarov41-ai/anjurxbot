"""
Inline Keyboards for AnjurX | Obuna Bot.
Implements the exact user flow:
- Main Menu: [➕ Kanal qo‘shish], [📢 Mening kanallarim], [⚙️ Sozlamalar], [❓ Yordam]
  (+ [👑 Super Admin Panel] for Super Admin only)
- Channel Dashboard: [📰 Manbalar], [⏰ Post vaqti], [📊 Statistika], [⏸ To‘xtatish/▶️ Davom ettirish], [🗑 Kanalni uzish], [🔙 Mening kanallarim]
- Source Selection: Multi-select checkboxes for admin-verified sources (Kun.uz, Daryo.uz, etc.)
- Post Frequency & Schedule: 1 ta, 2 ta, 3 ta; Instant vs Scheduled times
- Super Admin Panel keyboards
"""
from __future__ import annotations

from typing import List, Optional, Any, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import config
from app.services.rss_storage import ChannelItem, SourceItem, CategoryItem


def get_main_menu_keyboard(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """
    Main menu keyboard.
    Normal user:
    [➕ Kanal qo‘shish]
    [📢 Mening kanallarim]
    [⚙️ Sozlamalar]  [❓ Yordam]
    Super admin gets additional:
    [👑 Super Admin Panel]
    """
    buttons = [
        [
            InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="btn_add_channel"),
            InlineKeyboardButton(text="📢 Mening kanallarim", callback_data="btn_my_channels"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="btn_settings"),
            InlineKeyboardButton(text="❓ Yordam", callback_data="btn_help"),
        ],
    ]

    if user_id and config.is_super_admin(user_id):
        buttons.append([
            InlineKeyboardButton(text="👑 Super Admin Panel", callback_data="admin_panel_main"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channels_list_keyboard(channels: List[ChannelItem]) -> InlineKeyboardMarkup:
    """Displays user's connected channels for management."""
    buttons = []
    for ch in channels:
        status_dot = "🟢" if (ch.active and ch.can_post) else ("⏸" if not ch.active else "⚠️")
        title_display = ch.title[:24] + "..." if len(ch.title) > 24 else ch.title
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_dot} {title_display}",
                callback_data=f"ch_view:{ch.chat_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Yangi kanal qo‘shish", callback_data="btn_add_channel"),
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_detail_keyboard(channel: ChannelItem) -> InlineKeyboardMarkup:
    """
    Detailed actions for an individual channel:
    [📰 Manbalar]
    [⏰ Post vaqti]
    [🌐 Post tili]
    [📊 Statistika]
    [⏸ To‘xtatish] / [▶️ Davom ettirish]
    [🗑 Kanalni uzish]
    [🔙 Mening kanallarim]
    """
    status_btn_text = "⏸ To‘xtatish" if channel.active else "▶️ Davom ettirish"
    status_btn_cb = f"ch_toggle:{channel.chat_id}"

    lang_code = getattr(channel, "post_language", "uz") or "uz"
    lang_flags = {"uz": "🇺🇿 O‘zbekcha", "ru": "🇷🇺 Русский", "en": "🇬🇧 English", "auto": "🔄 Avtomatik"}
    lang_btn_text = f"🌐 Post tili: {lang_flags.get(lang_code, '🇺🇿')}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📰 Manbalar", callback_data=f"ch_sources:{channel.chat_id}"),
                InlineKeyboardButton(text="⏰ Post vaqti", callback_data=f"ch_schedule:{channel.chat_id}"),
            ],
            [
                InlineKeyboardButton(text=lang_btn_text, callback_data=f"ch_lang:{channel.chat_id}"),
            ],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data=f"ch_stats:{channel.chat_id}"),
                InlineKeyboardButton(text=status_btn_text, callback_data=status_btn_cb),
            ],
            [
                InlineKeyboardButton(text="🗑 Kanalni uzish", callback_data=f"ch_disconnect_ask:{channel.chat_id}"),
            ],
            [
                InlineKeyboardButton(text="🔙 Mening kanallarim", callback_data="btn_my_channels"),
            ],
        ]
    )


def get_channel_language_keyboard(channel_id: int, current_lang: str = "uz") -> InlineKeyboardMarkup:
    """Keyboard for selecting channel post language (uz, ru, en, auto)."""
    langs = [
        ("uz", "🇺🇿 O‘zbekcha"),
        ("ru", "🇷🇺 Русский"),
        ("en", "🇬🇧 English"),
        ("auto", "🔄 Avtomatik (Asl tilda)"),
    ]
    buttons = []
    for code, title in langs:
        check = "✅ " if code == current_lang else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{check}{title}",
                callback_data=f"ch_set_lang:{channel_id}:{code}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Kanal boshqaruvi", callback_data=f"ch_view:{channel_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_categories_keyboard(
    channel_id: int,
    categories: List[CategoryItem],
    sources_by_cat: Dict[str, List[SourceItem]],
    selected_source_ids: List[str],
) -> InlineKeyboardMarkup:
    """Displays category selection overview for a channel with counts (e.g. O‘zbekiston (3/4))."""
    buttons = []
    selected_set = set(selected_source_ids)

    for cat in categories:
        cat_sources = sources_by_cat.get(cat.id, [])
        if not cat_sources:
            continue
        total_count = len(cat_sources)
        selected_count = sum(1 for s in cat_sources if s.id in selected_set)

        status_icon = "✅" if selected_count == total_count and total_count > 0 else ("🔘" if selected_count > 0 else "📁")
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {cat.name} ({selected_count}/{total_count})",
                callback_data=f"ch_cat_view:{channel_id}:{cat.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="✅ Hammasini tanlash", callback_data=f"ch_src_bulk:{channel_id}:all:select"),
        InlineKeyboardButton(text="🧹 Tozalash", callback_data=f"ch_src_bulk:{channel_id}:all:clear"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Kanal boshqaruvi", callback_data=f"ch_view:{channel_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_category_sources_keyboard(
    channel_id: int,
    category: CategoryItem,
    sources: List[SourceItem],
    selected_source_ids: List[str],
) -> InlineKeyboardMarkup:
    """Displays sources within a category with individual checkboxes and bulk select/clear."""
    buttons = []
    selected_set = set(selected_source_ids)

    for src in sources:
        is_selected = src.id in selected_set
        checkbox = "☑" if is_selected else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{checkbox} {src.name}",
                callback_data=f"ch_src_toggle:{channel_id}:{category.id}:{src.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="✅ Kategoriya: Barchasi", callback_data=f"ch_src_bulk:{channel_id}:{category.id}:select"),
        InlineKeyboardButton(text="🧹 Tozalash", callback_data=f"ch_src_bulk:{channel_id}:{category.id}:clear"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Kategoriyalar ro‘yxati", callback_data=f"ch_sources:{channel_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_sources_keyboard(
    channel_id: int,
    all_sources: List[SourceItem],
    selected_source_ids: List[str],
) -> InlineKeyboardMarkup:
    """Fallback / legacy view for verified sources with toggle checkboxes."""
    buttons = []
    for src in all_sources:
        is_selected = src.id in selected_source_ids
        checkbox = "☑" if is_selected else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{checkbox} {src.name} ({src.category})",
                callback_data=f"ch_src_toggle:{channel_id}:all:{src.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="💾 Saqlash", callback_data=f"ch_view:{channel_id}"),
        InlineKeyboardButton(text="🔙 Ortga", callback_data=f"ch_view:{channel_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_schedule_keyboard(channel: ChannelItem) -> InlineKeyboardMarkup:
    """
    Frequency, schedule mode, and custom times options:
    - Limit: 1, 2, 3 (strictly capped at 3 for free users)
    - Schedule mode: Instant vs Custom (Tashkent timezone)
    - Custom time slot editing & presets
    """
    limit = channel.daily_limit
    b1_check = "✅ " if limit == 1 else ""
    b2_check = "✅ " if limit == 2 else ""
    b3_check = "✅ " if limit == 3 else ""

    sched_mode = channel.schedule_mode
    instant_check = "✅ " if sched_mode == "instant" else ""
    scheduled_check = "✅ " if sched_mode in ("custom", "scheduled") else ""

    buttons = [
        [
            InlineKeyboardButton(text=f"{b1_check}1 ta post", callback_data=f"ch_set_limit:{channel.chat_id}:1"),
            InlineKeyboardButton(text=f"{b2_check}2 ta post", callback_data=f"ch_set_limit:{channel.chat_id}:2"),
            InlineKeyboardButton(text=f"{b3_check}3 ta post", callback_data=f"ch_set_limit:{channel.chat_id}:3"),
        ],
        [
            InlineKeyboardButton(
                text=f"{instant_mode_label(instant_check)}",
                callback_data=f"ch_set_sched:{channel.chat_id}:instant",
            ),
            InlineKeyboardButton(
                text=f"{scheduled_mode_label(scheduled_check)}",
                callback_data=f"ch_set_sched:{channel.chat_id}:custom",
            ),
        ],
    ]

    if sched_mode in ("custom", "scheduled"):
        buttons.append([
            InlineKeyboardButton(
                text="✏️ Vaqtlarni kiritish / o‘zgartirish",
                callback_data=f"ch_edit_times:{channel.chat_id}",
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🌅 09:00, 14:00, 19:00",
                callback_data=f"ch_set_preset:{channel.chat_id}:standard",
            ),
            InlineKeyboardButton(
                text="💼 08:30, 13:00, 18:30",
                callback_data=f"ch_set_preset:{channel.chat_id}:work",
            ),
        ])

    buttons.append([
        InlineKeyboardButton(
            text="➕ Ko‘proq post (Shartnoma)",
            callback_data=f"ch_contract_info:{channel.chat_id}",
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Kanal boshqaruvi", callback_data=f"ch_view:{channel.chat_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def instant_mode_label(prefix: str) -> str:
    return f"{prefix}⚡ Darhol (Instant)"


def scheduled_mode_label(prefix: str) -> str:
    return f"{prefix}🕐 Belgilangan (Custom)"


def get_contract_contact_keyboard(channel_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Button linking directly to admin for contract/tariff expansion."""
    buttons = [
        [
            InlineKeyboardButton(text="👨‍💻 Admin bilan bog‘lanish", url="https://t.me/usafes"),
        ],
    ]
    if channel_id:
        buttons.append([
            InlineKeyboardButton(text="🔙 Ortga", callback_data=f"ch_schedule:{channel_id}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_disconnect_confirm_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    """Disconnect confirmation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Ha, uzilsin", callback_data=f"ch_disconnect_do:{channel_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ch_view:{channel_id}"),
            ]
        ]
    )


def get_connect_channel_guide_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Instructions and deep-link for adding bot to channel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Botni kanalga qo‘shish (Admin)",
                    url=f"https://t.me/{bot_username}?startchannel=true&admin=post_messages",
                )
            ],
            [
                InlineKeyboardButton(text="🔄 Kanalni tekshirish", callback_data="btn_check_channel"),
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Help center with direct link to admin."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👨‍💻 Admin bilan bog‘lanish", url="https://t.me/usafes"),
            ],
            [
                InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="btn_add_channel"),
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """General cancel action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


def get_destination_selection_keyboard(
    destinations: List[ChannelItem],
    callback_prefix: str = "rss_dest_sel",
    user_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """
    Keyboard for selecting destination channel owned by the user.
    Security: Strictly filters to user's own channels if user_id is provided,
    preventing IDOR and exposure of other users' channels.
    """
    buttons = []
    for d in destinations:
        # Strict ownership verification if user_id is given
        if user_id and d.owner_user_id and d.owner_user_id != user_id:
            if not config.is_super_admin(user_id):
                continue

        status_icon = "🟢" if (d.active and d.can_post) else "⏸"
        title = d.title[:24] + "..." if len(d.title) > 24 else d.title
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {title}",
                callback_data=f"{callback_prefix}:{d.chat_id}",
            )
        ])

    if not buttons:
        buttons.append([
            InlineKeyboardButton(text="➕ Avval kanal qo‘shing", callback_data="btn_add_channel")
        ])

    buttons.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_connection_confirm_keyboard(confirm_callback_data: str) -> InlineKeyboardMarkup:
    """Confirm or cancel a connection action."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, ulansin", callback_data=confirm_callback_data),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


def get_sources_list_keyboard(sources: List[SourceItem]) -> InlineKeyboardMarkup:
    """List of sources with delete buttons and back to main menu."""
    buttons = []
    for s in sources:
        name = getattr(s, "name", None) or getattr(s, "title", "Manba")
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {name[:24]}",
                callback_data=f"del_src_ask:{s.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_source_confirm_keyboard(source_id: str, title: str = "") -> InlineKeyboardMarkup:
    """Confirms source deletion."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Ha, o‘chirilsin", callback_data=f"del_src_do:{source_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="btn_my_sources"),
            ]
        ]
    )


def get_rss_list_keyboard(feeds: List[Any]) -> InlineKeyboardMarkup:
    """Lists feeds with unsub action buttons."""
    buttons = []
    for f in feeds:
        name = getattr(f, "name", None) or getattr(f, "title", "Feed")
        feed_id = getattr(f, "id", "")
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {name[:24]}",
                callback_data=f"unsub_feed:{feed_id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_main")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_unsub_confirm_keyboard(feed_id: str, title: str = "") -> InlineKeyboardMarkup:
    """Unsubscribe confirmation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Obunani bekor qilish", callback_data=f"unsub_confirm:{feed_id}"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


def get_allunsub_confirm_keyboard() -> InlineKeyboardMarkup:
    """Unsubscribe all confirmation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Barcha obunalarni o‘chirish", callback_data="allunsub_confirm"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


# ==============================================================================
# SUPER ADMIN KEYBOARDS
# ==============================================================================

def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Super Admin navigation panel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌐 Manbalar (RSS)", callback_data="admin_sources_list"),
                InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels_list"),
            ],
            [
                InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users_list"),
                InlineKeyboardButton(text="💼 Tariflar & Limitlar", callback_data="admin_tariffs"),
            ],
            [
                InlineKeyboardButton(text="📦 Post Queue (5 kunlik hovuz)", callback_data="admin_queue_stats"),
                InlineKeyboardButton(text="📊 Umumiy Statistika", callback_data="admin_stats"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Tizim Sozlamalari", callback_data="admin_settings"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


def get_admin_sources_keyboard(sources: List[SourceItem]) -> InlineKeyboardMarkup:
    """Super Admin sources manager."""
    buttons = []
    for s in sources[:15]:
        status = "🟢" if s.active else "⏸"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {s.name} ({s.category})",
                callback_data=f"admin_src_view:{s.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Yangi manba qo‘shish", callback_data="admin_src_add"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_source_detail_keyboard(source: SourceItem) -> InlineKeyboardMarkup:
    """Super Admin actions for a specific source."""
    toggle_text = "⏸ To‘xtatish" if source.active else "▶️ Faollashtirish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"admin_src_toggle:{source.id}"),
                InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"admin_src_del:{source.id}"),
            ],
            [
                InlineKeyboardButton(text="🔙 Manbalar ro‘yxati", callback_data="admin_sources_list"),
            ],
        ]
    )
