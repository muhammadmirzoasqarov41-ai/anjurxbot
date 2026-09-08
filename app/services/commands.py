"""
Telegram Bot Commands Configuration.
Sets contextual BotFather command menus for private and group chats.
"""
import logging
from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)

logger = logging.getLogger("anjurxbot.commands")


async def setup_bot_commands(bot: Bot):
    """
    Configures official Telegram Bot Command Menu for all scopes.
    Prioritizes key operational commands:
    /start, /help, /setup, /settings, /status
    """
    default_commands = [
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="help", description="Yordam va qo‘llanma"),
        BotCommand(command="setup", description="Guruhni sozlash ustasi"),
        BotCommand(command="settings", description="Guruh sozlamalari paneli"),
        BotCommand(command="status", description="Himoya filtrlari holati"),
    ]

    private_commands = [
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="help", description="Qo‘llanma va yordam markazi"),
        BotCommand(command="id", description="Sizning Telegram ID raqamingiz"),
    ]

    group_commands = [
        BotCommand(command="setup", description="Guruhni tezkor sozlash"),
        BotCommand(command="settings", description="Guruh sozlamalari paneli"),
        BotCommand(command="status", description="Himoya filtrlari holati"),
        BotCommand(command="help", description="Guruh buyruqlari qo‘llanmasi"),
        BotCommand(command="warn", description="A'zoga ogohlantirish berish (reply)"),
        BotCommand(command="mute", description="A'zo ovozini o‘chirish (reply)"),
        BotCommand(command="unmute", description="Ovoz cheklovini bekor qilish (reply)"),
        BotCommand(command="id", description="Chat va foydalanuvchi ID"),
    ]

    try:
        await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        logger.info("Telegram bot command menus configured successfully for all scopes.")
    except Exception as e:
        logger.warning(f"Failed to set Telegram bot commands: {e}")
