"""Admin panel — navigation helpers and text builders."""
from __future__ import annotations
from typing import Any
from app.services import group_service, guard_service, stats_service
from app.services.firebase import firebase_service
from app.config import settings


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def build_main_text(user_first_name: str) -> str:
    return (
        "🛡 <b>QOROVUL BOT</b>\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"Assalomu alaykum, <b>{_esc(user_first_name)}</b>!\n\n"
        "Bot orqali guruhlaringizni himoyalashingiz va\n"
        "majburiy obunani boshqarishingiz mumkin.\n\n"
        "👇 Kerakli bo'limni tanlang:"
    )


async def build_groups_text(groups: list[dict]) -> str:
    if not groups:
        return (
            "👥 <b>SIZNING GURUHLARINGIZ</b>\n\n"
            "Hozircha hech qanday guruh topilmadi.\n\n"
            "Botni guruhga administrator qilib qo'shing.\n"
            "Guruhda /start buyrug'ini yuboring — guruh ro'yxatga qo'shiladi."
        )
    lines = ["👥 <b>SIZNING GURUHLARINGIZ</b>\n"]
    nums = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, g in enumerate(groups[:10]):
        n = nums[i] if i < len(nums) else f"{i+1}."
        title = _esc(g.get("title") or str(g.get("chat_id", "")))
        if g.get("bot_status") in {"removed", "kicked"}:
            status = "⚫ Bot olib tashlangan"
        elif g.get("permissions_valid") is False:
            status = "🔴 Permission xatosi"
        elif g.get("is_active"):
            status = "🟢 Faol"
        else:
            status = "🟡 Sozlash kerak"
        lines.append(f"{n} {title} — {status}")
    return "\n".join(lines)


async def build_group_detail_text(group_id: int) -> str:
    data = await group_service.get_group(group_id)
    title = _esc(data.get("title", str(group_id)) if data else str(group_id))
    fsub = (data or {}).get("force_subscribe", {})
    guard_data = (data or {}).get("guard", {})
    fsub_status = "✅" if fsub.get("enabled") else "❌"
    guard_status = "✅" if guard_data.get("enabled") else "❌"
    if data and data.get("bot_status") in {"removed", "kicked"}:
        bot_status = "⚫ Bot olib tashlangan"
    elif data and data.get("permissions_valid") is False:
        bot_status = "🔴 Permission xatosi"
    elif data and data.get("is_active") and data.get("permissions_valid"):
        bot_status = "🟢 Bot ishlayapti"
    else:
        bot_status = "🟡 Sozlash kerak"
    return (
        f"🛡 <b>{title}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        "Guruh boshqaruvi\n\n"
        f"📢 Majburiy obuna: {fsub_status}\n"
        f"🛡 Qorovul: {guard_status}\n\n"
        f"{bot_status}\n\n"
        "👇 Quyidagi bo'limlardan birini tanlang:"
    )


async def build_guard_text(group_id: int) -> str:
    guard = await guard_service.get_guard_settings(group_id)
    master = "✅ YOQILGAN" if guard.get("enabled") else "❌ O'CHIRILGAN"
    features = {
        "anti_spam": "🛡 Anti-Spam",
        "anti_flood": "🌊 Anti-Flood",
        "anti_link": "🔗 Anti-Link",
        "anti_ads": "📢 Anti-Reklama",
        "anti_repeat": "🔁 Takroriy xabar",
        "bad_words": "🚫 So'z filtri",
        "new_member_protection": "👤 Yangi a'zolar",
    }
    lines = [f"🛡 <b>QOROVUL</b>\n\nUmumiy holat: {master}\n"]
    for key, label in features.items():
        mark = "🟢" if guard.get(key, False) else "🔴"
        lines.append(f"{label}: {mark}")
    return "\n".join(lines)


async def build_fsub_text(group_id: int) -> str:
    fsub = await group_service.get_fsub_settings(group_id)
    enabled = fsub.get("enabled", False)
    channels = fsub.get("channels", [])
    status = "✅ Yoqilgan" if enabled else "❌ O'chirilgan"
    lines = [
        "📢 <b>MAJBURIY OBUNA</b>\n",
        f"Holat: {status}\n",
        "Kanallar:" if channels else "Kanallar: (bo'sh)",
    ]
    for ch in channels:
        name = ch.get("username") or ch.get("title") or str(ch.get("channel_id",""))
        lines.append(f"  📢 {_esc(name)}")
    lines.append("\n👇 Boshqarish:")
    return "\n".join(lines)


async def build_stats_text(group_id: int) -> str:
    data = await group_service.get_group(group_id)
    title = _esc(data.get("title", str(group_id)) if data else str(group_id))
    st = await stats_service.get_stats(group_id)
    tracked_fields = tuple(stats_service.DEFAULT_STATS)
    if not any(st.get(field, 0) for field in tracked_fields):
        return f"📊 <b>GURUH STATISTIKASI</b>\n\n👥 Guruh: {title}\n\n📊 Hozircha statistika mavjud emas."
    number = lambda value: f"{int(value or 0):,}".replace(",", " ")
    return (
        f"📊 <b>GURUH STATISTIKASI</b>\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"👥 Guruh: {title}\n\n"
        f"📨 Jami tekshirilgan xabarlar: {number(st.get('messages_checked', 0))}\n\n"
        f"🗑 O'chirilgan xabarlar: {number(st.get('deleted_messages', 0))}\n"
        f"🔇 Mute: {number(st.get('muted_users', 0))}\n"
        f"🚫 Ban: {number(st.get('banned_users', 0))}\n"
        f"⚠️ Warning: {number(st.get('warnings', 0))}\n\n"
        f"📢 Obuna tekshiruvlari: {number(st.get('force_subscribe_checks', 0))}\n\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🛡 <b>QOROVUL:</b>\n\n"
        f"Spam: {number(st.get('spam', 0))}\n"
        f"Flood: {number(st.get('flood', 0))}\n"
        f"Link: {number(st.get('link', 0))}\n"
        f"Reklama: {number(st.get('advertisement', 0))}\n"
        f"Takroriy xabar: {number(st.get('repeat', 0))}\n"
        f"Taqiqlangan so'z: {number(st.get('bad_word', 0))}"
    )

async def build_daily_stats_text(group_id: int) -> str:
    st = await stats_service.get_daily_stats(group_id)
    return (
        f"📅 <b>BUGUN</b>\n\n"
        f"📨 Tekshirilgan: {st.get('messages_checked', 0)}\n"
        f"🗑 O'chirilgan: {st.get('deleted_messages', 0)}\n"
        f"🔇 Mute: {st.get('muted_users', 0)}\n"
        f"⚠️ Warning: {st.get('warnings', 0)}\n\n"
        f"🛡 Spam: {st.get('spam', 0)}\n"
        f"🌊 Flood: {st.get('flood', 0)}\n"
        f"🔗 Link: {st.get('link', 0)}\n"
        f"📢 Reklama: {st.get('advertisement', 0)}\n"
        f"🔁 Repeat: {st.get('repeat', 0)}\n"
        f"🚫 Bad Word: {st.get('bad_word', 0)}"
    )

def _format_datetime(iso_str: str) -> str:
    try:
        import datetime
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_str

async def build_admin_logs_text(logs: list[dict], page: int) -> str:
    if not logs:
        return f"📋 <b>ADMIN LOGLARI</b> (Sahifa: {page + 1})\n\nHozircha loglar yo'q."
    lines = [f"📋 <b>ADMIN LOGLARI</b> (Sahifa: {page + 1})\n"]
    for log in logs:
        admin_id = log.get("admin_id", "Noma'lum")
        action = _esc(log.get("action", ""))
        dt = _format_datetime(log.get("created_at", ""))
        lines.append(f"👮 Admin: {admin_id}\n⚙️ Amal: {action}\n📅 {dt}\n")
    return "\n".join(lines)

async def build_guard_logs_text(logs: list[dict], page: int) -> str:
    if not logs:
        return f"📋 <b>QOROVUL LOGLARI</b> (Sahifa: {page + 1})\n\nHozircha loglar yo'q."
    lines = [f"📋 <b>QOROVUL LOGLARI</b> (Sahifa: {page + 1})\n"]
    for log in logs:
        user_id = log.get("user_id", "Noma'lum")
        typ = _esc(log.get("type", "").upper())
        dt = _format_datetime(log.get("created_at", ""))
        lines.append(f"👤 Foydalanuvchi: {user_id}\n🛡 Hodisa: {typ}\n📅 {dt}\n")
    return "\n".join(lines)


async def build_flood_text(group_id: int) -> str:
    guard = await guard_service.get_guard_settings(group_id)
    fl = guard.get("flood_limit", 5)
    fw = guard.get("flood_window", 5)
    mu = guard.get("mute_duration", 300)
    return (
        "🌊 <b>ANTI-FLOOD SOZLAMALARI</b>\n\n"
        f"Hozirgi limit:\n"
        f"<b>{fl} ta xabar / {fw} soniya</b>\n\n"
        f"Mute muddati:\n"
        f"<b>{mu // 60} daqiqa {mu % 60} soniya</b>\n\n"
        "👇 O'zgartirish uchun tugmani bosing:"
    )


async def build_config_text(group_id: int) -> str:
    data = await group_service.get_group(group_id)
    title = _esc(data.get("title", str(group_id)) if data else str(group_id))
    guard = await guard_service.get_guard_settings(group_id)
    guard_on = "✅" if guard.get("enabled") else "❌"
    fsub = await group_service.get_fsub_settings(group_id)
    fsub_on = "✅" if fsub.get("enabled") else "❌"
    return (
        f"⚙️ <b>GURUH SOZLAMALARI</b>\n\n"
        f"👥 Guruh: {title}\n\n"
        f"🛡 Qorovul: {guard_on}\n"
        f"📢 Majburiy obuna: {fsub_on}\n\n"
        "Til: 🇺🇿 O'zbekcha"
    )


async def build_badwords_text(group_id: int) -> str:
    guard = await guard_service.get_guard_settings(group_id)
    words = await guard_service.get_bad_words(group_id)
    enabled = guard.get("bad_words", False)
    status = "✅ YOQILGAN" if enabled else "❌ O'CHIRILGAN"
    return (
        f"🚫 <b>SO'Z FILTRI</b>\n\n"
        f"Holat: {status}\n"
        f"Taqiqlangan so'zlar: {len(words)} ta"
    )


async def build_help_text() -> str:
    return (
        "ℹ️ <b>BOTDAN FOYDALANISH</b>\n\n"
        "1. Botni guruhga administrator qiling.\n"
        "2. Guruhda /setup yuboring.\n"
        "3. Permissionlarni tekshiring.\n"
        "4. Majburiy obunani sozlang.\n"
        "5. Qorovulni yoqing.\n\n"
        "<b>Asosiy komandalar:</b>\n"
        "/start — boshlash\n"
        "/setup — guruhni tekshirish\n"
        "/panel — admin panel\n"
        "/guard — qorovul\n"
        "/fsub — majburiy obuna\n"
        "/stats — statistika"
    )


def is_global_admin(user_id: int) -> bool:
    return settings.is_admin(user_id)
