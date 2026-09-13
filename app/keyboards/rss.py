"""
Inline and reply keyboards for AnjurX | Rss Bot.
"""
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.services.rss_storage import RSSFeed


def get_rss_list_keyboard(feeds: List[RSSFeed]) -> InlineKeyboardMarkup:
    """Returns an inline keyboard with an unsubscribe button next to each feed."""
    buttons = []
    for f in feeds[:15]:  # show up to 15 feeds per menu
        title = f.title[:26] + "..." if len(f.title) > 26 else f.title
        buttons.append([
            InlineKeyboardButton(text=f"❌ {title}", callback_data=f"rss_unsub:{f.id}"),
        ])

    control_row = [
        InlineKeyboardButton(text="📥 OPML Eksport", callback_data="rss_export_opml"),
        InlineKeyboardButton(text="🗑 Hammasini o'chirish", callback_data="rss_unsub_all_confirm"),
    ]
    buttons.append(control_row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_unsub_confirm_keyboard(feed_id: str) -> InlineKeyboardMarkup:
    """Confirmation keyboard for unsubscribing from a single feed."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, bekor qilish", callback_data=f"rss_unsub_do:{feed_id}"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="rss_cancel"),
            ]
        ]
    )


def get_allunsub_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard for unsubscribing from all feeds."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚠️ Ha, barchasini o'chirish", callback_data="rss_allunsub_confirm_do"),
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="rss_cancel"),
            ]
        ]
    )


def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Welcome keyboard for AnjurX | Rss Bot."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=f"https://t.me/{bot_username}?startgroup=true",
                ),
                InlineKeyboardButton(
                    text="📢 Kanalga qo'shish",
                    url=f"https://t.me/{bot_username}?startchannel=true",
                ),
            ],
            [
                InlineKeyboardButton(text="📋 Obunalarim (/rss)", callback_data="rss_show_list"),
                InlineKeyboardButton(text="📥 OPML Eksport", callback_data="rss_export_opml"),
            ],
        ]
    )
