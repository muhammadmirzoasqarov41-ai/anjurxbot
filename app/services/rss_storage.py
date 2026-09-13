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


def get_db_path() -> str:
    """Returns absolute path to database JSON file from env or config."""
    path_val = os.getenv("DATABASE_PATH") or getattr(config, "database_path", None) or "./data/rssbot.json"
    path_val = str(path_val).strip()
    if not os.path.isabs(path_val):
        return os.path.abspath(os.path.join(os.getcwd(), path_val))
    return os.path.abspath(path_val)


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
    def from_dict(cls, d: Any) -> "RSSFeed":
        if not isinstance(d, dict):
            url_str = str(d or "").strip()
            fid = make_feed_id(url_str) if url_str else "unknown_feed"
            return cls(
                id=fid,
                url=url_str,
                title=url_str or "RSS Feed",
                link=url_str,
            )

        url = str(d.get("url") or d.get("link") or "").strip()
        feed_id = str(d.get("id") or make_feed_id(url) if url else f"feed_{int(time.time())}")

        raw_subs = d.get("subscribers", [])
        subs: List[int] = []
        if isinstance(raw_subs, list):
            for s in raw_subs:
                try:
                    subs.append(int(s))
                except (ValueError, TypeError):
                    pass
        elif isinstance(raw_subs, (int, str)) and str(raw_subs).isdigit():
            subs.append(int(raw_subs))

        raw_hashes = d.get("seen_hashes", [])
        hashes = [str(h) for h in raw_hashes if isinstance(h, (str, int))] if isinstance(raw_hashes, list) else []

        err_cnt = 0
        try:
            err_cnt = int(d.get("error_count", 0))
        except (ValueError, TypeError):
            err_cnt = 0

        intvl = 300
        try:
            intvl = int(d.get("interval", 300))
        except (ValueError, TypeError):
            intvl = 300

        return cls(
            id=feed_id,
            url=url,
            title=str(d.get("title") or "Nomsiz RSS"),
            link=str(d.get("link") or url),
            description=str(d.get("description") or ""),
            subscribers=subs,
            seen_hashes=hashes,
            error_count=err_cnt,
            last_error=d.get("last_error"),
            last_checked=d.get("last_checked") or d.get("last_check"),
            last_updated=d.get("last_updated"),
            etag=d.get("etag"),
            last_modified=d.get("last_modified"),
            interval=intvl,
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
        )


class RSSStorage:
    """Manages all RSS subscriptions and feeds in memory and persistence layers."""

    def __init__(self):
        self._feeds: Dict[str, RSSFeed] = {}
        self._subscribers: Dict[int, Dict[str, Any]] = {}
        self._posts_delivered: int = 0
        self._recent_posts: List[Dict[str, Any]] = []
        self._loaded: bool = False

    @property
    def db_path(self) -> str:
        return get_db_path()

    @property
    def data_dir(self) -> str:
        return os.path.dirname(self.db_path)

    async def init(self):
        """Initializes database, connecting Firebase and loading persistence."""
        if self._loaded:
            return
        os.makedirs(self.data_dir, exist_ok=True)
        # 1. Attempt Firebase initialization
        try:
            await firebase_service.initialize()
        except Exception as e:
            logger.info(f"Firebase initialization skipped or unavailable: {e}. Running in local storage mode.")

        # 2. Load and normalize data
        await self._load_data()
        self._loaded = True

    def _normalize_and_load(self, data: Any):
        """
        Safely parses and normalizes local data from any structure:
        - Canonical dictionary format: {"feeds": {id: {...}}, "subscribers": {cid: {...}}}
        - List format: {"feeds": [{...}], "subscribers": [{...}]}
        - Legacy Qorovul/AnjurX format: {"subscribers": {chat_id: [feed_urls]}}
        - Raw feed list: [{...}]
        Guarantees zero 'str' object has no attribute 'get' errors.
        """
        if not data:
            return

        # Case: root is a list of feeds
        if isinstance(data, list):
            for item in data:
                feed = RSSFeed.from_dict(item)
                if feed.id and feed.url:
                    self._feeds[feed.id] = feed
            return

        if not isinstance(data, dict):
            logger.warning(f"Unexpected data type in DB: {type(data).__name__}. Skipping.")
            return

        # 1. Feeds normalizer
        raw_feeds = data.get("feeds", {})
        if isinstance(raw_feeds, dict):
            for k, v in raw_feeds.items():
                if isinstance(v, dict):
                    if not v.get("id"):
                        v["id"] = k
                    if not v.get("url") and (k.startswith("http://") or k.startswith("https://")):
                        v["url"] = k
                    feed = RSSFeed.from_dict(v)
                    self._feeds[feed.id] = feed
                elif isinstance(v, list):
                    # Legacy: key is feed URL/ID, value is list of subscriber chat_ids
                    url = k if (k.startswith("http://") or k.startswith("https://")) else ""
                    fid = make_feed_id(url) if url else k
                    subs = []
                    for sid in v:
                        try:
                            subs.append(int(sid))
                        except (ValueError, TypeError):
                            pass
                    self._feeds[fid] = RSSFeed(
                        id=fid,
                        url=url or fid,
                        title=k,
                        link=url or k,
                        subscribers=subs,
                    )
                elif isinstance(v, str):
                    url = v if (v.startswith("http://") or v.startswith("https://")) else k
                    fid = make_feed_id(url) if (url.startswith("http://") or url.startswith("https://")) else k
                    self._feeds[fid] = RSSFeed.from_dict({"id": fid, "url": url, "title": k, "link": url})
        elif isinstance(raw_feeds, list):
            for item in raw_feeds:
                feed = RSSFeed.from_dict(item)
                if feed.id:
                    self._feeds[feed.id] = feed

        # 2. Subscribers normalizer
        raw_subs = data.get("subscribers", {})
        if isinstance(raw_subs, dict):
            for k, v in raw_subs.items():
                cid = 0
                try:
                    cid = int(k)
                except (ValueError, TypeError):
                    pass

                if isinstance(v, dict):
                    sub_cid = 0
                    try:
                        sub_cid = int(v.get("chat_id") or cid or 0)
                    except (ValueError, TypeError):
                        sub_cid = cid
                    if sub_cid:
                        raw_f = v.get("feeds") or v.get("feed_ids") or []
                        feeds_list = [str(x) for x in raw_f if str(x).strip()] if isinstance(raw_f, list) else []
                        self._subscribers[sub_cid] = {
                            "chat_id": sub_cid,
                            "title": str(v.get("title") or f"Chat {sub_cid}"),
                            "type": str(v.get("type") or "private"),
                            "feeds": feeds_list,
                            "joined_at": str(v.get("joined_at") or datetime.utcnow().isoformat()),
                        }
                elif isinstance(v, list):
                    # Legacy: { "chat_id": ["feed_id_1", "feed_id_2"] }
                    if cid:
                        self._subscribers[cid] = {
                            "chat_id": cid,
                            "title": f"Chat {cid}",
                            "type": "private",
                            "feeds": [str(x) for x in v if str(x).strip()],
                            "joined_at": datetime.utcnow().isoformat(),
                        }
                elif isinstance(v, (int, str)):
                    target_cid = 0
                    try:
                        target_cid = int(v)
                    except (ValueError, TypeError):
                        target_cid = cid
                    if target_cid:
                        self._subscribers.setdefault(target_cid, {
                            "chat_id": target_cid,
                            "title": f"Chat {target_cid}",
                            "type": "private",
                            "feeds": [],
                            "joined_at": datetime.utcnow().isoformat(),
                        })
        elif isinstance(raw_subs, list):
            for item in raw_subs:
                if isinstance(item, dict):
                    try:
                        cid = int(item.get("chat_id", 0))
                        if cid:
                            raw_f = item.get("feeds") or item.get("feed_ids") or []
                            feeds_list = [str(x) for x in raw_f if str(x).strip()] if isinstance(raw_f, list) else []
                            self._subscribers[cid] = {
                                "chat_id": cid,
                                "title": str(item.get("title") or f"Chat {cid}"),
                                "type": str(item.get("type") or "private"),
                                "feeds": feeds_list,
                                "joined_at": str(item.get("joined_at") or datetime.utcnow().isoformat()),
                            }
                    except (ValueError, TypeError):
                        pass
                elif isinstance(item, (int, str)):
                    try:
                        cid = int(item)
                        if cid:
                            self._subscribers.setdefault(cid, {
                                "chat_id": cid,
                                "title": f"Chat {cid}",
                                "type": "private",
                                "feeds": [],
                                "joined_at": datetime.utcnow().isoformat(),
                            })
                    except (ValueError, TypeError):
                        pass

        # 3. Stats & delivered posts
        try:
            self._posts_delivered = int(data.get("posts_delivered", 0))
        except (ValueError, TypeError):
            self._posts_delivered = 0

        raw_recent = data.get("recent_posts", [])
        if isinstance(raw_recent, list):
            self._recent_posts = [p for p in raw_recent if isinstance(p, dict)]

        # 4. Bidirectional consistency synchronization
        for feed in self._feeds.values():
            for sid in feed.subscribers:
                if sid in self._subscribers:
                    if feed.id not in self._subscribers[sid]["feeds"]:
                        self._subscribers[sid]["feeds"].append(feed.id)
                else:
                    self._subscribers[sid] = {
                        "chat_id": sid,
                        "title": f"Chat {sid}",
                        "type": "private",
                        "feeds": [feed.id],
                        "joined_at": datetime.utcnow().isoformat(),
                    }

        for sid, sub in self._subscribers.items():
            for fid in sub.get("feeds", []):
                if fid in self._feeds and sid not in self._feeds[fid].subscribers:
                    self._feeds[fid].subscribers.append(sid)

    async def _load_data(self):
        # 1. Try local JSON first
        db_path = self.db_path
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self._normalize_and_load(data)
                        logger.info(
                            f"Loaded {len(self._feeds)} feeds and {len(self._subscribers)} "
                            f"subscribers from local DB ({db_path})."
                        )
                    else:
                        logger.info(f"Local DB {db_path} is empty, starting with clean state.")
            except json.JSONDecodeError as je:
                backup_path = f"{db_path}.corrupt.{int(time.time())}.bak"
                logger.error(f"Malformed JSON in local DB {db_path}: {je}. Backing up to {backup_path}")
                try:
                    import shutil
                    shutil.copy2(db_path, backup_path)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Error loading local DB {db_path}: {e}")

        # 2. Try sync from Firestore if actively connected
        if firebase_service.is_initialized():
            try:
                fs_feeds = await firebase_service.get_rss_feeds(limit=1000)
                fs_count = 0
                for fd in fs_feeds:
                    if isinstance(fd, dict):
                        feed = RSSFeed.from_dict(fd)
                        self._feeds[feed.id] = feed
                        fs_count += 1
                if fs_count > 0:
                    logger.info(f"Synced {fs_count} feeds from Firestore.")
            except Exception as e:
                logger.warning(f"Could not load feeds from Firestore: {e}")

    async def _save_local(self):
        """Writes current state to local JSON file safely and atomically."""
        db_path = self.db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        payload = {
            "feeds": {f.id: f.to_dict() for f in self._feeds.values()},
            "subscribers": {str(cid): sub for cid, sub in self._subscribers.items()},
            "posts_delivered": self._posts_delivered,
            "recent_posts": self._recent_posts[-100:],
            "updated_at": datetime.utcnow().isoformat(),
        }
        tmp_path = f"{db_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, db_path)
        except Exception as e:
            logger.error(f"Failed to write local DB: {e}")

    async def _save_feed_firestore(self, feed: RSSFeed):
        if not firebase_service.is_initialized():
            return
        try:
            await firebase_service.save_rss_feed(feed.to_dict())
        except Exception as e:
            logger.warning(f"Failed to sync feed {feed.id} to Firestore: {e}")

    async def _delete_feed_firestore(self, feed_id: str):
        if not firebase_service.is_initialized():
            return
        try:
            await firebase_service.delete_rss_feed(feed_id)
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
                "feeds": [feed_id],
                "joined_at": datetime.utcnow().isoformat(),
            }
        else:
            sub = self._subscribers[chat_id]
            f_list = sub.setdefault("feeds", sub.pop("feed_ids", []))
            if feed_id not in f_list:
                f_list.append(feed_id)
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

        if chat_id in feed.subscribers:
            feed.subscribers.remove(chat_id)

        # Update subscriber entity
        if chat_id in self._subscribers:
            sub = self._subscribers[chat_id]
            f_list = sub.get("feeds") or sub.get("feed_ids") or []
            if target_id in f_list:
                f_list.remove(target_id)
            sub["feeds"] = f_list
            if not f_list:
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
