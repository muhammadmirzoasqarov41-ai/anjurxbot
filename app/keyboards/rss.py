"""
Inline keyboards for AnjurX | Rss Bot.
Clean, modern, and step-by-step UX for managing RSS feeds, Telegram channels, and destinations.
"""
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import config
from app.services.rss_storage import SourceItem, DestinationItem, RSSFeed


def get_main_menu_keyboard(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Returns the primary navigation menu as requested by user."""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Kanal ulash", callback_data="menu_connect_channel"),
        ],
        [
            InlineKeyboardButton(text="🌐 Sayt/RSS qo‘shish", callback_data="menu_add_rss"),
            InlineKeyboardButton(text="📢 Telegram kanal qo‘shish", callback_data="menu_add_tg_source"),
        ],
        [
            InlineKeyboardButton(text="📋 Mening manbalarim", callback_data="menu_my_sources"),
            InlineKeyboardButton(text="⚙️ Sozlamalar", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton(text="❓ Yordam", callback_data="menu_help"),
        ],
    ]

    if user_id and config.is_super_admin(user_id):
        buttons.append([
            InlineKeyboardButton(text="👑 Admin Panel", callback_data="admin_panel_main"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_destination_selection_keyboard(
    destinations: List[DestinationItem],
    callback_prefix: str,
    user_id: Optional[int] = None,
) -> InlineKeyboardMarkup:
    """Shows user's connected destination channels to select for news delivery."""
    buttons = []
    for d in destinations[:10]:
        title = d.title[:24] + "..." if len(d.title) > 24 else d.title
        icon = "📢" if d.type == "channel" else ("👥" if "group" in d.type else "👤")
        status_icon = "✅" if d.can_post else "⚠️"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {title} ({status_icon})",
                callback_data=f"{callback_prefix}:{d.chat_id}",
            )
        ])

    if user_id:
        buttons.append([
            InlineKeyboardButton(
                text="👤 Shaxsiy chatimga yuborish",
                callback_data=f"{callback_prefix}:{user_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Yangi kanal ulash", callback_data="menu_connect_channel"),
        InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_connection_confirm_keyboard(callback_data_yes: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for connecting a source to a channel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ulash", callback_data=callback_data_yes),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="menu_cancel"),
            ]
        ]
    )


def get_sources_list_keyboard(sources: List[SourceItem]) -> InlineKeyboardMarkup:
    """Shows user's sources with 1-tap delete buttons."""
    buttons = []
    for s in sources[:12]:
        icon = "🌐" if s.type == "rss" else "📢"
        title = s.title[:22] + "..." if len(s.title) > 22 else s.title
        dest_count = len(s.destinations)
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {icon} {title} ({dest_count} kanal)",
                callback_data=f"del_src_ask:{s.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="➕ Yangi manba qo‘shish", callback_data="menu_add_picker"),
        InlineKeyboardButton(text="📥 OPML Eksport", callback_data="rss_export_opml"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delete_source_confirm_keyboard(source_id: str, title: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for deleting a source."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Ha, o‘chirish", callback_data=f"del_src_do:{source_id}"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_my_sources"),
            ]
        ]
    )


def get_connect_channel_guide_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Channel connection wizard keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Botni kanalga qo‘shish (Admin)",
                    url=f"https://t.me/{bot_username}?startchannel=true",
                )
            ],
            [
                InlineKeyboardButton(text="🔄 Yangilash / Tekshirish", callback_data="refresh_channels"),
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button for active FSM states."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_cancel"),
            ]
        ]
    )


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Tizim statistikasi", callback_data="admin_stats"),
                InlineKeyboardButton(text="📰 Barcha manbalar", callback_data="admin_sources"),
            ],
            [
                InlineKeyboardButton(text="📢 Barcha kanallar", callback_data="admin_destinations"),
                InlineKeyboardButton(text="⚡ Loglar va holat", callback_data="admin_health"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )


# Backward-compatible keyboards for existing commands
def get_rss_list_keyboard(feeds: List[RSSFeed]) -> InlineKeyboardMarkup:
    buttons = []
    for f in feeds[:15]:
        title = f.title[:26] + "..." if len(f.title) > 26 else f.title
        buttons.append([
            InlineKeyboardButton(text=f"❌ {title}", callback_data=f"rss_unsub:{f.id}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="📥 OPML Eksport", callback_data="rss_export_opml"),
        InlineKeyboardButton(text="🗑 Hammasini o'chirish", callback_data="rss_unsub_all_confirm"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_unsub_confirm_keyboard(feed_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, bekor qilish", callback_data=f"rss_unsub_do:{feed_id}"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


def get_allunsub_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Ha, barchasini o'chirish", callback_data="rss_allunsub_confirm_do"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_main"),
            ]
        ]
    )


def get_start_keyboard(bot_username: str, user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    return get_main_menu_keyboard(user_id)
