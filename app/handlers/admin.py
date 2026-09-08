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
    get_settings_guard_keyboard,
    get_settings_sec_keyboard,
    get_settings_warns_keyboard,
    get_settings_srv_keyboard,
    get_settings_presets_keyboard,
)
from app.keyboards.admin import (
    get_global_admin_keyboard,
    get_back_to_global_keyboard,
    get_back_to_settings_keyboard,
)
from app.keyboards.fsub import get_force_sub_admin_keyboard
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

    if message.chat.type not in ("group", "supergroup"):
        if config.is_super_admin(user_id):
            await message.reply(
                "⚙️ <b>Guruh Sozlamalari:</b>\n\n"
                "Guruh sozlamalarini boshqarish uchun ushbu buyruqni guruh ichida yuboring.\n"
                "Global bot boshqaruvi va umumiy statistika uchun: /admin buyrug'idan foydalaning.",
                parse_mode="HTML"
            )
        else:
            await message.reply(
                "❌ Bu buyruq faqat guruhlarda ishlaydi.\n"
                "Botni guruhingizga qo'shing va administrator huquqini bering.",
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
            "⛔ Bu bo'lim faqat guruh egasi va administratorlari uchun.",
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
        f"⚙️ <b>GURUH SOZLAMALARI:</b> {title}\n"
        f"ID: <code>{chat_id}</code>{warning_note}\n\n"
        f"Boshqarish uchun quyidagi bo'limlardan birini tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


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
        f"⚙️ <b>GURUH SOZLAMALARI:</b> {chat_title}\n"
        f"ID: <code>{group_id}</code>\n\n"
        f"Boshqarish uchun quyidagi bo'limlardan birini tanlang:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:guard:"))
@router.callback_query(F.data.startswith("guard:menu:"))
async def cb_settings_guard(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_guard_keyboard(group_id, guard)

    text = (
        "🛡 <b>Moderatsiya sozlamalari:</b>\n\n"
        "Guruhda xavfli havolalar, spam va reklamalarni nazorat qiling.\n"
        "Kerakli filtrni yoqish yoki o'chirish uchun tugmani bosing:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:sec:"))
async def cb_settings_sec(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_sec_keyboard(group_id, guard)

    text = (
        "🔒 <b>Xavfsizlik va Filtr sozlamalari:</b>\n\n"
        "Tez-tez yozish (Anti-Flood), bir xil xabarlarni qaytarish va "
        "uyatsiz/haqoratli so'zlarni avtomatik tozalash tizimi:"
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
        "🔔 <b>Ogohlantirish va Jazo Tizimi:</b>\n\n"
        f"• Ogohlantirish chegarasi: <b>{warn_limit} ta</b>\n"
        f"• Limit to'lgandagi jazo: <b>{punishment}</b>\n\n"
        "Qoidani buzgan a'zo limitga yetganda avtomatik ravishda tanlangan jazo qo'llaniladi.\n"
        "<i>Qo'lda ogohlantirish berish uchun uning xabariga reply qilib <code>/warn</code> yuboring.</i>"
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:srv:"))
async def cb_settings_srv(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    guard = group_config.get("guard_settings", {})
    keyboard = get_settings_srv_keyboard(group_id, guard)

    text = (
        "👋 <b>Xizmat Xabarlari Sozlamalari:</b>\n\n"
        "Guruhga yangi a'zo qo'shilganda yoki a'zo guruhdan chiqqanda paydo bo'ladigan "
        "xizmat xabarlarini avtomatik o'chirib tashlash:"
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
        "• <b>Qat'iy rejim:</b> Barcha himoyalar + Qayta xabar + So'kish filtri (Flood: 3 ta, Jazo: Mute)."
    )
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("settings:fsub:"))
@router.callback_query(F.data.startswith("fsub:menu:"))
async def cb_settings_fsub(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    fsub = group_config.get("force_sub", {})
    channels = fsub.get("channels", [])
    is_enabled = fsub.get("is_enabled", False)

    keyboard = get_force_sub_admin_keyboard(group_id, channels, is_enabled)
    text = (
        "📢 <b>Majburiy Obuna (Force Subscribe) Sozlamalari:</b>\n\n"
        "A'zolar guruhda xabar yozishi uchun ko'rsatilgan kanallarga obuna bo'lishi shart qilinadi.\n"
        "<i>Eslatma: Bot biriktirilgan kanallarda administrator bo'lishi zarur!</i>"
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


@router.callback_query(F.data == "common:close")
async def cb_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
