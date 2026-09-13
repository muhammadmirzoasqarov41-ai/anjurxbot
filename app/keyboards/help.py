"""
Help and Guide inline keyboards for AnjurXBot Qorovul.
Provides scannable submenus for onboarding, commands, guard, and settings.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Returns the primary inline keyboard for /start in private chat."""
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=add_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Qo'llanma",
                    callback_data="help:menu"
                ),
                InlineKeyboardButton(
                    text="🚀 Tezkor yo'riqnoma",
                    callback_data="help:start"
                )
            ]
        ]
    )


def get_help_menu_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Returns the Qorovul Help Center navigation menu keyboard."""
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛡 Qorovul nima va qanday ulanadi?",
                    callback_data="help:start"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Guruhni sozlash (/setup va /settings)",
                    callback_data="help:setup"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Anti-Link, Anti-Spam va Anti-Ads",
                    callback_data="help:links"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Anti-Flood va Bad Words (So'kish)",
                    callback_data="help:flood"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👮 Moderatsiya: Warn / Mute / Ban",
                    callback_data="help:moderation"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❓ Muammolarni hal qilish va Aloqa",
                    callback_data="help:support"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=add_url
                ),
                InlineKeyboardButton(
                    text="◀️ Bosh menyu",
                    callback_data="help:back_start"
                ),
            ]
        ]
    )


def get_help_sub_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Returns a navigation keyboard for individual help sub-sections."""
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Qo'llanmaga qaytish",
                    callback_data="help:menu"
                ),
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=add_url
                )
            ]
        ]
    )


def get_private_group_redirect_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Returns keyboard when a group command is invoked in private chat."""
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin=delete_messages+restrict_members+invite_users"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Guruhga qo'shish",
                    url=add_url
                )
            ],
            [
                InlineKeyboardButton(
                    text="📖 Qo'llanma",
                    callback_data="help:menu"
                )
            ]
        ]
    )
