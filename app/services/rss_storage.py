"""
RSS Data Storage and Persistence for AnjurX | Rss Bot.
Provides dual persistence: local JSON database file (./data/rssbot.json)
and Firebase Firestore (rss_feeds, rss_subscribers, rss_posts, rss_stats collections).
"""
import os
import json
import time
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple

from app.config import config
from app.services.firebase import firebase_service
from app.services.feed_parser import build_opml

logger = logging.getLogger("anjurxbot.storage")

DATA_DIR = os.path.join(os.getcwd(), "data")
LOCAL_DB_PATH = os.path.join(DATA_DIR, "rssbot.json")


def make_feed_id(url: str) -> str:
    """Creates a deterministic 16-character hex hash from feed URL."""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


@dataclass
class RSSFeed:
    id: str
    url: str
    title: str
    link: str
    description: str = ""
    subscribers: List[int] = field(default_factory=list)
    seen_hashes: List[str] = field(default_factory=list)
    error_count: int = 0
    last_error: Optional[str] = None
    last_checked: Optional[str] = None
    last_updated: Optional[str] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    interval: int = 300  # seconds between updates (default: 5 min)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RSSFeed":
        return cls(
            id=d.get("id") or make_feed_id(d.get("url", "")),
            url=d.get("url", ""),
            title=d.get("title", "Nomsiz RSS"),
            link=d.get("link", ""),
            description=d.get("description", ""),
            subscribers=[int(s) for s in d.get("subscribers", [])],
            seen_hashes=list(d.get("seen_hashes", [])),
            error_count=int(d.get("error_count", 0)),
            last_error=d.get("last_error"),
            last_checked=d.get("last_checked"),
            last_updated=d.get("last_updated"),
            etag=d.get("etag"),
            last_modified=d.get("last_modified"),
            interval=int(d.get("interval", 300)),
            created_at=d.get("created_at") or datetime.utcnow().isoformat(),
        )


class RSSStorage:
    """Manages all RSS subscriptions and feeds in memory and persistence layers."""

    def __init__(self):
        self._feeds: Dict[str, RSSFeed] = {}
        self._subscribers: Dict[int, Dict[str, Any]] = {}
        self._posts_delivered: int = 0
        self._recent_posts: List[Dict[str, Any]] = []
        self._loaded: bool = False

    async def init(self):
        """Initializes database, loading from Firestore or local JSON."""
        if self._loaded:
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        await self._load_data()
        self._loaded = True

    async def _load_data(self):
        # 1. Try local JSON first
        if os.path.exists(LOCAL_DB_PATH):
            try:
                with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for fd in data.get("feeds", []):
                        feed = RSSFeed.from_dict(fd)
                        self._feeds[feed.id] = feed
                    for sub in data.get("subscribers", []):
                        cid = int(sub.get("chat_id", 0))
                        if cid:
                            self._subscribers[cid] = sub
                    self._posts_delivered = int(data.get("posts_delivered", 0))
                    self._recent_posts = data.get("recent_posts", [])
                logger.info(f"Loaded {len(self._feeds)} feeds and {len(self._subscribers)} subscribers from local JSON.")
            except Exception as e:
                logger.error(f"Error loading local DB {LOCAL_DB_PATH}: {e}")

        # 2. Try sync from Firestore if available
        if firebase_service.is_initialized():
            try:
                db = firebase_service.db
                feeds_ref = db.collection("rss_feeds")
                docs = feeds_ref.stream()
                fs_count = 0
                for doc in docs:
                    d = doc.to_dict()
                    feed = RSSFeed.from_dict(d)
                    self._feeds[feed.id] = feed
                    fs_count += 1
                if fs_count > 0:
                    logger.info(f"Synced {fs_count} feeds from Firestore.")
            except Exception as e:
                logger.warning(f"Could not load feeds from Firestore: {e}")

    async def _save_local(self):
        """Writes current state to local JSON file safely."""
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = {
            "feeds": [f.to_dict() for f in self._feeds.values()],
            "subscribers": list(self._subscribers.values()),
            "posts_delivered": self._posts_delivered,
            "recent_posts": self._recent_posts[-100:],
            "updated_at": datetime.utcnow().isoformat(),
        }
        tmp_path = f"{LOCAL_DB_PATH}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, LOCAL_DB_PATH)
        except Exception as e:
            logger.error(f"Failed to write local DB: {e}")

    async def _save_feed_firestore(self, feed: RSSFeed):
        if not firebase_service.is_initialized():
            return
        try:
            db = firebase_service.db
            db.collection("rss_feeds").document(feed.id).set(feed.to_dict())
        except Exception as e:
            logger.warning(f"Failed to sync feed {feed.id} to Firestore: {e}")

    async def _delete_feed_firestore(self, feed_id: str):
        if not firebase_service.is_initialized():
            return
        try:
            db = firebase_service.db
            db.collection("rss_feeds").document(feed_id).delete()
        except Exception as e:
            logger.warning(f"Failed to delete feed {feed_id} from Firestore: {e}")

    # --------------------------------------------------------------------------
    # Feed and Subscription Operations
    # --------------------------------------------------------------------------
    async def get_all_feeds(self) -> List[RSSFeed]:
        await self.init()
        return list(self._feeds.values())

    async def get_feed_by_id(self, feed_id: str) -> Optional[RSSFeed]:
        await self.init()
        return self._feeds.get(feed_id)

    async def get_feed_by_url(self, url: str) -> Optional[RSSFeed]:
        await self.init()
        target_id = make_feed_id(url)
        if target_id in self._feeds:
            return self._feeds[target_id]
        # Check normalized match
        clean_url = url.strip().rstrip("/")
        for f in self._feeds.values():
            if f.url.strip().rstrip("/") == clean_url:
                return f
        return None

    async def add_subscription(
        self,
        chat_id: int,
        feed_url: str,
        title: str,
        link: str,
        description: str = "",
        initial_seen_hashes: Optional[List[str]] = None,
        chat_title: str = "",
        chat_type: str = "private",
    ) -> Tuple[RSSFeed, bool]:
        """
        Adds a subscription for chat_id.
        Returns (RSSFeed, is_newly_created_feed).
        """
        await self.init()
        feed_id = make_feed_id(feed_url)
        is_new = False

        if feed_id in self._feeds:
            feed = self._feeds[feed_id]
            if chat_id not in feed.subscribers:
                feed.subscribers.append(chat_id)
            if title and feed.title in ("Nomsiz RSS", "Nomsiz Atom"):
                feed.title = title
        else:
            is_new = True
            feed = RSSFeed(
                id=feed_id,
                url=feed_url,
                title=title or "RSS Feed",
                link=link or feed_url,
                description=description or "",
                subscribers=[chat_id],
                seen_hashes=list(initial_seen_hashes or []),
                created_at=datetime.utcnow().isoformat(),
            )
            self._feeds[feed_id] = feed

        # Track subscriber
        if chat_id not in self._subscribers:
            self._subscribers[chat_id] = {
                "chat_id": chat_id,
                "title": chat_title or f"Chat {chat_id}",
                "type": chat_type,
                "feed_ids": [feed_id],
                "created_at": datetime.utcnow().isoformat(),
            }
        else:
            sub = self._subscribers[chat_id]
            if feed_id not in sub.get("feed_ids", []):
                sub.setdefault("feed_ids", []).append(feed_id)
            if chat_title:
                sub["title"] = chat_title

        await self._save_local()
        await self._save_feed_firestore(feed)
        return feed, is_new

    async def remove_subscription(self, chat_id: int, feed_url_or_id: str) -> bool:
        """
        Removes subscription for chat_id from given feed URL or feed ID.
        """
        await self.init()
        target_id = feed_url_or_id if feed_url_or_id in self._feeds else make_feed_id(feed_url_or_id)
        feed = self._feeds.get(target_id)
        if not feed:
            # Check by raw URL
            clean = feed_url_or_id.strip().rstrip("/")
            for f in self._feeds.values():
                if f.url.strip().rstrip("/") == clean:
                    feed = f
                    target_id = f.id
                    break

        if not feed or chat_id not in feed.subscribers:
            return False

        feed.subscribers.remove(chat_id)

        # Update subscriber entity
        if chat_id in self._subscribers:
            sub = self._subscribers[chat_id]
            if target_id in sub.get("feed_ids", []):
                sub["feed_ids"].remove(target_id)
            if not sub["feed_ids"]:
                del self._subscribers[chat_id]

        # If feed has 0 subscribers, we can either keep or remove
        await self._save_local()
        await self._save_feed_firestore(feed)
        return True

    async def remove_all_subscriptions(self, chat_id: int) -> int:
        """Removes all subscriptions for the given chat_id."""
        await self.init()
        count = 0
        for feed in self._feeds.values():
            if chat_id in feed.subscribers:
                feed.subscribers.remove(chat_id)
                count += 1
                await self._save_feed_firestore(feed)

        if chat_id in self._subscribers:
            del self._subscribers[chat_id]

        await self._save_local()
        return count

    async def get_subscriptions_for_chat(self, chat_id: int) -> List[RSSFeed]:
        """Returns all RSS feeds that this chat is subscribed to."""
        await self.init()
        return [f for f in self._feeds.values() if chat_id in f.subscribers]

    async def update_feed_state(
        self,
        feed_id: str,
        seen_hashes: Optional[List[str]] = None,
        error: Optional[str] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ):
        """Updates runtime state of a feed after a poll."""
        await self.init()
        feed = self._feeds.get(feed_id)
        if not feed:
            return

        feed.last_checked = datetime.utcnow().isoformat()
        if error:
            feed.error_count += 1
            feed.last_error = str(error)
        else:
            feed.error_count = 0
            feed.last_error = None
            feed.last_updated = datetime.utcnow().isoformat()

        if etag:
            feed.etag = etag
        if last_modified:
            feed.last_modified = last_modified

        if seen_hashes:
            # Merge seen hashes, keeping the last 500
            merged = list(dict.fromkeys(feed.seen_hashes + seen_hashes))
            if len(merged) > 500:
                merged = merged[-500:]
            feed.seen_hashes = merged

        await self._save_local()
        await self._save_feed_firestore(feed)

    async def record_delivery(self, feed_title: str, item_title: str, item_link: str, recipient_count: int):
        """Logs a delivered post event for statistics."""
        self._posts_delivered += recipient_count
        log_entry = {
            "feed_title": feed_title,
            "item_title": item_title,
            "item_link": item_link,
            "recipient_count": recipient_count,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._recent_posts.append(log_entry)
        if len(self._recent_posts) > 100:
            self._recent_posts = self._recent_posts[-100:]

        await self._save_local()

    async def get_stats(self) -> Dict[str, Any]:
        """Returns overview statistics for dashboard."""
        await self.init()
        total_feeds = len(self._feeds)
        total_subscribers = len(self._subscribers)
        total_links = sum(len(f.subscribers) for f in self._feeds.values())
        healthy_feeds = sum(1 for f in self._feeds.values() if f.error_count == 0)
        error_feeds = sum(1 for f in self._feeds.values() if f.error_count > 0)

        return {
            "total_feeds": total_feeds,
            "total_subscribers": total_subscribers,
            "active_subscriptions": total_links,
            "healthy_feeds": healthy_feeds,
            "error_feeds": error_feeds,
            "posts_delivered": self._posts_delivered,
            "recent_posts": self._recent_posts[-20:],
        }

    async def export_opml(self, chat_id: Optional[int] = None) -> str:
        """Exports subscriptions in OPML format."""
        await self.init()
        if chat_id is not None:
            feeds = await self.get_subscriptions_for_chat(chat_id)
            title = f"AnjurX | Rss Bot Chat {chat_id} Subscriptions"
        else:
            feeds = list(self._feeds.values())
            title = "AnjurX | Rss Bot All Feeds"

        raw_list = [{"url": f.url, "title": f.title, "link": f.link} for f in feeds]
        return build_opml(raw_list, title=title)


# Global singleton storage instance
rss_storage = RSSStorage()
