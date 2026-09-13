"""
AnjurX | Rss Bot - High-Performance Telegram RSS/Atom/JSON Feed Reader Bot
Entrypoint forwarding to app.web_service
"""
import sys
from app.web_service import main

if __name__ == "__main__":
    main()
