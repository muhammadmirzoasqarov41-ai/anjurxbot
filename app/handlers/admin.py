"""
Super Admin Panel Handlers for AnjurX | Rss Bot.
Guarded strictly by Telegram numeric User ID via is_super_admin().
Usernames are never used for privilege checks.
"""
import sys
import time
import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.config import config
from app.services.permission_service import is_super_admin
from app.services.rss_storage import rss_storage
from app.keyboards.rss import get_admin_panel_keyboard, get_main_menu_keyboard

logger = logging.getLogger("anjurxbot.admin")
router = Router(name="admin_router")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Opens Super Admin Panel if sender is Super Admin."""
    user = message.from_user
    user_id = user.id if user else 0

    if not is_super_admin(user_id):
        await message.reply("⛔ <b>Kirish taqiqlangan.</b> Ushbu bo‘lim faqat bot egasi uchun.", parse_mode="HTML")
        return

    stats = await rss_storage.get_stats()
    text = (
        "👑 <b>Super Admin Panel</b>\n\n"
        "Xush kelibsiz! Tizim boshqaruvi va monitoring bo‘limi.\n\n"
        f"• <b>Jami manbalar:</b> {stats.get('total_sources', 0)} ta\n"
        f"• <b>Jami kanallar:</b> {stats.get('total_destinations', 0)} ta\n"
        f"• <b>Yetkazilgan postlar:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Super Admin ID:</b> <code>{user_id}</code> (Faol)\n"
    )
    await message.answer(
        text,
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_panel_main")
async def cb_admin_panel_main(callback: CallbackQuery):
    """Admin panel main menu callback."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("Ruxsat berilmagan", show_alert=True)
        return

    stats = await rss_storage.get_stats()
    text = (
        "👑 <b>Super Admin Panel</b>\n\n"
        f"• <b>Jami manbalar:</b> {stats.get('total_sources', 0)} ta\n"
        f"• <b>Jami kanallar:</b> {stats.get('total_destinations', 0)} ta\n"
        f"• <b>Yetkazilgan postlar:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Super Admin ID:</b> <code>{user_id}</code> (Faol)\n"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Detailed stats."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("Ruxsat berilmagan", show_alert=True)
        return

    stats = await rss_storage.get_stats()
    sources = await rss_storage.get_all_sources()
    destinations = await rss_storage.get_all_destinations()

    rss_count = sum(1 for s in sources if s.type == "rss")
    tg_count = sum(1 for s in sources if s.type == "telegram_channel")
    active_dests = sum(1 for d in destinations if d.can_post)

    text = (
        "📊 <b>Batafsil Tizim Statistikasi</b>\n\n"
        f"• <b>Jami manbalar:</b> {len(sources)} ta\n"
        f"   └ 🌐 RSS saytlar: {rss_count} ta\n"
        f"   └ 📢 Telegram kanallar: {tg_count} ta\n\n"
        f"• <b>Jami kanallar (Destinations):</b> {len(destinations)} ta\n"
        f"   └ ✅ Post yuborish faol: {active_dests} ta\n"
        f"   └ ⚠️ Huquqi yo'q/muammoli: {len(destinations) - active_dests} ta\n\n"
        f"• <b>Jami yetkazilgan postlar:</b> {stats.get('posts_delivered', 0)} ta"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panelga qaytish", callback_data="admin_panel_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_sources")
async def cb_admin_sources(callback: CallbackQuery):
    """List all sources in system."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("Ruxsat berilmagan", show_alert=True)
        return

    sources = await rss_storage.get_all_sources()
    if not sources:
        text = "ℹ️ Tizimda hozircha hech qanday manba yo‘q."
    else:
        lines = ["📰 <b>Barcha ulangan manbalar:</b>\n"]
        for i, s in enumerate(sources[:20], 1):
            icon = "🌐 RSS" if s.type == "rss" else "📢 TG"
            err_info = f" (Xato: {s.error_count})" if s.error_count > 0 else ""
            lines.append(f"{i}. {icon}: <b>{s.title[:30]}</b> → {len(s.destinations)} kanal{err_info}")
        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panelga qaytish", callback_data="admin_panel_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_destinations")
async def cb_admin_destinations(callback: CallbackQuery):
    """List all destination channels in system."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("Ruxsat berilmagan", show_alert=True)
        return

    destinations = await rss_storage.get_all_destinations()
    if not destinations:
        text = "ℹ️ Tizimda hozircha hech qanday kanal ulanmagan."
    else:
        lines = ["📢 <b>Barcha ulangan kanallar:</b>\n"]
        for i, d in enumerate(destinations[:20], 1):
            status = "✅" if d.can_post else "❌ (Huquq yo‘q)"
            un = f" (@{d.username})" if d.username else ""
            lines.append(f"{i}. <b>{d.title[:30]}</b>{un} — {status}")
        text = "\n".join(lines)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panelga qaytish", callback_data="admin_panel_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_health")
async def cb_admin_health(callback: CallbackQuery):
    """System health check."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("Ruxsat berilmagan", show_alert=True)
        return

    import os
    text = (
        "⚡ <b>Tizim Holati va Diagnostika</b>\n\n"
        f"• <b>Python versiyasi:</b> {sys.version.split()[0]}\n"
        f"• <b>Storage fayli:</b> <code>{rss_storage.db_path}</code>\n"
        f"• <b>Fayl hajmi:</b> {os.path.getsize(rss_storage.db_path) if os.path.exists(rss_storage.db_path) else 0} bayt\n"
        f"• <b>Vaqt mintaqasi:</b> {config.timezone}\n"
        f"• <b>Bot Token:</b> {'Sozlangan ✅' if config.has_token() else 'Kiritilmagan ❌'}\n"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panelga qaytish", callback_data="admin_panel_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
