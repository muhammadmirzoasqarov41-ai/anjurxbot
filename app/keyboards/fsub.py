"""
Force Subscribe (Majburiy obuna) Keyboards.
"""
from typing import List, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.common import get_back_button


def get_force_sub_user_keyboard(channels: List[Dict[str, Any]], group_id: int) -> InlineKeyboardMarkup:
    """Keyboard shown to regular users who have not subscribed to required channels."""
    buttons = []
    for idx, ch in enumerate(channels, start=1):
        title = ch.get("title") or f"Kanal #{idx}"
        url = ch.get("invite_link") or ch.get("url") or f"https://t.me/{str(ch.get('channel_id')).replace('@', '')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {title}", url=url)])

    # Verification button with group_id encoded
    buttons.append([
        InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data=f"fsub:check:{group_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_force_sub_admin_keyboard(group_id: int, channels: List[Dict[str, Any]], is_enabled: bool) -> InlineKeyboardMarkup:
    """Admin configuration keyboard for Force Subscribe."""
    gid = str(group_id)
    status_icon = "✅ Yoqilgan" if is_enabled else "❌ O'chirilgan"

    buttons = [
        [
            InlineKeyboardButton(
                text=f"Holat: {status_icon}",
                callback_data=f"fsub:toggle_status:{gid}",
            )
        ],
        [
            InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data=f"fsub:add_channel:{gid}"),
        ],
    ]

    for ch in channels:
        cid = ch.get("channel_id")
        title = ch.get("title") or str(cid)
        buttons.append([
            InlineKeyboardButton(text=f"❌ O'chirish: {title}", callback_data=f"fsub:del_channel:{gid}:{cid}")
        ])

    buttons.append([get_back_button(f"admin:panel:{gid}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
