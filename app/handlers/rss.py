"""
Telegram Handlers for AnjurX | Rss Bot.
Implements /sub, /unsub, /rss, /export, /import, /allunsub commands
and interactive inline keyboard callbacks.
"""
import io
import logging
from typing import Optional
from urllib.parse import urlparse
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BufferedInputFile,
)

from app.services.rss_storage import rss_storage
from app.services.feed_fetcher import feed_fetcher
from app.services.feed_parser import escape_tg_html, parse_opml
from app.keyboards.rss import (
    get_rss_list_keyboard,
    get_unsub_confirm_keyboard,
    get_allunsub_confirm_keyboard,
)

logger = logging.getLogger("anjurxbot.rss_handler")
router = Router(name="rss_router")


async def is_admin_or_private(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Checks if command sender is administrator in group/channel, or in private chat."""
    if chat_id > 0:
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception as e:
        logger.warning(f"Could not verify admin status for user {user_id} in {chat_id}: {e}")
        return False


def extract_url(text: str) -> Optional[str]:
    """Extracts first valid HTTP/HTTPS URL from command arguments."""
    parts = text.split()
    for part in parts[1:]:
        clean = part.strip()
        if clean.startswith(("http://", "https://")):
            return clean
    return None


# --------------------------------------------------------------------------
# /sub <URL>
# --------------------------------------------------------------------------
@router.message(Command("sub"))
async def cmd_sub(message: Message, bot: Bot):
    """Subscribes current chat to an RSS/Atom/JSON feed."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    # Check admin privileges in groups/channels
    if not await is_admin_or_private(bot, chat_id, user.id):
        await message.reply("⛔ Faqat guruh/kanal administratorlari yangi feed qo'shishi mumkin.")
        return

    url = extract_url(message.text or "")
    if not url:
        await message.reply(
            "ℹ️ <b>Foydalanish:</b>\n<code>/sub &lt;feed_url&gt;</code>\n\n"
            "<b>Misollar:</b>\n"
            "• <code>/sub https://kun.uz/news/rss</code>\n"
            "• <code>/sub https://daryo.uz/rss/</code>\n"
            "• <code>/sub https://news.ycombinator.com/rss</code>\n"
            "• <code>/sub https://techcrunch.com</code> <i>(avtomatik aniqlanadi)</i>",
            parse_mode="HTML",
        )
        return

    status_msg = await message.reply("⏳ <i>Feed tekshirilmoqda va obuna qilinmoqda...</i>", parse_mode="HTML")

    try:
        parsed_feed, status, etag, lm, _ = await feed_fetcher.fetch_and_parse(url)
        if not parsed_feed:
            await status_msg.edit_text(
                f"❌ <b>Feedni yuklab bo'lmadi.</b>\nHTTP status: {status}\nIltimos, havola to'g'riligini tekshiring.",
                parse_mode="HTML",
            )
            return

        # Seed existing item hashes so old posts aren't spammed
        initial_seen = [item.get_hash() for item in parsed_feed.items]

        chat_title = message.chat.title or user.full_name or f"Chat {chat_id}"
        chat_type = message.chat.type

        feed, is_new = await rss_storage.add_subscription(
            chat_id=chat_id,
            feed_url=parsed_feed.feed_url,
            title=parsed_feed.title,
            link=parsed_feed.link,
            description=parsed_feed.description,
            initial_seen_hashes=initial_seen,
            chat_title=chat_title,
            chat_type=chat_type,
        )

        title_esc = escape_tg_html(feed.title)
        link_esc = escape_tg_html(feed.link)

        reply_text = (
            f"✅ <b>Muvaffaqiyatli obuna bo'lindi!</b>\n\n"
            f"📰 <b>Nomi:</b> <a href=\"{link_esc}\">{title_esc}</a>\n"
            f"🔗 <b>Feed:</b> <code>{escape_tg_html(feed.url)}</code>\n"
            f"📦 <b>Mavjud maqolalar:</b> {len(parsed_feed.items)} ta\n\n"
            f"🔔 Yangi postlar e'lon qilinganda ushbu chatga avtomatik yetkaziladi."
        )

        await status_msg.edit_text(reply_text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error subscribing chat {chat_id} to {url}: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Xatolik yuz berdi:</b>\n<code>{escape_tg_html(str(e))}</code>",
            parse_mode="HTML",
        )


# --------------------------------------------------------------------------
# /unsub [URL]
# --------------------------------------------------------------------------
@router.message(Command("unsub"))
async def cmd_unsub(message: Message, bot: Bot):
    """Unsubscribes from an RSS feed or shows interactive unsubscribe menu."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await is_admin_or_private(bot, chat_id, user.id):
        await message.reply("⛔ Faqat guruh/kanal administratorlari obunani bekor qilishi mumkin.")
        return

    url = extract_url(message.text or "")
    if url:
        # Direct unsubscribe by URL
        success = await rss_storage.remove_subscription(chat_id, url)
        if success:
            await message.reply(
                f"✅ Obuna bekor qilindi:\n<code>{escape_tg_html(url)}</code>",
                parse_mode="HTML",
            )
        else:
            await message.reply("⚠️ Ushbu havola bo'yicha faol obuna topilmadi.")
        return

    # No URL provided: show list of subscribed feeds with 1-tap delete buttons
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await message.reply("ℹ️ Ushbu chatda hech qanday faol RSS obuna mavjud emas.")
        return

    keyboard = get_rss_list_keyboard(feeds)
    await message.reply(
        f"📋 <b>Bekor qilmoqchi bo'lgan obunani tanlang ({len(feeds)} ta mavjud):</b>",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# --------------------------------------------------------------------------
# /rss [raw]
# --------------------------------------------------------------------------
@router.message(Command("rss"))
async def cmd_rss(message: Message):
    """Lists all active RSS subscriptions for the current chat."""
    chat_id = message.chat.id
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)

    if not feeds:
        await message.reply(
            "📭 <b>Sizda hali faol RSS obunalar yo'q.</b>\n\n"
            "Yangi feed qo'shish uchun: <code>/sub &lt;url&gt;</code> yuboring.",
            parse_mode="HTML",
        )
        return

    is_raw = "raw" in (message.text or "").lower()

    if is_raw:
        lines = [f"📋 <b>Joriy obunalar ro'yxati ({len(feeds)} ta):</b>\n"]
        for idx, f in enumerate(feeds, start=1):
            lines.append(f"{idx}. <code>{escape_tg_html(f.url)}</code>")
        await message.reply("\n".join(lines), parse_mode="HTML")
        return

    lines = [f"📋 <b>Joriy RSS obunalar ({len(feeds)} ta):</b>\n"]
    for idx, f in enumerate(feeds, start=1):
        title_esc = escape_tg_html(f.title)
        link_esc = escape_tg_html(f.link or f.url)
        lines.append(f"{idx}. <a href=\"{link_esc}\">{title_esc}</a>")

    lines.append("\n<i>O'chirish uchun /unsub yoki quyidagi tugmalardan foydalaning:</i>")
    keyboard = get_rss_list_keyboard(feeds)
    await message.reply("\n".join(lines), reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)


# --------------------------------------------------------------------------
# /export
# --------------------------------------------------------------------------
@router.message(Command("export"))
async def cmd_export(message: Message):
    """Exports chat's subscriptions as an OPML file."""
    chat_id = message.chat.id
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)

    if not feeds:
        await message.reply("📭 Eksport qilish uchun hech qanday obuna topilmadi.")
        return

    opml_xml = await rss_storage.export_opml(chat_id)
    doc = BufferedInputFile(
        file=opml_xml.encode("utf-8"),
        filename=f"anjurx_rss_chat_{abs(chat_id)}.opml",
    )
    await message.reply_document(
        document=doc,
        caption=f"📦 <b>AnjurX | Rss Bot</b>\nSizning obunalaringiz ({len(feeds)} ta feed) OPML formatida eksport qilindi.",
        parse_mode="HTML",
    )


# --------------------------------------------------------------------------
# /allunsub
# --------------------------------------------------------------------------
@router.message(Command("allunsub"))
async def cmd_allunsub(message: Message, bot: Bot):
    """Asks confirmation to remove all subscriptions for this chat."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await is_admin_or_private(bot, chat_id, user.id):
        await message.reply("⛔ Faqat administratorlar barcha obunalarni o'chirishi mumkin.")
        return

    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await message.reply("📭 Ushbu chatda hech qanday faol obuna mavjud emas.")
        return

    keyboard = get_allunsub_confirm_keyboard()
    await message.reply(
        f"⚠️ <b>Diqqat!</b> Ushbu chatdagi barcha <b>{len(feeds)} ta</b> RSS obunani o'chirmoqchimisiz?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# --------------------------------------------------------------------------
# OPML Document Import Handler
# --------------------------------------------------------------------------
@router.message(F.document)
async def handle_opml_import_document(message: Message, bot: Bot):
    """Handles an uploaded OPML document to bulk-subscribe to feeds."""
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    doc = message.document
    if not doc or not doc.file_name:
        return

    # Check if file is OPML or XML
    filename = doc.file_name.lower()
    if not (filename.endswith(".opml") or filename.endswith(".xml")):
        return

    if not await is_admin_or_private(bot, chat_id, user.id):
        await message.reply("⛔ Faqat administratorlar OPML orqali obuna qo'shishi mumkin.")
        return

    status_msg = await message.reply("📥 <i>OPML fayl o'qilmoqda...</i>", parse_mode="HTML")

    try:
        file_obj = await bot.get_file(doc.file_id)
        if not file_obj.file_path:
            await status_msg.edit_text("❌ Faylni yuklab bo'lmadi.")
            return

        file_bytes = await bot.download_file(file_obj.file_path)
        content_str = file_bytes.read().decode("utf-8", errors="replace")

        feed_tuples = parse_opml(content_str)
        if not feed_tuples:
            await status_msg.edit_text("⚠️ Fayl ichida hech qanday yaroqli RSS feed havolasi topilmadi.")
            return

        added_count = 0
        chat_title = message.chat.title or user.full_name or f"Chat {chat_id}"

        for url, title in feed_tuples[:30]:  # Cap at 30 to avoid abuse
            try:
                await rss_storage.add_subscription(
                    chat_id=chat_id,
                    feed_url=url,
                    title=title,
                    link=url,
                    chat_title=chat_title,
                    chat_type=message.chat.type,
                )
                added_count += 1
            except Exception:
                pass

        await status_msg.edit_text(
            f"✅ <b>OPML import yakunlandi!</b>\n\n"
            f"Jami qo'shilgan feedlar: <b>{added_count} ta</b>\n"
            f"Obunalarni ko'rish uchun: /rss",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error importing OPML: {e}")
        await status_msg.edit_text(f"❌ OPML import xatosi: {e}")


# --------------------------------------------------------------------------
# Callback Queries
# --------------------------------------------------------------------------
@router.callback_query(F.data.startswith("rss_unsub:"))
async def on_unsub_click(callback: CallbackQuery):
    feed_id = callback.data.split(":")[1]
    feed = await rss_storage.get_feed_by_id(feed_id)
    title = feed.title if feed else "tanlangan feed"

    keyboard = get_unsub_confirm_keyboard(feed_id)
    await callback.message.edit_text(
        f"Haqiqatan ham <b>{escape_tg_html(title)}</b> obunasini bekor qilmoqchimisiz?",
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rss_unsub_do:"))
async def on_unsub_execute(callback: CallbackQuery):
    feed_id = callback.data.split(":")[1]
    chat_id = callback.message.chat.id
    success = await rss_storage.remove_subscription(chat_id, feed_id)

    if success:
        await callback.message.edit_text("✅ Obuna muvaffaqiyatli bekor qilindi.")
    else:
        await callback.message.edit_text("⚠️ Obuna allaqachon bekor qilingan.")
    await callback.answer()


@router.callback_query(F.data == "rss_allunsub_confirm_do")
async def on_allunsub_execute(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    count = await rss_storage.remove_all_subscriptions(chat_id)
    await callback.message.edit_text(f"✅ Barcha obunalar ({count} ta) o'chirildi.")
    await callback.answer()


@router.callback_query(F.data == "rss_cancel")
async def on_rss_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Amal bekor qilindi.")
    await callback.answer()


@router.callback_query(F.data == "rss_show_list")
async def on_rss_show_list_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await callback.message.edit_text(
            "📭 <b>Sizda hali faol RSS obunalar yo'q.</b>\n\n"
            "Yangi feed qo'shish uchun: <code>/sub &lt;url&gt;</code> yuboring.",
            parse_mode="HTML",
        )
    else:
        lines = [f"📋 <b>Joriy RSS obunalar ({len(feeds)} ta):</b>\n"]
        for idx, f in enumerate(feeds, start=1):
            title_esc = escape_tg_html(f.title)
            link_esc = escape_tg_html(f.link or f.url)
            lines.append(f"{idx}. <a href=\"{link_esc}\">{title_esc}</a>")
        keyboard = get_rss_list_keyboard(feeds)
        await callback.message.edit_text("\n".join(lines), reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "rss_export_opml")
async def on_rss_export_opml_callback(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    feeds = await rss_storage.get_subscriptions_for_chat(chat_id)
    if not feeds:
        await callback.answer("Obunalar yo'q!", show_alert=True)
        return

    opml_xml = await rss_storage.export_opml(chat_id)
    doc = BufferedInputFile(
        file=opml_xml.encode("utf-8"),
        filename=f"anjurx_rss_chat_{abs(chat_id)}.opml",
    )
    await callback.message.answer_document(
        document=doc,
        caption=f"📦 <b>AnjurX | Rss Bot</b>\nSizning obunalaringiz ({len(feeds)} ta feed) OPML formatida.",
        parse_mode="HTML",
    )
    await callback.answer()
