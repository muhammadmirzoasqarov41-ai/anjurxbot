"""
Super Admin Panel Handlers for AnjurX | Obuna Bot.
Strictly guarded by Telegram numeric User ID via is_super_admin().
Usernames are never used for privilege checks.

Implements:
- /admin and [👑 Super Admin Panel]
- [🌐 Manbalar (RSS)]: Add, View, Toggle, Delete verified sources
- [📢 Kanallar]: Complete overview of all connected channels across the platform
- [👥 Foydalanuvchilar]: User directory and Plan management
- [💼 Tariflar & Limitlar]: /set_contract command for custom limits
- [📦 Post Queue (5 kunlik hovuz)]: 5-Day Post Pool monitoring
- [📊 Umumiy Statistika]: Platform wide analytics
"""
import os
import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from app.config import config
from app.services.permission_service import is_super_admin
from app.services.rss_storage import rss_storage
from app.services.feed_fetcher import feed_fetcher
from app.keyboards.rss import (
    get_admin_dashboard_keyboard,
    get_admin_sources_keyboard,
    get_admin_source_detail_keyboard,
)
from app.states.rss import AdminAddSourceState

logger = logging.getLogger("anjurxbot.admin")
router = Router(name="admin_router")


# ==============================================================================
# 1. /admin & MAIN ADMIN DASHBOARD
# ==============================================================================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Opens Super Admin Panel if sender is verified Super Admin."""
    await state.clear()
    user = message.from_user
    user_id = user.id if user else 0

    if not is_super_admin(user_id):
        await message.reply(
            "⛔ <b>Kirish taqiqlangan.</b> Ushbu bo‘lim faqat bot egasi uchun.",
            parse_mode="HTML",
        )
        return

    stats = await rss_storage.get_stats()
    text = (
        "👑 <b>Super Admin Panel — AnjurX</b>\n\n"
        "Xush kelibsiz! Tizim boshqaruvi va monitoring bo‘limi.\n\n"
        f"• <b>Faol manbalar:</b> {stats.get('active_sources', 0)}/{stats.get('total_sources', 0)} ta\n"
        f"• <b>Ulangan kanallar:</b> {stats.get('active_channels', 0)}/{stats.get('total_destinations', 0)} ta\n"
        f"• <b>Post Pool (Navbatda):</b> {stats.get('pool_queued', 0)} ta post\n"
        f"• <b>Jami yetkazilgan:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Super Admin ID:</b> <code>{user_id}</code> (Tasdiqlangan)\n"
    )
    await message.answer(
        text,
        reply_markup=get_admin_dashboard_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin_panel_main")
async def cb_admin_panel_main(callback: CallbackQuery, state: FSMContext):
    """Callback for main admin panel."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    stats = await rss_storage.get_stats()
    text = (
        "👑 <b>Super Admin Panel — AnjurX</b>\n\n"
        f"• <b>Faol manbalar:</b> {stats.get('active_sources', 0)}/{stats.get('total_sources', 0)} ta\n"
        f"• <b>Ulangan kanallar:</b> {stats.get('active_channels', 0)}/{stats.get('total_destinations', 0)} ta\n"
        f"• <b>Post Pool (Navbatda):</b> {stats.get('pool_queued', 0)} ta post\n"
        f"• <b>Jami yetkazilgan:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Super Admin ID:</b> <code>{user_id}</code> (Tasdiqlangan)\n"
    )
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_admin_dashboard_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_admin_dashboard_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


# ==============================================================================
# 2. [🌐 MANBALAR] (Super Admin Verified Sources Manager)
# ==============================================================================

@router.callback_query(F.data == "admin_sources_list")
async def cb_admin_sources_list(callback: CallbackQuery, state: FSMContext):
    """Shows list of all verified sources with add/edit/delete actions."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    sources = await rss_storage.get_all_sources()
    text = (
        f"🌐 <b>Tizimdagi manbalar ({len(sources)} ta)</b>\n\n"
        "Ushbu manbalar oddiy foydalanuvchilar o‘z kanallariga ulashi uchun tayyorlangan "
        "tasdiqlangan manbalardir.\n\n"
        "Manba sozlamalarini ko‘rish uchun uning ustiga bosing:"
    )
    kb = get_admin_sources_keyboard(sources)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_src_add")
async def cb_admin_src_add(callback: CallbackQuery, state: FSMContext):
    """Prompts super admin to send an RSS/Atom feed URL."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    await state.set_state(AdminAddSourceState.waiting_for_url)
    text = (
        "➕ <b>Yangi manba qo‘shish (Super Admin)</b>\n\n"
        "Iltimos, RSS yoki Atom feed URL manzilini yuboring.\n"
        "<i>Misol: https://kun.uz/news/rss</i>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_sources_list")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(AdminAddSourceState.waiting_for_url)
async def process_admin_add_url(message: Message, state: FSMContext):
    """Validates RSS feed URL and adds source."""
    user_id = message.from_user.id if message.from_user else 0
    if not is_super_admin(user_id):
        await message.reply("⛔ Ruxsat berilmagan.", parse_mode="HTML")
        return

    url = (message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.reply("⚠️ Noto‘g‘ri havola formati. URL https:// bilan boshlanishi kerak.")
        return

    wait_msg = await message.reply("⏳ Feed tekshirilmoqda va tahlil qilinmoqda...")

    try:
        parsed, status, etag, last_mod, not_mod = await feed_fetcher.fetch_and_parse(url)
        feed_title = parsed.title if (parsed and parsed.title) else "Yangi Manba"
        category = "Yangiliklar"

        source = await rss_storage.add_source(
            name=feed_title,
            url=url,
            source_type="rss",
            category=category,
        )
        await state.clear()
        await wait_msg.edit_text(
            f"✅ <b>Manba muvaffaqiyatli qo‘shildi!</b>\n\n"
            f"• Nomi: <b>{source.name}</b>\n"
            f"• URL: <code>{source.url}</code>\n"
            f"• Kategoriya: {source.category}\n"
            f"• ID: <code>{source.id}</code>\n\n"
            "Endi ushbu manba barcha kanallar uchun tanlov ro‘yxatida mavjud.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Manbalarga qaytish", callback_data="admin_sources_list")],
                ]
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error adding source {url}: {e}")
        await wait_msg.edit_text(
            f"❌ <b>Feedni yuklab bo‘lmadi:</b> {e}\n\n"
            "Havola to‘g‘riligini va sayt RSS xizmati ishlayotganini tekshiring.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_sources_list")]
                ]
            ),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("admin_src_view:"))
async def cb_admin_src_view(callback: CallbackQuery):
    """Views individual source details."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    source_id = callback.data.split(":")[1]
    source = await rss_storage.get_source(source_id)
    if not source:
        await callback.answer("Manba topilmadi.", show_alert=True)
        return

    status_str = "🟢 Faol" if source.active else "⏸ To‘xtatilgan"
    last_fetch = source.last_fetch_at or "Hali yuklanmagan"

    text = (
        f"🌐 <b>Manba tafsilotlari</b>\n\n"
        f"• <b>Nomi:</b> {source.name}\n"
        f"• <b>URL:</b> <code>{source.url}</code>\n"
        f"• <b>Holat:</b> {status_str}\n"
        f"• <b>Kategoriya:</b> {source.category}\n"
        f"• <b>Oxirgi tekshirish:</b> <code>{last_fetch}</code>\n"
        f"• <b>Xatolar soni:</b> {source.error_count}\n"
        f"• <b>ID:</b> <code>{source.id}</code>\n"
    )
    kb = get_admin_source_detail_keyboard(source)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_src_toggle:"))
async def cb_admin_src_toggle(callback: CallbackQuery):
    """Toggles source active/paused state."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    source_id = callback.data.split(":")[1]
    new_state = await rss_storage.toggle_source(source_id)
    if new_state is not None:
        action = "🟢 Manba faollashtirildi" if new_state else "⏸ Manba to‘xtatildi"
        await callback.answer(action, show_alert=False)
        await cb_admin_src_view(callback)
    else:
        await callback.answer("Manba topilmadi.", show_alert=True)


@router.callback_query(F.data.startswith("admin_src_del:"))
async def cb_admin_src_del(callback: CallbackQuery):
    """Deletes source from system."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    source_id = callback.data.split(":")[1]
    deleted = await rss_storage.delete_source(source_id)
    if deleted:
        await callback.answer("🗑 Manba tizimdan o‘chirildi.", show_alert=True)
        await cb_admin_sources_list(callback, FSMContext)
    else:
        await callback.answer("O‘chirishda xatolik.", show_alert=True)


# ==============================================================================
# 3. [📢 KANALLAR] (All Connected Channels in the Platform)
# ==============================================================================

@router.callback_query(F.data == "admin_channels_list")
async def cb_admin_channels_list(callback: CallbackQuery):
    """Lists all channels registered across the platform."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    channels = await rss_storage.get_all_channels()
    if not channels:
        text = "ℹ️ <b>Hozircha tizimda birorta ham kanal ulanmagan.</b>"
    else:
        lines = [f"📢 <b>Tizimga ulangan barcha kanallar ({len(channels)} ta):</b>\n"]
        for i, ch in enumerate(channels[:25], 1):
            ch.reset_daily_if_needed()
            st = "🟢" if (ch.active and ch.can_post) else ("⏸" if not ch.active else "⚠️")
            plan_tag = " [💼 Shartnoma]" if ch.plan == "contract" else ""
            lines.append(
                f"{i}. {st} <b>{ch.title}</b>{plan_tag}\n"
                f"   ID: <code>{ch.chat_id}</code> | Bugun: {ch.today_delivered_count}/{ch.daily_limit} | "
                f"Egasi: <code>{ch.owner_user_id}</code>"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 4. [👥 FOYDALANUVCHILAR] & [💼 TARIFLAR]
# ==============================================================================

@router.callback_query(F.data == "admin_users_list")
async def cb_admin_users_list(callback: CallbackQuery):
    """Displays registered users and their current plans."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    users = await rss_storage.get_all_users()
    lines = [f"👥 <b>Ro‘yxatdan o‘tgan foydalanuvchilar ({len(users)} ta):</b>\n"]
    for i, u in enumerate(users[:25], 1):
        uname = f"@{u.username}" if u.username else u.first_name or f"User {u.user_id}"
        plan_str = f"💼 Shartnoma ({u.custom_limit or 10} post)" if u.plan == "contract" else "Standart (3 post)"
        lines.append(f"{i}. <b>{uname}</b> (<code>{u.user_id}</code>) — {plan_str}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💼 Tarif o‘zgartirish", callback_data="admin_tariffs")],
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")],
        ]
    )
    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_tariffs")
async def cb_admin_tariffs(callback: CallbackQuery):
    """Tariffs and contract plans management guide."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    text = (
        "💼 <b>Tariflar va Limitlar Boshqaruvi</b>\n\n"
        "Standart bepul foydalanuvchilar uchun kanal limitlari qat’iy <b>3 ta post/kun</b>.\n\n"
        "Agar foydalanuvchi yoki kanal bilan maxsus shartnoma tuzilgan bo‘lsa, limitni "
        "quyidagi buyruq orqali o‘rnatishingiz mumkin:\n\n"
        "<code>/set_contract &lt;user_id&gt; &lt;kunlik_limit&gt;</code>\n\n"
        "<i>Misol:</i>\n"
        "<code>/set_contract 123456789 20</code>\n"
        "(Ushbu foydalanuvchining barcha kanallari uchun kunlik 20 ta post limiti beriladi)"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(Command("set_contract"))
async def cmd_set_contract(message: Message):
    """Command handler for Super Admin to assign contract plan and custom limit."""
    user_id = message.from_user.id if message.from_user else 0
    if not is_super_admin(user_id):
        return

    args = (message.text or "").split()[1:]
    if len(args) < 2:
        await message.reply(
            "⚠️ <b>Noto‘g‘ri format!</b>\n\n"
            "Format: <code>/set_contract &lt;user_id&gt; &lt;limit&gt;</code>\n"
            "Misol: <code>/set_contract 123456789 25</code>",
            parse_mode="HTML",
        )
        return

    try:
        target_uid = int(args[0])
        limit_val = int(args[1])
    except ValueError:
        await message.reply("⚠️ user_id va limit butun son bo‘lishi kerak.")
        return

    user = await rss_storage.set_user_contract_plan(target_uid, plan="contract", custom_limit=limit_val)
    await message.reply(
        f"✅ <b>Foydalanuvchiga shartnoma tarifi berildi!</b>\n\n"
        f"• User ID: <code>{target_uid}</code>\n"
        f"• Kunlik limit: <b>{limit_val} ta post</b>\n"
        f"Ushbu foydalanuvchiga tegishli barcha kanallar limiti yangilandi.",
        parse_mode="HTML",
    )


# ==============================================================================
# 5. [📦 POST QUEUE (5 KUNLIK HOVUZ)] & [📊 STATISTIKA]
# ==============================================================================

@router.callback_query(F.data == "admin_queue_stats")
async def cb_admin_queue_stats(callback: CallbackQuery):
    """Monitors 5-Day Retention Post Pool status."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    stats = await rss_storage.get_stats()
    text = (
        "📦 <b>5 Kunlik Post Hovuzi (Post Retention Pool)</b>\n\n"
        "Kelayotgan barcha RSS yangiliklar bazada <b>5 kun</b> davomida saqlanadi "
        "va navbat asosida kanallarga adolatli (Fair Round Robin) taqsimlanadi.\n\n"
        f"• <b>Navbatda turgan postlar:</b> {stats.get('pool_queued', 0)} ta\n"
        f"• <b>Yetkazilgan postlar:</b> {stats.get('pool_delivered', 0)} ta\n"
        f"• <b>Muddati o‘tgan (5 kundan eski):</b> {stats.get('pool_expired', 0)} ta\n"
        f"• <b>Yetkazishda xatolik bo‘lgan:</b> {stats.get('pool_failed', 0)} ta\n"
        f"• <b>Hovuzdagi jami postlar:</b> {stats.get('total_in_pool', 0)} ta\n\n"
        "<i>5 kundan oshgan postlar avtomatik ravishda tozalanadi, takroriy yuborishdan himoya "
        "kalitlari esa butunlay saqlanib qoladi.</i>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    """Platform-wide analytics."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    stats = await rss_storage.get_stats()
    text = (
        "📊 <b>Umumiy Tizim Statistikasi</b>\n\n"
        f"• <b>Manbalar soni:</b> {stats.get('total_sources', 0)} ta (Faol: {stats.get('active_sources', 0)})\n"
        f"• <b>Kanallar soni:</b> {stats.get('total_destinations', 0)} ta (Faol: {stats.get('active_channels', 0)})\n"
        f"• <b>Foydalanuvchilar:</b> {stats.get('total_users', 0)} ta\n"
        f"• <b>Jami yetkazilgan postlar:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Post Pool navbatida:</b> {stats.get('pool_queued', 0)} ta post\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    """Global system configuration view."""
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_super_admin(user_id):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    db_path = rss_storage.db_path
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    text = (
        "⚙️ <b>Tizim Sozlamalari va Ma’lumotlar</b>\n\n"
        f"• <b>Baza fayli:</b> <code>{db_path}</code>\n"
        f"• <b>Fayl hajmi:</b> {db_size} bayt\n"
        f"• <b>5 Kunlik Retensiya:</b> Faol (Avtomatik tozalash)\n"
        f"• <b>Standart limit:</b> 3 ta post/kun (Free plan)\n"
        f"• <b>Taqsimlash algoritmi:</b> Least Delivered Fair Round Robin\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Admin Panel", callback_data="admin_panel_main")]
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
