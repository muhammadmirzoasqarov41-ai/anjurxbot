"""
Unified Data Storage and Persistence for AnjurX | Rss Bot.
Supports:
- Dual Source Types: RSS/Atom/JSON feeds and Telegram Channels
- Destination Management: Channels, Supergroups, Groups, and Private chats
- Strict Duplicate Prevention with persistent delivery tracking
- Dual persistence: local JSON database file (./data/rssbot.json) and Firebase Firestore
"""
import os
import json
import time
import hashlib
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple, Set

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
class SourceItem:
    """Represents an aggregation source (Website RSS or Telegram Channel)."""
    id: str  # e.g. "rss_<hash>" or "tg_<channel_id>"
    type: str  # "rss" or "telegram_channel"
    url_or_id: str  # URL for RSS, channel_id for Telegram channel
    title: str
    link: str  # Website link or t.me channel URL
    owner_id: int  # Telegram user ID who added this source
    destinations: List[int] = field(default_factory=list)  # list of target chat IDs
    seen_ids: List[str] = field(default_factory=list)  # Seen item hashes (RSS) or message IDs (TG)
    error_count: int = 0
    last_error: Optional[str] = None
    last_checked: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceItem":
        raw_dests = d.get("destinations", [])
        dests: List[int] = []
        if isinstance(raw_dests, list):
            for x in raw_dests:
                try:
                    dests.append(int(x))
                except (ValueError, TypeError):
                    pass

        raw_seen = d.get("seen_ids", d.get("seen_hashes", []))
        seen = [str(x) for x in raw_seen if x is not None] if isinstance(raw_seen, list) else []

        owner = 0
        try:
            owner = int(d.get("owner_id", 0))
        except (ValueError, TypeError):
            owner = 0

        err_cnt = 0
        try:
            err_cnt = int(d.get("error_count", 0))
        except (ValueError, TypeError):
            err_cnt = 0

        return cls(
            id=str(d.get("id", "")),
            type=str(d.get("type", "rss")),
            url_or_id=str(d.get("url_or_id") or d.get("url") or ""),
            title=str(d.get("title") or "Nomsiz Manba"),
            link=str(d.get("link") or ""),
            owner_id=owner,
            destinations=dests,
            seen_ids=seen,
            error_count=err_cnt,
            last_error=d.get("last_error"),
            last_checked=d.get("last_checked"),
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
        )


@dataclass
class DestinationItem:
    """Represents a connected delivery destination (Channel, Group, Private chat)."""
    chat_id: int
    title: str
    username: Optional[str] = None
    type: str = "channel"  # "channel", "supergroup", "group", "private"
    can_post: bool = True
    added_by: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DestinationItem":
        cid = 0
        try:
            cid = int(d.get("chat_id", 0))
        except (ValueError, TypeError):
            cid = 0

        added = 0
        try:
            added = int(d.get("added_by", 0))
        except (ValueError, TypeError):
            added = 0

        return cls(
            chat_id=cid,
            title=str(d.get("title") or f"Chat {cid}"),
            username=d.get("username"),
            type=str(d.get("type") or "channel"),
            can_post=bool(d.get("can_post", True)),
            added_by=added,
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
        )


@dataclass
class RSSFeed:
    """Backward compatibility model for existing feed polling engine."""
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
    interval: int = 300
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Any) -> "RSSFeed":
        if not isinstance(d, dict):
            url_str = str(d or "").strip()
            fid = make_feed_id(url_str) if url_str else "unknown_feed"
            return cls(id=fid, url=url_str, title=url_str or "RSS Feed", link=url_str)

        url = str(d.get("url") or d.get("link") or "").strip()
        feed_id = str(d.get("id") or make_feed_id(url) if url else f"feed_{int(time.time())}")

        raw_subs = d.get("subscribers", d.get("destinations", []))
        subs: List[int] = []
        if isinstance(raw_subs, list):
            for s in raw_subs:
                try:
                    subs.append(int(s))
                except (ValueError, TypeError):
                    pass
        elif isinstance(raw_subs, (int, str)) and str(raw_subs).isdigit():
            subs.append(int(raw_subs))

        raw_hashes = d.get("seen_hashes", d.get("seen_ids", []))
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
    """Manages all sources, destinations, and delivered posts in memory and persistence layers."""

    def __init__(self):
        self._sources: Dict[str, SourceItem] = {}
        self._destinations: Dict[int, DestinationItem] = {}
        self._feeds: Dict[str, RSSFeed] = {}
        self._subscribers: Dict[int, Dict[str, Any]] = {}
        self._delivered_signatures: Set[str] = set()
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
        """Safely parses and normalizes data from existing and new schemas."""
        if not data or not isinstance(data, dict):
            return

        # 1. Sources (new schema)
        raw_sources = data.get("sources", {})
        if isinstance(raw_sources, dict):
            for k, v in raw_sources.items():
                if isinstance(v, dict):
                    if not v.get("id"):
                        v["id"] = k
                    source = SourceItem.from_dict(v)
                    self._sources[source.id] = source

        # 2. Feeds (legacy schema mapping)
        raw_feeds = data.get("feeds", {})
        if isinstance(raw_feeds, dict):
            for k, v in raw_feeds.items():
                if isinstance(v, dict):
                    feed = RSSFeed.from_dict(v)
                    self._feeds[feed.id] = feed
                    # Map to source if not already present
                    if feed.id not in self._sources:
                        self._sources[feed.id] = SourceItem(
                            id=feed.id,
                            type="rss",
                            url_or_id=feed.url,
                            title=feed.title,
                            link=feed.link,
                            owner_id=feed.subscribers[0] if feed.subscribers else 0,
                            destinations=list(feed.subscribers),
                            seen_ids=list(feed.seen_hashes),
                            error_count=feed.error_count,
                            last_error=feed.last_error,
                            last_checked=feed.last_checked,
                            created_at=feed.created_at,
                        )

        # 3. Destinations (new schema)
        raw_destinations = data.get("destinations", {})
        if isinstance(raw_destinations, dict):
            for k, v in raw_destinations.items():
                if isinstance(v, dict):
                    dest = DestinationItem.from_dict(v)
                    if dest.chat_id != 0:
                        self._destinations[dest.chat_id] = dest

        # 4. Subscribers (legacy schema mapping)
        raw_subs = data.get("subscribers", {})
        if isinstance(raw_subs, dict):
            for k, v in raw_subs.items():
                cid = 0
                try:
                    cid = int(k)
                except (ValueError, TypeError):
                    continue

                if isinstance(v, dict):
                    self._subscribers[cid] = v
                    if cid not in self._destinations:
                        self._destinations[cid] = DestinationItem(
                            chat_id=cid,
                            title=str(v.get("title") or f"Chat {cid}"),
                            type=str(v.get("type") or "private"),
                            can_post=True,
                            added_by=cid if cid > 0 else 0,
                            created_at=str(v.get("joined_at") or datetime.utcnow().isoformat()),
                        )

        # 5. Delivered Keys (for duplicate protection across restarts)
        raw_keys = data.get("delivered_keys", [])
        if isinstance(raw_keys, list):
            for k in raw_keys:
                if isinstance(k, str) and k:
                    self._delivered_signatures.add(k)

        # 6. Delivered posts count and recent list
        self._posts_delivered = int(data.get("posts_delivered", 0))
        raw_recent = data.get("recent_posts", [])
        if isinstance(raw_recent, list):
            self._recent_posts = [p for p in raw_recent if isinstance(p, dict)]
            for p in self._recent_posts:
                # also populate delivery signatures
                sid = p.get("source_id")
                mid = p.get("message_id")
                did = p.get("destination_id")
                if sid and mid and did:
                    self._delivered_signatures.add(f"{sid}:{mid}:{did}")

        # 7. Bidirectional consistency synchronization
        for source in self._sources.values():
            if source.type == "rss":
                self._feeds[source.id] = RSSFeed(
                    id=source.id,
                    url=source.url_or_id,
                    title=source.title,
                    link=source.link,
                    subscribers=list(source.destinations),
                    seen_hashes=list(source.seen_ids),
                    error_count=source.error_count,
                    last_error=source.last_error,
                    last_checked=source.last_checked,
                    created_at=source.created_at,
                )

        for feed in self._feeds.values():
            for sid in feed.subscribers:
                if sid not in self._destinations:
                    self._destinations[sid] = DestinationItem(
                        chat_id=sid,
                        title=f"Chat {sid}",
                        type="channel" if sid < -1000000000000 else "private",
                        can_post=True,
                    )

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
                            f"Loaded {len(self._sources)} sources, {len(self._destinations)} "
                            f"destinations from local DB ({db_path})."
                        )
                    else:
                        logger.info(f"Local DB {db_path} is empty, starting with clean state.")
            except Exception as e:
                logger.error(f"Error loading local DB {db_path}: {e}")

        # 2. Try sync from Firestore if actively connected
        if firebase_service.is_initialized():
            try:
                fs_sources = await firebase_service.get_all_sources(limit=1000)
                for s in fs_sources:
                    if isinstance(s, dict):
                        item = SourceItem.from_dict(s)
                        if item.id:
                            self._sources[item.id] = item
                fs_dests = await firebase_service.get_all_destinations(limit=1000)
                for d in fs_dests:
                    if isinstance(d, dict):
                        dest = DestinationItem.from_dict(d)
                        if dest.chat_id != 0:
                            self._destinations[dest.chat_id] = dest
            except Exception as e:
                logger.warning(f"Could not load aggregator data from Firestore: {e}")

    async def _save_local(self):
        """Writes current state to local JSON file safely and atomically."""
        db_path = self.db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # Keep delivered_keys bounded to last 5000 to prevent unbounded file growth
        delivered_keys_list = list(self._delivered_signatures)[-5000:]
        payload = {
            "sources": {s.id: s.to_dict() for s in self._sources.values()},
            "destinations": {str(cid): d.to_dict() for cid, d in self._destinations.items()},
            "feeds": {f.id: f.to_dict() for f in self._feeds.values()},
            "subscribers": {
                str(cid): {
                    "chat_id": cid,
                    "title": d.title,
                    "type": d.type,
                    "feeds": [s.id for s in self._sources.values() if cid in s.destinations],
                    "joined_at": d.created_at,
                }
                for cid, d in self._destinations.items()
            },
            "delivered_keys": delivered_keys_list,
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

    # --------------------------------------------------------------------------
    # Duplicate Protection
    # --------------------------------------------------------------------------
    async def is_post_delivered(self, source_id: str, message_id: int, destination_id: int) -> bool:
        """Checks if a Telegram post has already been delivered to the destination channel."""
        key = f"{source_id}:{message_id}:{destination_id}"
        return key in self._delivered_signatures

    async def record_channel_delivery(
        self,
        source_id: str,
        source_title: str,
        message_id: int,
        destination_id: int,
        destination_title: str = "",
        title: str = "",
        link: str = "",
    ) -> bool:
        """Records delivery signature for duplicate protection and logs delivered item."""
        key = f"{source_id}:{message_id}:{destination_id}"
        if key in self._delivered_signatures:
            return False

        self._delivered_signatures.add(key)
        self._posts_delivered += 1

        post_item = {
            "id": f"tg_{source_id}_{message_id}_{destination_id}",
            "source_id": source_id,
            "source_title": source_title or f"Channel {source_id}",
            "source_type": "telegram_channel",
            "message_id": message_id,
            "title": title or f"Post #{message_id}",
            "link": link or "",
            "destination_id": destination_id,
            "destination_title": destination_title or f"Channel {destination_id}",
            "delivered_at": datetime.utcnow().isoformat(),
        }
        self._recent_posts.append(post_item)
        if len(self._recent_posts) > 100:
            self._recent_posts = self._recent_posts[-100:]

        # Update source seen_ids
        if source_id in self._sources:
            s = self._sources[source_id]
            if str(message_id) not in s.seen_ids:
                s.seen_ids.append(str(message_id))
                if len(s.seen_ids) > 500:
                    s.seen_ids = s.seen_ids[-500:]

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.save_delivered_post(post_item)
            await firebase_service.increment_stat("posts_delivered", 1)
        return True

    # --------------------------------------------------------------------------
    # Destination Management (Channels, Groups, Private chats)
    # --------------------------------------------------------------------------
    async def get_all_destinations(self) -> List[DestinationItem]:
        await self.init()
        return list(self._destinations.values())

    async def get_destination(self, chat_id: int) -> Optional[DestinationItem]:
        await self.init()
        return self._destinations.get(chat_id)

    async def get_destinations_for_user(self, user_id: int) -> List[DestinationItem]:
        """Returns destination channels connected by or available to this user."""
        await self.init()
        if config.is_super_admin(user_id):
            return list(self._destinations.values())
        return [d for d in self._destinations.values() if d.added_by == user_id or d.chat_id == user_id]

    async def save_destination(
        self,
        chat_id: int,
        title: str,
        username: Optional[str] = None,
        chat_type: str = "channel",
        can_post: bool = True,
        added_by: int = 0,
    ) -> DestinationItem:
        """Registers or updates a destination channel/chat."""
        await self.init()
        now = datetime.utcnow().isoformat()
        if chat_id in self._destinations:
            dest = self._destinations[chat_id]
            if title:
                dest.title = title
            if username:
                dest.username = username
            if chat_type:
                dest.type = chat_type
            dest.can_post = can_post
            if added_by:
                dest.added_by = added_by
            dest.updated_at = now
        else:
            dest = DestinationItem(
                chat_id=chat_id,
                title=title or f"Chat {chat_id}",
                username=username,
                type=chat_type,
                can_post=can_post,
                added_by=added_by,
                created_at=now,
                updated_at=now,
            )
            self._destinations[chat_id] = dest

        # Update legacy _subscribers representation
        self._subscribers[chat_id] = {
            "chat_id": chat_id,
            "title": dest.title,
            "type": dest.type,
            "feeds": [s.id for s in self._sources.values() if chat_id in s.destinations],
            "joined_at": dest.created_at,
        }

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.save_destination(dest.to_dict())
        return dest

    async def remove_destination(self, chat_id: int) -> bool:
        await self.init()
        removed = self._destinations.pop(chat_id, None)
        self._subscribers.pop(chat_id, None)
        # Remove from all sources
        for s in self._sources.values():
            if chat_id in s.destinations:
                s.destinations.remove(chat_id)
        for f in self._feeds.values():
            if chat_id in f.subscribers:
                f.subscribers.remove(chat_id)

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.delete_destination(chat_id)
        return removed is not None

    # --------------------------------------------------------------------------
    # Source Management (RSS & Telegram Channels)
    # --------------------------------------------------------------------------
    async def get_all_sources(self) -> List[SourceItem]:
        await self.init()
        return list(self._sources.values())

    async def get_source(self, source_id: str) -> Optional[SourceItem]:
        await self.init()
        return self._sources.get(source_id)

    async def get_sources_for_user(self, user_id: int) -> List[SourceItem]:
        await self.init()
        if config.is_super_admin(user_id):
            return list(self._sources.values())
        return [s for s in self._sources.values() if s.owner_id == user_id]

    async def get_sources_by_telegram_chat_id(self, chat_id: int) -> List[SourceItem]:
        """Finds all registered telegram_channel sources matching chat_id."""
        await self.init()
        target_str = str(chat_id)
        target_id = f"tg_{chat_id}"
        results = []
        for s in self._sources.values():
            if s.type == "telegram_channel":
                if s.id == target_id or s.url_or_id == target_str:
                    results.append(s)
        return results

    async def add_telegram_source(
        self,
        source_chat_id: int,
        source_title: str,
        source_username: Optional[str],
        destination_chat_id: int,
        owner_id: int,
    ) -> Tuple[SourceItem, bool]:
        """Connects a Telegram source channel to a destination channel."""
        await self.init()
        source_id = f"tg_{source_chat_id}"
        is_new = False

        if source_id in self._sources:
            source = self._sources[source_id]
            if destination_chat_id not in source.destinations:
                source.destinations.append(destination_chat_id)
            if source_title:
                source.title = source_title
            if source_username:
                source.link = f"https://t.me/{source_username}"
        else:
            is_new = True
            source = SourceItem(
                id=source_id,
                type="telegram_channel",
                url_or_id=str(source_chat_id),
                title=source_title or f"Telegram Channel {source_chat_id}",
                link=f"https://t.me/{source_username}" if source_username else "",
                owner_id=owner_id,
                destinations=[destination_chat_id],
                seen_ids=[],
                created_at=datetime.utcnow().isoformat(),
            )
            self._sources[source_id] = source

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.save_source(source.to_dict())
        return source, is_new

    async def add_rss_source(
        self,
        url: str,
        title: str,
        link: str,
        destination_chat_id: int,
        owner_id: int,
        seen_hashes: Optional[List[str]] = None,
    ) -> Tuple[SourceItem, bool]:
        """Connects a Website RSS feed to a destination channel."""
        await self.init()
        source_id = f"rss_{make_feed_id(url)}"
        legacy_feed_id = make_feed_id(url)
        is_new = False

        if source_id in self._sources:
            source = self._sources[source_id]
            if destination_chat_id not in source.destinations:
                source.destinations.append(destination_chat_id)
            if title and source.title in ("Nomsiz RSS", "Nomsiz Manba"):
                source.title = title
        else:
            is_new = True
            source = SourceItem(
                id=source_id,
                type="rss",
                url_or_id=url,
                title=title or "Nomsiz RSS",
                link=link or url,
                owner_id=owner_id,
                destinations=[destination_chat_id],
                seen_ids=list(seen_hashes or []),
                created_at=datetime.utcnow().isoformat(),
            )
            self._sources[source_id] = source

        # Mirror in _feeds for legacy gardener compatibility
        self._feeds[legacy_feed_id] = RSSFeed(
            id=legacy_feed_id,
            url=url,
            title=source.title,
            link=source.link,
            subscribers=list(source.destinations),
            seen_hashes=list(source.seen_ids),
            created_at=source.created_at,
        )

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.save_source(source.to_dict())
            await firebase_service.save_rss_feed(self._feeds[legacy_feed_id].to_dict())
        return source, is_new

    async def delete_source(self, source_id: str, user_id: Optional[int] = None) -> bool:
        """Deletes a source. If user_id is provided, verifies ownership or super admin privilege."""
        await self.init()
        source = self._sources.get(source_id)
        if not source:
            # Check legacy feed_id
            legacy_src_id = f"rss_{source_id}"
            source = self._sources.get(legacy_src_id)
            if source:
                source_id = legacy_src_id

        if not source:
            return False

        if user_id is not None and not config.is_super_admin(user_id):
            if source.owner_id != user_id:
                return False

        self._sources.pop(source_id, None)
        # Also remove from feeds
        raw_id = source_id.replace("rss_", "").replace("tg_", "")
        self._feeds.pop(raw_id, None)
        self._feeds.pop(source_id, None)

        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.delete_source(source_id)
            await firebase_service.delete_rss_feed(raw_id)
        return True

    # --------------------------------------------------------------------------
    # Backward-Compatible RSS Feed Operations (Used by gardener.py & /sub /unsub)
    # --------------------------------------------------------------------------
    async def get_all_feeds(self) -> List[RSSFeed]:
        await self.init()
        return list(self._feeds.values())

    async def get_feed_by_id(self, feed_id: str) -> Optional[RSSFeed]:
        await self.init()
        if feed_id in self._feeds:
            return self._feeds[feed_id]
        if f"rss_{feed_id}" in self._sources:
            s = self._sources[f"rss_{feed_id}"]
            return RSSFeed(
                id=feed_id,
                url=s.url_or_id,
                title=s.title,
                link=s.link,
                subscribers=list(s.destinations),
                seen_hashes=list(s.seen_ids),
                error_count=s.error_count,
                last_error=s.last_error,
                last_checked=s.last_checked,
            )
        return None

    async def get_feed_by_url(self, url: str) -> Optional[RSSFeed]:
        await self.init()
        fid = make_feed_id(url)
        if fid in self._feeds:
            return self._feeds[fid]
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
        """Legacy helper for /sub command."""
        await self.init()
        # Save destination
        await self.save_destination(
            chat_id=chat_id,
            title=chat_title or f"Chat {chat_id}",
            chat_type=chat_type,
            added_by=chat_id if chat_id > 0 else 0,
        )
        # Add RSS source
        source, is_new = await self.add_rss_source(
            url=feed_url,
            title=title,
            link=link,
            destination_chat_id=chat_id,
            owner_id=chat_id if chat_id > 0 else 0,
            seen_hashes=initial_seen_hashes,
        )
        fid = make_feed_id(feed_url)
        feed = self._feeds.get(fid) or RSSFeed(
            id=fid,
            url=feed_url,
            title=title,
            link=link,
            subscribers=[chat_id],
            seen_hashes=list(initial_seen_hashes or []),
        )
        return feed, is_new

    async def remove_subscription(self, chat_id: int, feed_id: str) -> bool:
        await self.init()
        feed = await self.get_feed_by_id(feed_id)
        if not feed:
            return False

        if chat_id in feed.subscribers:
            feed.subscribers.remove(chat_id)

        # Update source
        src_id = f"rss_{feed.id}"
        if src_id in self._sources:
            s = self._sources[src_id]
            if chat_id in s.destinations:
                s.destinations.remove(chat_id)
            if not s.destinations:
                await self.delete_source(src_id)

        if not feed.subscribers:
            self._feeds.pop(feed.id, None)

        await self._save_local()
        return True

    async def remove_all_subscriptions(self, chat_id: int) -> int:
        await self.init()
        count = 0
        for feed in list(self._feeds.values()):
            if chat_id in feed.subscribers:
                feed.subscribers.remove(chat_id)
                count += 1
                if not feed.subscribers:
                    self._feeds.pop(feed.id, None)

        for source in list(self._sources.values()):
            if chat_id in source.destinations:
                source.destinations.remove(chat_id)
                if not source.destinations:
                    self._sources.pop(source.id, None)

        await self._save_local()
        return count

    async def get_subscriptions_for_chat(self, chat_id: int) -> List[RSSFeed]:
        await self.init()
        return [f for f in self._feeds.values() if chat_id in f.subscribers]

    async def record_post_delivery(
        self,
        feed_id: str,
        feed_title: str,
        title: str,
        link: str,
        recipients_count: int,
        published_at: Optional[str] = None,
    ):
        """Records delivery of a newly published post from RSS."""
        now = datetime.utcnow().isoformat()
        post_record = {
            "id": f"{feed_id}_{int(time.time() * 1000)}",
            "feed_id": feed_id,
            "feed_title": feed_title,
            "source_type": "rss",
            "title": title,
            "link": link,
            "published_at": published_at or now,
            "delivered_at": now,
            "recipients_count": recipients_count,
        }
        self._recent_posts.append(post_record)
        if len(self._recent_posts) > 100:
            self._recent_posts = self._recent_posts[-100:]

        self._posts_delivered += recipients_count
        await self._save_local()
        if firebase_service.is_initialized():
            await firebase_service.save_delivered_post(post_record)
            await firebase_service.increment_stat("posts_delivered", recipients_count)

    async def update_feed_success(
        self,
        feed_id: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        new_seen_hashes: Optional[List[str]] = None,
    ):
        feed = self._feeds.get(feed_id)
        now = datetime.utcnow().isoformat()
        if feed:
            feed.error_count = 0
            feed.last_error = None
            feed.last_checked = now
            feed.last_updated = now
            if etag:
                feed.etag = etag
            if last_modified:
                feed.last_modified = last_modified
            if new_seen_hashes:
                seen_set = set(feed.seen_hashes)
                seen_set.update(new_seen_hashes)
                feed.seen_hashes = list(seen_set)[-500:]

        # Sync with SourceItem
        src_id = f"rss_{feed_id}"
        if src_id in self._sources:
            s = self._sources[src_id]
            s.error_count = 0
            s.last_error = None
            s.last_checked = now
            if new_seen_hashes:
                seen_set = set(s.seen_ids)
                seen_set.update(new_seen_hashes)
                s.seen_ids = list(seen_set)[-500:]

        await self._save_local()

    async def update_feed_error(self, feed_id: str, error_message: str):
        feed = self._feeds.get(feed_id)
        now = datetime.utcnow().isoformat()
        if feed:
            feed.error_count += 1
            feed.last_error = error_message
            feed.last_checked = now

        src_id = f"rss_{feed_id}"
        if src_id in self._sources:
            s = self._sources[src_id]
            s.error_count += 1
            s.last_error = error_message
            s.last_checked = now

        await self._save_local()

    async def update_feed_state(
        self,
        feed_id: str,
        seen_hashes: Optional[List[str]] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Unified feed status updater used by gardener background engine."""
        if error:
            await self.update_feed_error(feed_id, error)
        else:
            await self.update_feed_success(
                feed_id,
                etag=etag,
                last_modified=last_modified,
                new_seen_hashes=seen_hashes,
            )

    async def record_delivery(
        self,
        feed_title: str,
        item_title: str,
        item_link: str,
        recipient_count: int,
    ):
        """Convenience alias for delivery recording used by gardener."""
        await self.record_post_delivery(
            feed_id="feed",
            feed_title=feed_title,
            title=item_title,
            link=item_link,
            recipients_count=recipient_count,
        )

    async def get_stats(self) -> Dict[str, Any]:
        await self.init()
        total_subscribers = len(self._destinations)
        active_subscriptions = sum(len(s.destinations) for s in self._sources.values())
        return {
            "total_sources": len(self._sources),
            "total_feeds": len(self._feeds),
            "total_destinations": total_subscribers,
            "total_subscribers": total_subscribers,
            "active_subscriptions": active_subscriptions,
            "posts_delivered": self._posts_delivered,
            "recent_posts": self._recent_posts[-20:],
        }

    async def export_opml(self, chat_id: int) -> str:
        feeds = await self.get_subscriptions_for_chat(chat_id)
        opml_data = [{"title": f.title, "url": f.url, "link": f.link} for f in feeds]
        return build_opml(opml_data, title=f"AnjurX RSS Obunalari - Chat {chat_id}")


# Global singleton instance
rss_storage = RSSStorage()
