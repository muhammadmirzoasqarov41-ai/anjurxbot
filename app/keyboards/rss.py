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
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import config
from app.services.rss_storage import ChannelItem, SourceItem


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
    [📊 Statistika]
    [⏸ To‘xtatish] / [▶️ Davom ettirish]
    [🗑 Kanalni uzish]
    [🔙 Mening kanallarim]
    """
    status_btn_text = "⏸ To‘xtatish" if channel.active else "▶️ Davom ettirish"
    status_btn_cb = f"ch_toggle:{channel.chat_id}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📰 Manbalar", callback_data=f"ch_sources:{channel.chat_id}"),
                InlineKeyboardButton(text="⏰ Post vaqti", callback_data=f"ch_schedule:{channel.chat_id}"),
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


def get_channel_sources_keyboard(
    channel_id: int,
    all_sources: List[SourceItem],
    selected_source_ids: List[str],
) -> InlineKeyboardMarkup:
    """Displays super admin verified sources with toggle checkboxes."""
    buttons = []
    for src in all_sources:
        is_selected = src.id in selected_source_ids
        checkbox = "☑" if is_selected else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{checkbox} {src.name} ({src.category})",
                callback_data=f"ch_src_toggle:{channel_id}:{src.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="💾 Saqlash", callback_data=f"ch_view:{channel_id}"),
        InlineKeyboardButton(text="🔙 Ortga", callback_data=f"ch_view:{channel_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_channel_schedule_keyboard(channel: ChannelItem) -> InlineKeyboardMarkup:
    """
    Frequency and schedule mode options:
    Limit selection: 1 ta, 2 ta, 3 ta (strictly capped at 3 for free users)
    Schedule mode: Instant vs Scheduled times
    """
    limit = channel.daily_limit
    b1_check = "✅ " if limit == 1 else ""
    b2_check = "✅ " if limit == 2 else ""
    b3_check = "✅ " if limit == 3 else ""

    sched_mode = channel.schedule_mode
    instant_check = "✅ " if sched_mode == "instant" else ""
    scheduled_check = "✅ " if sched_mode == "scheduled" else ""

    buttons = [
        [
            InlineKeyboardButton(text=f"{b1_check}1 ta", callback_data=f"ch_set_limit:{channel.chat_id}:1"),
            InlineKeyboardButton(text=f"{b2_check}2 ta", callback_data=f"ch_set_limit:{channel.chat_id}:2"),
            InlineKeyboardButton(text=f"{b3_check}3 ta", callback_data=f"ch_set_limit:{channel.chat_id}:3"),
        ],
        [
            InlineKeyboardButton(
                text="➕ Ko‘proq post (Shartnoma)",
                callback_data=f"ch_contract_info:{channel.chat_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{instant_mode_label(instant_check)}",
                callback_data=f"ch_set_sched:{channel.chat_id}:instant",
            ),
            InlineKeyboardButton(
                text=f"{scheduled_mode_label(scheduled_check)}",
                callback_data=f"ch_set_sched:{channel.chat_id}:scheduled",
            ),
        ],
        [
            InlineKeyboardButton(text="🔙 Kanal boshqaruvi", callback_data=f"ch_view:{channel.chat_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def instant_mode_label(prefix: str) -> str:
    return f"{prefix}⚡ Darhol"


def scheduled_mode_label(prefix: str) -> str:
    return f"{prefix}🕐 Belgilangan vaqt"


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
