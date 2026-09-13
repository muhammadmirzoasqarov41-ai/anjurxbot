"""
Telegram Handlers for RSS Feeds and Telegram Channel Sources.
Implements:
- Step-by-step interactive FSM flows for Website/RSS sources and Telegram Channel sources
- Clear, jargon-free Uzbek prompts and validation errors
- Source deletion and management (Mening manbalarim)
- Backward-compatible /sub, /unsub, /rss, /export, /allunsub commands
"""
import io
import re
import logging
from typing import Optional
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from app.config import config
from app.services.permission_service import permission_service, is_super_admin
from app.services.rss_storage import rss_storage
from app.services.feed_fetcher import feed_fetcher
from app.services.feed_parser import escape_tg_html, parse_opml
from app.states.rss import AddRssState, AddTelegramSourceState
from app.keyboards.rss import (
    get_main_menu_keyboard,
    get_destination_selection_keyboard,
    get_connection_confirm_keyboard,
    get_sources_list_keyboard,
    get_delete_source_confirm_keyboard,
    get_cancel_keyboard,
    get_rss_list_keyboard,
    get_unsub_confirm_keyboard,
    get_allunsub_confirm_keyboard,
)

logger = logging.getLogger("anjurxbot.rss_handler")
router = Router(name="rss_router")


def extract_url(text: str) -> Optional[str]:
    """Extracts first valid HTTP/HTTPS URL from command arguments or message text."""
    clean = text.strip()
    match = re.search(r'(https?://[^\s]+)', clean)
    if match:
        return match.group(1)
    if "." in clean and not clean.startswith("@") and not " " in clean:
        return f"https://{clean}"
    return None


# ==============================================================================
# 1. Step-by-Step Flow: Website / RSS qo'shish
# ==============================================================================
@router.callback_query(F.data == "menu_add_rss")
async def cb_start_add_rss(callback: CallbackQuery, state: FSMContext):
    """Step 1: Prompts user to send website or RSS link."""
    await state.set_state(AddRssState.waiting_for_url)
    text = (
        "🌐 <b>Sayt yoki RSS qo‘shish</b>\n\n"
        "Sayt yoki RSS lentasi havolasini yuboring:\n"
        "Masalan: <code>kun.uz</code> yoki <code>https://kun.uz/news/rss</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.message(AddRssState.waiting_for_url)
async def process_rss_url(message: Message, state: FSMContext, bot: Bot):
    """Step 2 & 3: Validates URL, detects RSS/Atom/JSON feed and site title."""
    url = extract_url(message.text or "")
    if not url:
        await message.reply(
            "❌ <b>Noto‘g‘ri havola kiritildi.</b>\n\n"
            "Iltimos, to‘g‘ri sayt yoki RSS havolasini yuboring (masalan: <code>kun.uz</code>):",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    status_msg = await message.reply("⏳ <i>Sayt tekshirilmoqda va RSS lentasi qidirilmoqda...</i>", parse_mode="HTML")

    try:
        parsed_feed, status, etag, lm, _ = await feed_fetcher.fetch_and_parse(url)
        if not parsed_feed:
            await status_msg.edit_text(
                "❌ <b>Bu manbani o‘qib bo‘lmadi.</b>\n\n"
                "Sayt RSS lentasiga ruxsat bermayotgan bo‘lishi yoki havola noto‘g‘ri bo‘lishi mumkin.\n"
                "Boshqa havola yuborib ko‘ring:",
                reply_markup=get_cancel_keyboard(),
                parse_mode="HTML",
            )
            return

        feed_title = parsed_feed.title or url
        feed_link = parsed_feed.link or url
        seen_hashes = [item.get_hash() for item in parsed_feed.items]

        # Save feed info in FSM state
        await state.update_data(
            url=url,
            title=feed_title,
            link=feed_link,
            seen_hashes=seen_hashes,
        )

        # Step 4: Ask user which destination channel to send news to
        user_id = message.from_user.id if message.from_user else 0
        destinations = await rss_storage.get_destinations_for_user(user_id)

        keyboard = get_destination_selection_keyboard(
            destinations=destinations,
            callback_prefix="rss_dest_sel",
            user_id=user_id,
        )

        await state.set_state(AddRssState.waiting_for_destination)
        await status_msg.edit_text(
            f"✅ <b>Manba topildi:</b> {escape_tg_html(feed_title)}\n\n"
            "Qaysi kanalga postlar yuborilsin? Kanalni tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Error checking RSS URL {url}: {e}")
        await status_msg.edit_text(
            "❌ <b>Manbani tekshirishda xatolik yuz berdi.</b>\nIltimos, qaytadan urinib ko‘ring.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )


@router.callback_query(AddRssState.waiting_for_destination, F.data.startswith("rss_dest_sel:"))
async def process_rss_destination_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Step 5: User selected destination channel, show confirmation."""
    chat_id_str = callback.data.split(":", 1)[1]
    try:
        dest_id = int(chat_id_str)
    except ValueError:
        await callback.answer("Noto'g'ri kanal tanlandi", show_alert=True)
        return

    data = await state.get_data()
    feed_title = data.get("title", "RSS Manba")

    dest_item = await rss_storage.get_destination(dest_id)
    if dest_item:
        dest_title = dest_item.title
    elif dest_id == callback.from_user.id:
        dest_title = "Shaxsiy chat"
    else:
        dest_title = f"Chat {dest_id}"

    await state.update_data(destination_id=dest_id, destination_title=dest_title)
    await state.set_state(AddRssState.waiting_for_confirm)

    confirm_text = (
        "📰 <b>Tasdiqlash</b>\n\n"
        f"🌐 <b>Manba:</b> {escape_tg_html(feed_title)}\n"
        f"📢 <b>Kanal:</b> {escape_tg_html(dest_title)}\n\n"
        "Ushbu manbani kanalga ulamoqchimisiz?"
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_connection_confirm_keyboard("rss_confirm_yes"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(AddRssState.waiting_for_confirm, F.data == "rss_confirm_yes")
async def process_rss_confirm(callback: CallbackQuery, state: FSMContext):
    """Step 6: Confirm and connect RSS source to destination."""
    data = await state.get_data()
    url = data.get("url")
    title = data.get("title", "RSS Manba")
    link = data.get("link", url)
    dest_id = data.get("destination_id")
    dest_title = data.get("destination_title", "Kanal")
    seen_hashes = data.get("seen_hashes", [])
    user_id = callback.from_user.id if callback.from_user else 0

    if not url or not dest_id:
        await callback.message.edit_text("❌ Ma'lumotlar topilmadi. Qaytadan urinib ko'ring.")
        await state.clear()
        return

    # Add RSS source to storage
    await rss_storage.add_rss_source(
        url=url,
        title=title,
        link=link,
        destination_chat_id=dest_id,
        owner_id=user_id,
        seen_hashes=seen_hashes,
    )

    await state.clear()
    success_text = (
        "✅ <b>Muvaffaqiyatli ulandi!</b>\n\n"
        f"Endi <b>{escape_tg_html(title)}</b> saytidan yangi maqolalar "
        f"<b>{escape_tg_html(dest_title)}</b> kanaliga avtomatik yetkaziladi."
    )
    keyboard = get_main_menu_keyboard(user_id=user_id)
    await callback.message.edit_text(
        success_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer("Ulandi!")


# ==============================================================================
# 2. Step-by-Step Flow: Telegram kanal qo'shish (Source)
# ==============================================================================
@router.callback_query(F.data == "menu_add_tg_source")
async def cb_start_add_tg_source(callback: CallbackQuery, state: FSMContext):
    """Step 1: Prompts user to specify source Telegram channel."""
    await state.set_state(AddTelegramSourceState.waiting_for_source)
    text = (
        "📢 <b>Telegram kanal qo‘shish (Manba)</b>\n\n"
        "Boshqa bir Telegram kanalidagi postlarni o‘z kanalingizga nusxalab borishingiz mumkin.\n\n"
        "<b>Qanday qilinadi:</b>\n"
        "1. Botni manba kanalga administrator yoki a‘zo qilib qo‘shing;\n"
        "2. Kanal usernamesini (@manba_kanal) yuboring yoki o‘sha kanaldan bitta postni bu yerga <b>Forward</b> qiling:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.message(AddTelegramSourceState.waiting_for_source)
async def process_tg_source(message: Message, state: FSMContext, bot: Bot):
    """Step 2: Resolves Telegram source channel via username, ID or forwarded post."""
    source_chat_id: Optional[int] = None
    source_title: str = ""
    source_username: Optional[str] = None

    # Case A: Forwarded message from a channel
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        source_chat_id = message.forward_from_chat.id
        source_title = message.forward_from_chat.title or f"Kanal {source_chat_id}"
        source_username = message.forward_from_chat.username

    # Case B: Text containing @username, t.me link or channel ID
    else:
        raw_text = (message.text or "").strip()
        # Handle t.me/joinchat or t.me/username
        if "t.me/" in raw_text:
            raw_text = raw_text.split("t.me/")[-1].split("/")[0].split("?")[0]

        target = raw_text.lstrip("@")
        try:
            if target.startswith("-100") and target[4:].isdigit():
                chat_obj = await bot.get_chat(int(target))
            else:
                chat_obj = await bot.get_chat(f"@{target}" if not target.startswith("-") else int(target))

            source_chat_id = chat_obj.id
            source_title = chat_obj.title or f"Kanal {source_chat_id}"
            source_username = chat_obj.username
        except Exception as e:
            logger.warning(f"Could not resolve Telegram channel '{raw_text}': {e}")

    if not source_chat_id:
        await message.reply(
            "❌ <b>Manba kanalga kirish yo‘q.</b>\n\n"
            "Bot manba kanalni o‘qiy olmadi. Botni manba kanalga a‘zo yoki administrator qilib "
            "qo‘shganingizga ishonch hosil qiling va qayta urinib ko‘ring:\n"
            "<i>(Masalan: @manba_kanal yoki kanaldan post forward qiling)</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    # Check if bot can actually read this chat
    try:
        bot_member = await bot.get_chat_member(source_chat_id, bot.id)
    except Exception as e:
        logger.warning(f"Bot cannot access chat {source_chat_id}: {e}")
        await message.reply(
            f"❌ <b>Bot '{escape_tg_html(source_title)}' kanaliga kira olmadi.</b>\n\n"
            "Botni manba kanalga a‘zo yoki administrator qilib qo‘shing.",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    await state.update_data(
        source_chat_id=source_chat_id,
        source_title=source_title,
        source_username=source_username,
    )

    # Step 3: Ask user for destination channel
    user_id = message.from_user.id if message.from_user else 0
    destinations = await rss_storage.get_destinations_for_user(user_id)

    # Filter out the source channel itself to prevent loops
    valid_dests = [d for d in destinations if d.chat_id != source_chat_id]

    keyboard = get_destination_selection_keyboard(
        destinations=valid_dests,
        callback_prefix="tg_dest_sel",
        user_id=user_id,
    )

    await state.set_state(AddTelegramSourceState.waiting_for_destination)
    await message.reply(
        f"✅ <b>Manba kanal topildi:</b> {escape_tg_html(source_title)}\n\n"
        "Postlar qaysi kanalga nusxalansin? O‘z kanalingizni tanlang:",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(AddTelegramSourceState.waiting_for_destination, F.data.startswith("tg_dest_sel:"))
async def process_tg_destination_selection(callback: CallbackQuery, state: FSMContext):
    """Step 4: User selected destination channel, show confirmation."""
    chat_id_str = callback.data.split(":", 1)[1]
    try:
        dest_id = int(chat_id_str)
    except ValueError:
        await callback.answer("Noto'g'ri kanal tanlandi", show_alert=True)
        return

    data = await state.get_data()
    source_title = data.get("source_title", "Manba Kanal")

    dest_item = await rss_storage.get_destination(dest_id)
    if dest_item:
        dest_title = dest_item.title
    elif dest_id == callback.from_user.id:
        dest_title = "Shaxsiy chat"
    else:
        dest_title = f"Chat {dest_id}"

    await state.update_data(destination_id=dest_id, destination_title=dest_title)
    await state.set_state(AddTelegramSourceState.waiting_for_confirm)

    confirm_text = (
        "📢 <b>Tasdiqlash</b>\n\n"
        f"📤 <b>Manba kanal:</b> {escape_tg_html(source_title)}\n"
        f"📥 <b>Destination kanal:</b> {escape_tg_html(dest_title)}\n\n"
        "Postlar muallif/forward yozuvisiz toza nusxalanadi.\n"
        "Ushbu ulanishni faollashtirasizmi?"
    )

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_connection_confirm_keyboard("tg_confirm_yes"),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(AddTelegramSourceState.waiting_for_confirm, F.data == "tg_confirm_yes")
async def process_tg_confirm(callback: CallbackQuery, state: FSMContext):
    """Step 5: Confirm and save Telegram channel source."""
    data = await state.get_data()
    source_chat_id = data.get("source_chat_id")
    source_title = data.get("source_title", "Manba Kanal")
    source_username = data.get("source_username")
    dest_id = data.get("destination_id")
    dest_title = data.get("destination_title", "Kanal")
    user_id = callback.from_user.id if callback.from_user else 0

    if not source_chat_id or not dest_id:
        await callback.message.edit_text("❌ Ma'lumotlar topilmadi. Qaytadan urinib ko'ring.")
        await state.clear()
        return

    await rss_storage.add_telegram_source(
        source_chat_id=source_chat_id,
        source_title=source_title,
        source_username=source_username,
        destination_chat_id=dest_id,
        owner_id=user_id,
    )

    await state.clear()
    success_text = (
        "✅ <b>Telegram kanal manbasi muvaffaqiyatli ulandi!</b>\n\n"
        f"Endi <b>{escape_tg_html(source_title)}</b> kanaliga yangi post chiqqanda, "
        f"u <b>{escape_tg_html(dest_title)}</b> kanaliga avtomatik nusxalanadi (Forward yozuvisiz)."
    )
    keyboard = get_main_menu_keyboard(user_id=user_id)
    await callback.message.edit_text(
        success_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer("Ulandi!")


# ==============================================================================
# 3. Mening manbalarim & Source Deletion
# ==============================================================================
@router.callback_query(F.data == "menu_my_sources")
async def cb_my_sources(callback: CallbackQuery, state: FSMContext):
    """Displays user's active sources with deletion buttons."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    sources = await rss_storage.get_sources_for_user(user_id)

    if not sources:
        text = (
            "📋 <b>Mening manbalarim</b>\n\n"
            "Sizda hali birorta ham ulangan manba yo‘q.\n\n"
            "Saytlar (RSS) yoki boshqa Telegram kanallardan postlarni avtomatik "
            "yetkazish uchun quyidagi tugmalardan birini tanlang:"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌐 Sayt/RSS qo‘shish", callback_data="menu_add_rss"),
                    InlineKeyboardButton(text="📢 Telegram kanal qo‘shish", callback_data="menu_add_tg_source"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
                ],
            ]
        )
    else:
        text_lines = ["📋 <b>Sizning ulangan manbalaringiz:</b>\n"]
        for s in sources:
            icon = "🌐 RSS" if s.type == "rss" else "📢 TG"
            dest_count = len(s.destinations)
            text_lines.append(f"• {icon}: <b>{escape_tg_html(s.title)}</b> → {dest_count} ta kanal")
        text_lines.append("\n<i>Manbani o‘chirish uchun quyidagi tugmalardan birini bosing:</i>")
        text = "\n".join(text_lines)
        keyboard = get_sources_list_keyboard(sources)

    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data.startswith("del_src_ask:"))
async def cb_ask_delete_source(callback: CallbackQuery):
    """Asks confirmation before deleting source."""
    source_id = callback.data.split(":", 1)[1]
    source = await rss_storage.get_source(source_id)
    title = source.title if source else "Manba"

    confirm_text = (
        f"⚠️ <b>{escape_tg_html(title)}</b> manbasini rostdan ham o‘chirmoqchimisiz?\n\n"
        "O‘chirilgandan so‘ng bu manbadan postlar kanalingizga yuborilmaydi."
    )
    keyboard = get_delete_source_confirm_keyboard(source_id, title)
    await callback.message.edit_text(confirm_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("del_src_do:"))
async def cb_do_delete_source(callback: CallbackQuery):
    """Executes deletion of target source."""
    source_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0
    deleted = await rss_storage.delete_source(source_id, user_id=user_id)

    if deleted:
        await callback.answer("Manba o‘chirildi", show_alert=True)
    else:
        await callback.answer("O'chirishda xatolik yoki ruxsat yo'q", show_alert=True)

    await cb_my_sources(callback, FSMContext(None, None))  # refresh list


@router.callback_query(F.data == "menu_add_picker")
async def cb_add_picker(callback: CallbackQuery):
    """Picker to choose between RSS or Telegram Channel source."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌐 Sayt/RSS qo‘shish", callback_data="menu_add_rss"),
                InlineKeyboardButton(text="📢 Telegram kanal qo‘shish", callback_data="menu_add_tg_source"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="menu_my_sources"),
            ],
        ]
    )
    await callback.message.edit_text(
        "Qaysi turdagi manbani qo‘shmoqchisiz?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


# ==============================================================================
# 4. Settings (Sozlamalar)
# ==============================================================================
@router.callback_query(F.data == "menu_settings")
async def cb_settings(callback: CallbackQuery):
    """Displays user settings, statistics, and system parameters."""
    user_id = callback.from_user.id if callback.from_user else 0
    stats = await rss_storage.get_stats()
    user_sources = await rss_storage.get_sources_for_user(user_id)
    user_dests = await rss_storage.get_destinations_for_user(user_id)

    text = (
        "⚙️ <b>Sozlamalar va Ma‘lumotlar</b>\n\n"
        f"• <b>Sizning manbalaringiz:</b> {len(user_sources)} ta\n"
        f"• <b>Sizning kanallaringiz:</b> {len(user_dests)} ta\n"
        f"• <b>Yetkazilgan postlar:</b> {stats.get('posts_delivered', 0)} ta\n"
        f"• <b>Tekshirish intervali:</b> ~{config.min_interval // 60} daqiqa\n"
        f"• <b>Vaqt mintaqasi:</b> {config.timezone}\n\n"
        "<i>Barcha yangiliklar real-time vaqtlarda avtomatik tekshirilib yetkaziladi.</i>"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 OPML Eksport", callback_data="rss_export_opml"),
                InlineKeyboardButton(text="📢 Kanallarni tekshirish", callback_data="refresh_channels"),
            ],
            [
                InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main"),
            ],
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 5. Backward Compatibility: /sub, /unsub, /rss, /export, /allunsub
# ==============================================================================
@router.message(Command("sub"))
async def cmd_sub(message: Message, bot: Bot):
    """Legacy command: Subscribes current chat to an RSS feed."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await permission_service.can_user_manage_chat(bot, chat_id, user.id):
        await message.reply("⛔ Faqat administratorlar yangi obuna qo'shishi mumkin.")
        return

    url = extract_url(message.text or "")
    if not url:
        await message.reply(
            "ℹ️ <b>Foydalanish:</b>\n<code>/sub &lt;feed_url&gt;</code>\n\n"
            "<b>Misol:</b> <code>/sub https://kun.uz/news/rss</code>",
            parse_mode="HTML",
        )
        return

    status_msg = await message.reply("⏳ <i>Feed tekshirilmoqda...</i>", parse_mode="HTML")
    try:
        parsed_feed, status, etag, lm, _ = await feed_fetcher.fetch_and_parse(url)
        if not parsed_feed:
            await status_msg.edit_text(f"❌ <b>Feedni yuklab bo'lmadi.</b> (HTTP: {status})", parse_mode="HTML")
            return

        initial_seen = [item.get_hash() for item in parsed_feed.items]
        chat_title = message.chat.title or user.full_name or f"Chat {chat_id}"
        feed, is_new = await rss_storage.add_subscription(
            chat_id=chat_id,
            feed_url=url,
            title=parsed_feed.title or url,
            link=parsed_feed.link or url,
            description=parsed_feed.description or "",
            initial_seen_hashes=initial_seen,
            chat_title=chat_title,
            chat_type=message.chat.type,
        )
        await status_msg.edit_text(
            f"✅ <b>Muvaffaqiyatli obuna bo'lindi!</b>\n\n"
            f"📰 <b>Manba:</b> <a href=\"{feed.link}\">{escape_tg_html(feed.title)}</a>\n"
            f"🔗 <b>Lenta:</b> <code>{feed.url}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.error(f"Error in /sub: {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi.", parse_mode="HTML")


@router.message(Command("unsub"))
async def cmd_unsub(message: Message, bot: Bot):
    """Legacy command: Unsubscribes from an RSS feed."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await permission_service.can_user_manage_chat(bot, chat_id, user.id):
        await message.reply("⛔ Faqat administratorlar obunani bekor qilishi mumkin.")
        return

    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await message.reply("ℹ️ Ushbu chatda hozircha faol obunalar mavjud emas.")
        return

    keyboard = get_rss_list_keyboard(feeds)
    await message.reply("Bekor qilmoqchi bo'lgan obunani tanlang:", reply_markup=keyboard)


@router.message(Command("rss"))
async def cmd_rss(message: Message):
    """Legacy command: Lists subscriptions in chat."""
    chat_id = message.chat.id
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await message.reply("ℹ️ Ushbu chatda hozircha faol obunalar mavjud emas.")
        return

    lines = ["📋 <b>Faol obunalar:</b>\n"]
    for i, f in enumerate(feeds, 1):
        lines.append(f"{i}. <a href=\"{f.link}\">{escape_tg_html(f.title)}</a>\n   <code>{f.url}</code>")
    await message.reply("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("export"))
@router.callback_query(F.data == "rss_export_opml")
async def handle_export_opml(event, bot: Bot):
    """Exports subscriptions in standard OPML format."""
    message = event if isinstance(event, Message) else event.message
    chat_id = message.chat.id
    opml_xml = await rss_storage.export_opml(chat_id)
    file_bytes = opml_xml.encode("utf-8")
    input_file = BufferedInputFile(file_bytes, filename=f"anjurx_subscriptions_{chat_id}.opml")
    await message.answer_document(
        document=input_file,
        caption="📥 Sizning obunalaringiz OPML formatida.",
    )
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(Command("allunsub"))
async def cmd_allunsub(message: Message, bot: Bot):
    """Legacy command: Clears all subscriptions in chat."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await permission_service.can_user_manage_chat(bot, chat_id, user.id):
        await message.reply("⛔ Faqat administratorlar barcha obunalarni o'chirishi mumkin.")
        return

    count = await rss_storage.remove_all_subscriptions(chat_id)
    await message.reply(f"🗑 {count} ta obuna muvaffaqiyatli o'chirildi.")
