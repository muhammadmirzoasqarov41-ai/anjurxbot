"""
Telegram Bot command setup for AnjurX | Rss Bot.
Registers bot command menus for users and administrators.
"""
import logging
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllChatAdministrators

logger = logging.getLogger("anjurxbot.commands")


async def setup_bot_commands(bot: Bot):
    """Sets standard BotFather command menu in Telegram clients."""
    user_commands = [
        BotCommand(command="start", description="Bosh menyuni ochish"),
        BotCommand(command="help", description="Qo‘llanma va yordam"),
        BotCommand(command="sub", description="Yangi RSS feedga obuna bo'lish: /sub <url>"),
        BotCommand(command="unsub", description="Obunani bekor qilish"),
        BotCommand(command="rss", description="Obunalar ro'yxati"),
        BotCommand(command="export", description="Obunalarni OPML formatida eksport qilish"),
        BotCommand(command="allunsub", description="Barcha obunalarni o'chirish"),
    ]

    admin_commands = [
        BotCommand(command="admin", description="Super Admin Panel"),
        BotCommand(command="sub", description="Guruh/kanal uchun RSS obuna qo'shish"),
        BotCommand(command="unsub", description="Obunani o'chirish"),
        BotCommand(command="rss", description="Faol obunalar"),
        BotCommand(command="export", description="OPML eksport"),
        BotCommand(command="allunsub", description="Barcha obunalarni o'chirish"),
    ]

    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
        logger.info("AnjurX | Rss Bot commands registered successfully in Telegram.")
    except Exception as e:
        logger.warning(f"Could not register Telegram commands menu: {e}")
