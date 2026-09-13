"""
Admin command handlers and callback routers.
Includes /settings (canonical group control), /panel (alias),
Super Admin dashboard (/admin), manual moderation tools (/warn, /mute, /unmute),
and administrative metrics inspection.
"""
import time
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.services.warning import warning_service
from app.services.moderation import moderation_service
from app.services.stats_service import stats_service
from app.services.firebase import firebase_service
from app.services.health_service import health_service
from app.database.firestore import db
from app.keyboards.settings import (
    get_group_settings_keyboard,
    get_settings_general_keyboard,
    get_settings_spam_keyboard,
    get_settings_flood_keyboard,
    get_settings_link_keyboard,
    get_settings_ads_keyboard,
    get_settings_badwords_keyboard,
    get_settings_raid_keyboard,
    get_settings_warns_keyboard,
    get_settings_mute_keyboard,
    get_settings_ban_keyboard,
    get_settings_stats_keyboard,
    get_settings_presets_keyboard,
    get_settings_guard_keyboard,
    get_settings_sec_keyboard,
    get_settings_srv_keyboard,
)
from app.keyboards.admin import (
    get_global_admin_keyboard,
    get_back_to_global_keyboard,
    get_back_to_settings_keyboard,
)
from app.keyboards.help import get_private_group_redirect_keyboard
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback
from app.config import config

router = Router(name="admin_router")


# =====================================================================
# 1. GROUP SETTINGS (/settings and /panel alias)
# =====================================================================

@router.message(Command("settings", "panel"))
async def cmd_settings(message: Message, bot: Bot):
    """
    Main entry point for group configuration (/settings or /panel).
    Strictly scoped to message.chat.id and verified for group administrators.
    """
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    # Contextual guidance in private chat (Requirement #12)
    if message.chat.type not in ("group", "supergroup"):
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username or "AnjurXBot"
        await message.reply(
            "⚙️ <b>/settings faqat guruh ichida ishlaydi.</b>\n\n"
            "Botni guruhga qo‘shing va guruhda <code>/settings</code> buyrug‘ini yuboring.",
            reply_markup=get_private_group_redirect_keyboard(bot_username),
            parse_mode="HTML"
        )
        return

    chat_id = message.chat.id
    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None

    # Sync and register group data with Telegram metadata
    await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
        chat=message.chat,
        bot=bot
    )

    is_admin = await permission_service.is_user_admin(
        bot,
        chat_id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    )
    if not is_admin:
        await message.reply(
            "⛔ <b>Kirish taqiqlangan!</b>\n"
            "Bu bo‘lim faqat guruh egasi va administratorlari uchun mo‘ljallangan.",
            parse_mode="HTML"
        )
        return

    # Check bot permissions for helpful guidance
    is_bot_adm, can_del, can_rst = await permission_service.get_bot_permissions(bot, chat_id)
    warning_note = ""
    if not is_bot_adm or not can_del or not can_rst:
        warning_note = (
            "\n\n⚠️ <i>Diqqat: Bot barcha filtrlarni (xabarlarni o'chirish, jazo qo'llash) "
            "to'liq bajarishi uchun guruhda to'liq Administrator huquqlariga ega bo'lishi kerak!</i>"
        )

    keyboard = get_group_settings_keyboard(chat_id)
    title = message.chat.title or f"Guruh {chat_id}"
    await message.reply(
        f"🛡 <b>QOROVUL</b>\n\n"
        f"Holat: 🟢 FAOL\n"
        f"Guruh: <b>{title}</b>\n"
        f"ID: <code>{chat_id}</code>{warning_note}\n\n"
        f"Boshqarish uchun quyidagi bo‘limlardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =====================================================================
# 1.1. GROUP PROTECTION STATUS (/status)
# =====================================================================

@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot):
    """
    Displays current group guard status (/status).
    Contextual in private chat, detailed in group chat.
    """
    if message.chat.type not in ("group", "supergroup"):
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username or "AnjurXBot"
        await message.reply(
            "📊 <b>/status faqat guruh ichida ishlaydi.</b>\n\n"
            "Botni guruhingizga qo‘shing va guruh ichida <code>/status</code> buyrug‘ini yuboring.",
            reply_markup=get_private_group_redirect_keyboard(bot_username),
            parse_mode="HTML"
        )
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None
    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None

    group_config = await group_service.get_or_register_group(
        chat_id,
        title=message.chat.title or "",
        chat=message.chat,
        bot=bot
    )

    guard = group_config.get("guard_settings", {})
    mod_stats = group_config.get("moderation_stats", {})

    def _icon(val: bool) -> str:
        return "🟢" if val else "🔴"

    anti_spam_st = _icon(bool(guard.get("anti_spam", True)))
    anti_flood_st = _icon(bool(guard.get("anti_flood", True)))
    anti_link_st = _icon(bool(guard.get("anti_link", True)))
    anti_ads_st = _icon(bool(guard.get("anti_ads", True)))
    bad_words_st = _icon(bool(guard.get("bad_words_filter", True)))

    # Real counts directly from Firestore
    spam_cnt = mod_stats.get("spam", 0)
    flood_cnt = mod_stats.get("flood", 0)
    link_cnt = mod_stats.get("link", 0)
    ads_cnt = mod_stats.get("ads", 0)
    warn_cnt = mod_stats.get("warn", 0)
    mute_cnt = mod_stats.get("mute", 0)
    ban_cnt = mod_stats.get("ban", 0)

    title = message.chat.title or f"Guruh {chat_id}"
    status_text = (
        f"🛡 <b>QOROVUL HOLATI:</b> {title}\n"
        f"ID: <code>{chat_id}</code>\n\n"
        f"Anti-Spam: {anti_spam_st}\n"
        f"Anti-Flood: {anti_flood_st}\n"
        f"Anti-Link: {anti_link_st}\n"
        f"Anti-Ads: {anti_ads_st}\n"
        f"Bad Words: {bad_words_st}\n\n"
        f"<b>Bugungi moderatsiya:</b>\n"
        f"• Spam: {spam_cnt}\n"
        f"• Flood: {flood_cnt}\n"
        f"• Link: {link_cnt}\n"
        f"• Ads: {ads_cnt}\n"
        f"• Warn: {warn_cnt}\n"
        f"• Mute: {mute_cnt}\n"
        f"• Ban: {ban_cnt}\n\n"
        f"⚙️ Sozlamalarni o‘zgartirish uchun: /settings"
    )

    is_admin = await permission_service.is_user_admin(
        bot,
        chat_id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat
    )

    kb = None
    if is_admin:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data=f"settings:menu:{chat_id}"),
                    InlineKeyboardButton(text="❌ Yopish", callback_data="common:close")
                ]
            ]
        )

    await message.reply(status_text, reply_markup=kb, parse_mode="HTML")


# --- Settings Submenu Callbacks ---

@router.callback_query(F.data.startswith("settings:menu:"))
@router.callback_query(F.data.startswith("admin:panel:"))
async def cb_settings_menu(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    keyboard = get_group_settings_keyboard(group_id)
    chat_title = callback.message.chat.title if callback.message and callback.message.chat else f"Guruh {group_id}"
    text = (
        f"🛡 <b>QOROVUL</b>\n\n"
        f"Holat: 🟢 FAOL\n"
        f"Guruh: <b>{chat_title}</b>\n"
        f"ID: <code>{group_id}</code>\n\n"
        f"Boshqarish uchun quyidagi bo‘limlardan birini tanlang:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:general:"))
@router.callback_query(F.data.startswith("settings:srv:"))
async def cb_settings_general(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_general_keyboard(group_id, guard)

    text = (
        "🛡 <b>Umumiy Himoya:</b>\n\n"
        "• Yangi a'zolar nazorati: dastlabki 5 daqiqa ichida spam va linklarni avtomatik bloklaydi.\n"
        "• Kirdi/Chiqdi xabarlari: guruhdagi ortiqcha service xabarlarni tozalaydi."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:spam:"))
async def cb_settings_spam(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_spam_keyboard(group_id, guard)

    text = (
        "🚫 <b>Spam Himoyasi:</b>\n\n"
        "• Spam xabarlari, shubhali fishing va kripto firibgarliklarini aniqlash.\n"
        "• Bir xil matnni qayta-qayta yuboruvchi spamerlarni avtomatik to'xtatish."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:flood:"))
async def cb_settings_flood(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_flood_keyboard(group_id, guard)

    limit = guard.get("flood_limit", 5)
    text = (
        "🌊 <b>Anti-Flood Himoyasi:</b>\n\n"
        f"Ketma-ket tez yozishni to'xtatadi. Hozirgi chegara: <b>{limit} ta xabar</b>.\n"
        "O'zgartirish uchun tugmani bosing:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:link:"))
@router.callback_query(F.data.startswith("settings:guard:"))
@router.callback_query(F.data.startswith("guard:menu:"))
async def cb_settings_link(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_link_keyboard(group_id, guard)

    text = (
        "🔗 <b>Link Himoyasi:</b>\n\n"
        "Guruhga yuborilgan har qanday havolalar (t.me, http://, https://) avtomatik o'chiriladi.\n"
        "Ishonchli saytlar uchun istisno ro'yxati (Allowed Domains) mavjud."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:ads:"))
async def cb_settings_ads(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_ads_keyboard(group_id, guard)

    text = (
        "📢 <b>Reklama Himoyasi:</b>\n\n"
        "Telegram kanallar, guruhlar, botlar reklamasi va havolali postlar filtrlanadi."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:badwords:"))
@router.callback_query(F.data.startswith("settings:sec:"))
async def cb_settings_badwords(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_badwords_keyboard(group_id, guard)

    words_count = len(guard.get("bad_words", []))
    text = (
        "🤬 <b>Yomon So'zlar va 18+ Filtri:</b>\n\n"
        f"Bazadagi taqiqlangan so'zlar: <b>{words_count} ta</b>.\n"
        "Harflar o'rniga belgi qo'yib yozilgan so'kishlar ham aniqlanadi."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:raid:"))
async def cb_settings_raid(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_raid_keyboard(group_id, guard)

    thresh = guard.get("raid_threshold", 10)
    text = (
        "🤖 <b>Raid va Botlar Hujumidan Himoya:</b>\n\n"
        f"Guruhga bir vaqtda ko'p botlar yoki spamerlar qo'shilsa ({thresh} a'zo / 30s), "
        "guruh avtomatik himoyalanadi va spamerlar bloklanadi."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:warns:"))
@router.callback_query(F.data.startswith("admin:warns:"))
async def cb_settings_warns(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_warns_keyboard(group_id, guard)

    warn_limit = guard.get("warn_limit", 3)
    punishment = str(guard.get("punishment", "mute")).upper()

    text = (
        "⚠️ <b>Ogohlantirish (Warn) Tizimi:</b>\n\n"
        f"• Chegara: <b>{warn_limit} ta</b>\n"
        f"• Limit to'lgandagi jazo: <b>{punishment}</b>\n\n"
        "Qo'lda ogohlantirish berish uchun: a'zo xabariga reply qilib <code>/warn</code> yuboring."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:mute:"))
async def cb_settings_mute(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_mute_keyboard(group_id, guard)

    dur = guard.get("mute_duration", 900)
    mins = max(1, dur // 60)

    text = (
        "🔇 <b>Mute (Ovozni o'chirish) Boshqaruvi:</b>\n\n"
        f"• Standart mute davomiyligi: <b>{mins} daqiqa</b>\n\n"
        "Qo'lda mute qilish uchun a'zo xabariga reply qilib:\n"
        "<code>/mute</code> (standart vaqt)\n"
        "<code>/mute 30m</code> (30 daqiqa)\n"
        "<code>/mute 2h</code> (2 soat)\n"
        "Ovozni qaytarish uchun: <code>/unmute</code>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:ban:"))
async def cb_settings_ban(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    keyboard = get_settings_ban_keyboard(group_id)
    text = (
        "🔨 <b>Ban (Guruhdan haydash) Boshqaruvi:</b>\n\n"
        "Qo'lda a'zoni bloklash uchun uning xabariga reply qilib:\n"
        "<code>/ban</code> yuboring.\n\n"
        "Bandan chiqarish uchun:\n"
        "<code>/unban [USER_ID]</code> yuboring."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:presets:"))
@router.callback_query(F.data.startswith("setup:menu:"))
async def cb_settings_presets(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    keyboard = get_settings_presets_keyboard(group_id)
    text = (
        "⚡️ <b>Tezkor Sozlash Rejimlari:</b>\n\n"
        "Barcha filtrlarni bir teginishda optimal darajada sozlang:\n\n"
        "• <b>Standart rejim:</b> Havola, spam va reklamalarni tozalash (Flood limiti: 5 ta).\n"
        "• <b>Qat'iy rejim:</b> Barcha himoyalar + Qayta xabar + So'kish filtri + Raid (Jazo: Mute)."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:stats:"))
@router.callback_query(F.data.startswith("admin:stats:"))
async def cb_settings_stats(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    summary = await stats_service.get_summary()
    runtime = summary.get("runtime", {})
    chat_title = callback.message.chat.title if callback.message and callback.message.chat else f"Guruh {group_id}"

    text = (
        f"📊 <b>Guruh Statistikasi:</b> {chat_title}\n\n"
        f"🔍 Tekshirilgan xabarlar: <b>{runtime.get('messages_checked', 0)}</b>\n"
        f"🔗 O'chirilgan havolalar: <b>{runtime.get('links_deleted', 0)}</b>\n"
        f"🚫 Bloklangan spamlar: <b>{runtime.get('spam_blocked', 0)}</b>\n"
        f"🌊 To'xtatilgan flood: <b>{runtime.get('flood_stopped', 0)}</b>\n"
        f"🤬 Tozalangan so'kishlar: <b>{runtime.get('bad_words_blocked', 0)}</b>\n"
        f"⚠️ Berilgan ogohlantirishlar: <b>{runtime.get('warnings_issued', 0)}</b>\n"
        f"🔇 Mute qilingan a'zolar: <b>{runtime.get('users_muted', 0)}</b>\n"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"settings:menu:{group_id}"),
                InlineKeyboardButton(text="❌ Yopish", callback_data="common:close"),
            ]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# =====================================================================
# 2. SUPER ADMIN PANEL (/admin)
# Strictly restricted to Bot Super Admin ID
# =====================================================================

@router.message(Command("admin"))
async def cmd_global_admin(message: Message):
    """
    Global bot Super Admin dashboard (/admin).
    Strictly checked by Telegram user_id.
    """
    user = message.from_user
    if not user or not config.is_super_admin(user.id):
        await message.reply(
            "⛔ Ruxsat berilmagan. Bu bo‘lim faqat botning Super Administratori uchun.",
            parse_mode="HTML"
        )
        return

    keyboard = get_global_admin_keyboard()
    await message.reply(
        "👑 <b>AnjurXBot Super Admin Boshqaruv Markazi:</b>\n\n"
        "Global statistika, barcha guruhlar monitoringi va Firebase holati:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data == "global:menu")
async def cb_global_menu(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    keyboard = get_global_admin_keyboard()
    try:
        await callback.message.edit_text(
            "👑 <b>AnjurXBot Super Admin Boshqaruv Markazi:</b>\n\n"
            "Global statistika, barcha guruhlar monitoringi va Firebase holati:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "global:stats")
async def cb_global_stats(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    summary = await stats_service.get_summary()
    runtime = summary.get("runtime", {})
    all_groups = await firebase_service.get_all_groups(limit=500)
    all_users = await firebase_service.get_all_users(limit=500)
    active_groups = [g for g in all_groups if g.get("is_active", True)]

    text = (
        "📊 <b>Global Tizim Statistikasi:</b>\n\n"
        f"👥 Jami guruhlar: <b>{len(all_groups)}</b> ta (🟢 Faol: <b>{len(active_groups)}</b> ta)\n"
        f"👤 Bazadagi foydalanuvchilar: <b>{len(all_users)}</b> ta\n\n"
        f"🔍 Jami tekshirilgan xabarlar: <b>{runtime.get('messages_checked', 0):,}</b>\n"
        f"🔗 O'chirilgan havolalar: <b>{runtime.get('links_deleted', 0):,}</b>\n"
        f"🚫 Bloklangan spamlar: <b>{runtime.get('spam_blocked', 0):,}</b>\n"
        f"🌊 To'xtatilgan flood: <b>{runtime.get('flood_stopped', 0):,}</b>\n"
        f"🤬 Bloklangan so'kishlar: <b>{runtime.get('bad_words_blocked', 0):,}</b>\n"
        f"⚠️ Berilgan ogohlantirishlar: <b>{runtime.get('warnings_issued', 0):,}</b>\n"
        f"🔇 Mute qilinganlar: <b>{runtime.get('users_muted', 0):,}</b>\n"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_back_to_global_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("global:groups:"))
async def cb_global_groups(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    parts = callback.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    per_page = 5

    all_groups = await firebase_service.get_all_groups(limit=500)
    if not all_groups:
        text = (
            "👥 <b>Ulangan Guruhlar Ro'yxati:</b>\n\n"
            "Hozircha bazada saqlangan guruhlar mavjud emas."
        )
        await callback.message.edit_text(text, reply_markup=get_back_to_global_keyboard(), parse_mode="HTML")
        await callback.answer()
        return

    total_groups = len(all_groups)
    total_pages = max(1, (total_groups + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    current_batch = all_groups[start_idx : start_idx + per_page]

    lines = [f"👥 <b>Ulangan Guruhlar (Sahifa {page}/{total_pages}, Jami: {total_groups} ta):</b>\n"]
    for idx, g in enumerate(current_batch, start=start_idx + 1):
        title = g.get("title") or "Noma'lum guruh"
        gid = g.get("group_id") or g.get("chat_id")
        owner_id = g.get("owner_id")
        owner_name = g.get("owner", {}).get("first_name") if isinstance(g.get("owner"), dict) else None
        owner_str = f"<code>{owner_id}</code> ({owner_name})" if owner_name else (f"<code>{owner_id}</code>" if owner_id else "Aniqlanmagan")
        admins_cnt = len(g.get("admins", []))
        members_cnt = g.get("members_count", 0)
        status_sym = "🟢 Faol" if g.get("is_active", True) else "🔴 Nofaol"
        bot_status = "👑 Admin" if g.get("bot_status") in ("administrator", "creator") else "👤 A'zo"

        lines.append(
            f"<b>{idx}. {title}</b>\n"
            f"   • ID: <code>{gid}</code> | {status_sym} | {bot_status}\n"
            f"   • Egasi: {owner_str}\n"
            f"   • Adminlar: {admins_cnt} ta | A'zolar: {members_cnt} ta\n"
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"global:groups:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"global:groups:{page + 1}"))

    kb_rows = [nav_buttons, [InlineKeyboardButton(text="◀️ Orqaga", callback_data="global:menu"), InlineKeyboardButton(text="❌ Yopish", callback_data="common:close")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("global:users:"))
async def cb_global_users(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    parts = callback.data.split(":")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    per_page = 8

    all_users = await firebase_service.get_all_users(limit=500)
    total_users = len(all_users)
    total_pages = max(1, (total_users + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    current_batch = all_users[start_idx : start_idx + per_page]

    lines = [f"👤 <b>Foydalanuvchilar Ro'yxati (Sahifa {page}/{total_pages}, Jami: {total_users} ta):</b>\n"]
    for idx, u in enumerate(current_batch, start=start_idx + 1):
        uid = u.get("user_id") or u.get("_id")
        fname = u.get("first_name") or "User"
        uname = f"@{u.get('username')}" if u.get("username") else "—"
        bot_badge = "🤖 Bot" if u.get("is_bot") else "👤"
        lines.append(f"{idx}. {bot_badge} <b>{fname}</b> ({uname}) — <code>{uid}</code>")

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"global:users:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="none"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"global:users:{page + 1}"))

    kb_rows = [nav_buttons, [InlineKeyboardButton(text="◀️ Orqaga", callback_data="global:menu"), InlineKeyboardButton(text="❌ Yopish", callback_data="common:close")]]
    keyboard = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "global:firebase")
async def cb_global_firebase(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    project_id = config.firebase_project_id
    sa_present = bool(config.firebase_service_account)
    db_initialized = bool(db._db is not None)
    memory_docs = len(db._memory_db)

    sa_status = "✅ Yuklangan" if sa_present else "⚠️ Standby (In-memory)"
    conn_status = "🟢 Faol (Cloud Firestore)" if db_initialized else "🟡 Mahalliy (In-memory kesh)"

    text = (
        "🗄 <b>Firebase Firestore Tizim Holati:</b>\n\n"
        f"• Project ID: <code>{project_id}</code>\n"
        f"• Service Account: {sa_status}\n"
        f"• Firestore ulanishi: {conn_status}\n"
        f"• Keshdagi to'plamlar: <b>{memory_docs} ta</b>\n\n"
        "<i>Barcha guruh sozlamalari va foydalanuvchilar doimiy xavfsiz saqlanmoqda.</i>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_back_to_global_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "global:health")
async def cb_global_health(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    uptime_sec = int(time.time() - getattr(stats_service, "_start_time", time.time()))
    uptime_min = uptime_sec // 60
    uptime_hr = uptime_min // 60

    debug_str = "Yoqilgan" if config.debug else "O'chirilgan"

    text = (
        "🛠 <b>Bot Texnik Holati:</b>\n\n"
        f"• Ish vaqti (Uptime): <b>{uptime_hr} soat {uptime_min % 60} daqiqa</b>\n"
        f"• Polling / Webhook: 🟢 Faol (Polling)\n"
        f"• Framework: <b>Aiogram 3.13.1 (Python)</b>\n"
        f"• Timezone: <b>{config.timezone}</b>\n"
        f"• Port: <b>{config.port}</b>\n"
        f"• Debug rejimi: <b>{debug_str}</b>\n"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_back_to_global_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "global:broadcast")
async def cb_global_broadcast(callback: CallbackQuery):
    if not config.is_super_admin(callback.from_user.id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    text = (
        "📢 <b>Xabar Tarqatish (Broadcast) Markazi:</b>\n\n"
        "Barcha guruhlarga xabar yuborish uchun xavfsizlik va spam filtrlariga rioya qilish talab etiladi.\n"
        "Barcha guruhlarga xabarnoma yuborish web boshqaruv paneli orqali boshqariladi."
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_back_to_global_keyboard(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# =====================================================================
# 3. MANUAL MODERATION COMMANDS (Reply-based)
# =====================================================================

@router.message(Command("warn"))
async def cmd_warn(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    if not await permission_service.is_user_admin(
        bot,
        message.chat.id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    ):
        await message.reply("⛔ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchiga ogohlantirish berish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot:
        await message.reply("Botlarga ogohlantirish berilmaydi.")
        return

    if await permission_service.is_user_admin(bot, message.chat.id, target.id, username=target.username, chat=message.chat):
        await message.reply("Adminlarga ogohlantirish berib bo'lmaydi.")
        return

    group_config = await group_service.get_or_register_group(message.chat.id, message.chat.title or "", chat=message.chat, bot=bot)
    warn_limit = group_config.get("guard_settings", {}).get("warn_limit", 3)
    punishment_type = group_config.get("guard_settings", {}).get("punishment", "mute")

    new_count, reached = warning_service.add_warning(message.chat.id, target.id, warn_limit)

    if reached:
        if punishment_type == "mute":
            await moderation_service.mute_user(bot, message.chat.id, target.id, 900)
            await message.reply(
                f"🚫 <b>{target.first_name}</b> ogohlantirishlar soni ({warn_limit}/{warn_limit}) to'ldi.\n"
                f"Guruhda 15 daqiqaga ovozi o'chirildi (Mute).",
                parse_mode="HTML"
            )
        elif punishment_type == "kick":
            await moderation_service.kick_user(bot, message.chat.id, target.id)
            await message.reply(
                f"👞 <b>{target.first_name}</b> ogohlantirishlar soni to'lgani uchun guruhdan chiqarildi.",
                parse_mode="HTML"
            )
        elif punishment_type == "ban":
            await moderation_service.ban_user(bot, message.chat.id, target.id)
            await message.reply(
                f"🔨 <b>{target.first_name}</b> ogohlantirishlar to'lgani uchun guruhdan bloklandi.",
                parse_mode="HTML"
            )
    else:
        await message.reply(
            f"⚠️ <b>{target.first_name}</b> ogohlantirish oldi!\n"
            f"Ogohlantirishlar: <b>{new_count}/{warn_limit}</b>",
            parse_mode="HTML"
        )


@router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    if not await permission_service.is_user_admin(
        bot,
        message.chat.id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    ):
        await message.reply("⛔ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchini mute qilish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    if await permission_service.is_user_admin(bot, message.chat.id, target.id, username=target.username, chat=message.chat):
        await message.reply("Adminlarni mute qilib bo'lmaydi.")
        return

    args = message.text.split()[1:] if message.text else []
    duration = 900
    if args:
        val = args[0].lower()
        if val.endswith("m") and val[:-1].isdigit():
            duration = int(val[:-1]) * 60
        elif val.endswith("h") and val[:-1].isdigit():
            duration = int(val[:-1]) * 3600
        elif val.isdigit():
            duration = int(val) * 60

    success = await moderation_service.mute_user(bot, message.chat.id, target.id, duration)
    if success:
        mins = duration // 60
        await message.reply(f"🔇 <b>{target.first_name}</b> {mins} daqiqaga mute qilindi.", parse_mode="HTML")
    else:
        await message.reply("❌ Foydalanuvchini mute qilib bo'lmadi. Botda kerakli admin huquqlari borligini tekshiring.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    if not await permission_service.is_user_admin(
        bot,
        message.chat.id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    ):
        await message.reply("⛔ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchini un-mute qilish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    success = await moderation_service.unmute_user(bot, message.chat.id, target.id)
    if success:
        warning_service.clear_warnings(message.chat.id, target.id)
        await message.reply(f"🔊 <b>{target.first_name}</b> uchun cheklovlar bekor qilindi.", parse_mode="HTML")
    else:
        await message.reply("❌ Cheklovni bekor qilishda xatolik yuz berdi.")


@router.message(Command("ban"))
async def cmd_ban(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    if not await permission_service.is_user_admin(
        bot,
        message.chat.id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    ):
        await message.reply("⛔ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchini ban qilish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot and target.id == bot.id:
        return

    if await permission_service.is_user_admin(bot, message.chat.id, target.id, username=target.username, chat=message.chat):
        await message.reply("Adminlarni ban qilib bo‘lmaydi.")
        return

    success = await moderation_service.ban_user(bot, message.chat.id, target.id)
    if success:
        await group_service.increment_group_stat(message.chat.id, "ban")
        await message.reply(f"🔨 <b>{target.first_name}</b> guruhdan bloklandi (Ban).", parse_mode="HTML")
    else:
        await message.reply("❌ Foydalanuvchini bloklab bo‘lmadi. Botda administrator huquqi borligini tekshiring.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    sender_chat_id = message.sender_chat.id if message.sender_chat else None
    sender_chat_username = message.sender_chat.username if message.sender_chat else None
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    if not await permission_service.is_user_admin(
        bot,
        message.chat.id,
        user_id,
        username=username,
        sender_chat_id=sender_chat_id,
        sender_chat_username=sender_chat_username,
        chat=message.chat,
        force_fresh=True,
    ):
        await message.reply("⛔ Bu amal faqat guruh adminlari uchun.")
        return

    target_id = None
    target_name = "Foydalanuvchi"
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or "Foydalanuvchi"
    else:
        args = message.text.split()[1:] if message.text else []
        if args and args[0].isdigit():
            target_id = int(args[0])

    if not target_id:
        await message.reply("⚠️ Foydalanuvchini bandan chiqarish uchun uning xabariga reply qiling yoki Telegram ID raqamini yozing: <code>/unban 12345678</code>", parse_mode="HTML")
        return

    success = await moderation_service.unban_user(bot, message.chat.id, target_id)
    if success:
        await message.reply(f"✅ <b>{target_name}</b> (<code>{target_id}</code>) blokdan chiqarildi.", parse_mode="HTML")
    else:
        await message.reply("❌ Foydalanuvchini blokdan chiqarib bo‘lmadi.")


@router.callback_query(F.data == "common:close")
async def cb_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
