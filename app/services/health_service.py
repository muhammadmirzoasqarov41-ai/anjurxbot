"""Non-sensitive Telegram and Firebase health checks."""

from __future__ import annotations

import datetime
from typing import Any

from aiogram import Bot

from app.services.firebase import firebase_service


class HealthService:
    async def check(self, bot: Bot) -> dict[str, Any]:
        result: dict[str, Any] = {"telegram": False, "firebase": False, "bot_status": "unknown"}
        try:
            me = await bot.get_me()
            result["telegram"] = True
            result["bot_status"] = "connected" if me else "unknown"
        except Exception:
            pass
        try:
            ref = firebase_service.db.collection("health_checks").document("service")
            await ref.set({"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
            await ref.get()
            result["firebase"] = True
        except Exception:
            pass
        return result


health_service = HealthService()