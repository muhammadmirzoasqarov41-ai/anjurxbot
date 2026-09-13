"""
Unified Data Storage and Persistence for AnjurX | Obuna Bot.
Implements:
- SourceItem: Super-Admin managed sources (RSS/Atom/JSON feed)
- ChannelItem: Connected Telegram destination channels with individual limits, sources, schedules
- PostItem: 5-day retention Post Pool for news distribution
- DeliveredPostItem: Strict duplicate protection per (source, external_id, channel)
- UserItem: User profiles with Plan (FREE vs CONTRACT) and custom limits
- Dual persistence: local JSON database file (./data/rssbot.json) and Firebase Firestore
"""
import os
import json
import time
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
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


def get_tashkent_now() -> datetime:
    """Returns current datetime in Tashkent (UTC+5) for accurate daily limit resets."""
    # Tashkent is UTC+5 without DST
    return datetime.utcnow() + timedelta(hours=5)


def get_today_tashkent_str() -> str:
    """Returns today's date in Tashkent as YYYY-MM-DD."""
    return get_tashkent_now().strftime("%Y-%m-%d")


# ==============================================================================
# DATA MODELS
# ==============================================================================

@dataclass
class SourceItem:
    """Represents a Super Admin managed news source (RSS/Atom/JSON feed)."""
    id: str  # e.g. "src_kunuz" or "src_<hash>"
    name: str  # Display name e.g. "Kun.uz"
    url: str  # Feed URL
    type: str = "rss"  # "rss", "atom", "json"
    category: str = "Yangiliklar"
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_fetch_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    error_count: int = 0
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    posts_count: int = 0

    # Backward compatibility properties for existing modules
    @property
    def title(self) -> str:
        return self.name

    @property
    def link(self) -> str:
        return self.url

    @property
    def subscribers(self) -> List[int]:
        return []

    @property
    def seen_hashes(self) -> List[str]:
        return []

    @property
    def destinations(self) -> List[int]:
        return []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceItem":
        sid = str(d.get("id") or make_feed_id(d.get("url") or d.get("url_or_id") or "unknown"))
        name = str(d.get("name") or d.get("title") or "Nomsiz Manba")
        url = str(d.get("url") or d.get("url_or_id") or d.get("link") or "")
        stype = str(d.get("type") or "rss")
        cat = str(d.get("category") or "Yangiliklar")
        act = bool(d.get("active", True))
        err_cnt = int(d.get("error_count", 0)) if str(d.get("error_count", 0)).isdigit() else 0
        posts_cnt = int(d.get("posts_count", 0)) if str(d.get("posts_count", 0)).isdigit() else 0

        return cls(
            id=sid,
            name=name,
            url=url,
            type=stype,
            category=cat,
            active=act,
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
            last_fetch_at=d.get("last_fetch_at") or d.get("last_checked"),
            last_success_at=d.get("last_success_at"),
            last_error=d.get("last_error"),
            error_count=err_cnt,
            etag=d.get("etag"),
            last_modified=d.get("last_modified"),
            posts_count=posts_cnt,
        )


@dataclass
class ChannelItem:
    """Represents a connected Telegram destination channel owned by a user."""
    chat_id: int
    title: str
    username: Optional[str] = None
    owner_user_id: int = 0
    active: bool = True
    can_post: bool = True
    daily_limit: int = 3  # Normal users strictly max 3; contract users can have higher limit
    plan: str = "free"  # "free" or "contract"
    schedule_mode: str = "instant"  # "instant" or "scheduled"
    schedule_times: List[str] = field(default_factory=lambda: ["09:00", "14:00", "19:00"])
    selected_sources: List[str] = field(default_factory=list)  # list of source_ids
    today_delivered_count: int = 0
    today_date: str = field(default_factory=get_today_tashkent_str)
    last_delivered_at: Optional[str] = None
    total_delivered_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def reset_daily_if_needed(self, today_str: Optional[str] = None) -> bool:
        """Resets today_delivered_count if date has changed in Tashkent timezone."""
        today = today_str or get_today_tashkent_str()
        if self.today_date != today:
            self.today_date = today
            self.today_delivered_count = 0
            self.updated_at = datetime.utcnow().isoformat()
            return True
        return False

    def is_limit_reached(self) -> bool:
        self.reset_daily_if_needed()
        return self.today_delivered_count >= self.daily_limit

    def set_daily_limit(self, limit: int, is_super_admin: bool = False):
        """Strictly enforces max 3 for free users; allows custom for contract users/admins."""
        if not is_super_admin and self.plan != "contract":
            self.daily_limit = min(max(1, int(limit)), 3)
        else:
            self.daily_limit = max(1, int(limit))
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ChannelItem":
        cid = 0
        try:
            cid = int(d.get("chat_id", 0))
        except (ValueError, TypeError):
            cid = 0

        owner = 0
        try:
            owner = int(d.get("owner_user_id") or d.get("added_by") or 0)
        except (ValueError, TypeError):
            owner = 0

        limit = 3
        try:
            limit = int(d.get("daily_limit", 3))
        except (ValueError, TypeError):
            limit = 3

        plan = str(d.get("plan") or "free")
        if plan != "contract":
            limit = min(max(1, limit), 3)

        raw_srcs = d.get("selected_sources", [])
        srcs = [str(s) for s in raw_srcs if s] if isinstance(raw_srcs, list) else []

        raw_times = d.get("schedule_times", ["09:00", "14:00", "19:00"])
        times = [str(t) for t in raw_times if t] if isinstance(raw_times, list) else ["09:00", "14:00", "19:00"]

        return cls(
            chat_id=cid,
            title=str(d.get("title") or f"Kanal {cid}"),
            username=d.get("username"),
            owner_user_id=owner,
            active=bool(d.get("active", True)),
            can_post=bool(d.get("can_post", True)),
            daily_limit=limit,
            plan=plan,
            schedule_mode=str(d.get("schedule_mode") or "instant"),
            schedule_times=times,
            selected_sources=srcs,
            today_delivered_count=int(d.get("today_delivered_count", 0)),
            today_date=str(d.get("today_date") or get_today_tashkent_str()),
            last_delivered_at=d.get("last_delivered_at"),
            total_delivered_count=int(d.get("total_delivered_count", 0)),
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
        )


@dataclass
class PostItem:
    """Represents an article stored in the 5-Day Retention Post Pool."""
    post_id: str  # Unique ID e.g. "post_<hash>"
    source_id: str
    source_name: str
    external_post_id: str  # URL or GUID hash from source
    title: str
    description: str
    content: str
    url: str
    image_url: Optional[str] = None
    media_type: Optional[str] = None
    published_at: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: str = field(
        default_factory=lambda: (datetime.utcnow() + timedelta(days=5)).isoformat()
    )
    status: str = "queued"  # "queued", "assigned", "delivered", "expired", "failed"
    assigned_channel_id: Optional[int] = None
    delivered_at: Optional[str] = None
    attempts: int = 0
    last_error: Optional[str] = None

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        curr = now or datetime.utcnow()
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return curr > exp
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PostItem":
        fetched = str(d.get("fetched_at") or datetime.utcnow().isoformat())
        default_exp = (datetime.utcnow() + timedelta(days=5)).isoformat()
        expires = str(d.get("expires_at") or default_exp)

        return cls(
            post_id=str(d.get("post_id") or make_feed_id(d.get("url") or str(time.time()))),
            source_id=str(d.get("source_id") or ""),
            source_name=str(d.get("source_name") or "Manba"),
            external_post_id=str(d.get("external_post_id") or make_feed_id(d.get("url") or "")),
            title=str(d.get("title") or "Yangi post"),
            description=str(d.get("description") or ""),
            content=str(d.get("content") or ""),
            url=str(d.get("url") or ""),
            image_url=d.get("image_url"),
            media_type=d.get("media_type"),
            published_at=d.get("published_at"),
            fetched_at=fetched,
            expires_at=expires,
            status=str(d.get("status") or "queued"),
            assigned_channel_id=d.get("assigned_channel_id"),
            delivered_at=d.get("delivered_at"),
            attempts=int(d.get("attempts", 0)),
            last_error=d.get("last_error"),
        )


@dataclass
class UserItem:
    """Represents a Telegram user registered with AnjurX."""
    user_id: int
    username: Optional[str] = None
    first_name: str = ""
    plan: str = "free"  # "free" or "contract"
    custom_limit: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserItem":
        uid = 0
        try:
            uid = int(d.get("user_id", 0))
        except (ValueError, TypeError):
            uid = 0
        return cls(
            user_id=uid,
            username=d.get("username"),
            first_name=str(d.get("first_name") or ""),
            plan=str(d.get("plan") or "free"),
            custom_limit=int(d["custom_limit"]) if d.get("custom_limit") is not None else None,
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
        )


# Backward compatibility aliases for existing code
RSSFeed = SourceItem
DestinationItem = ChannelItem


# ==============================================================================
# MAIN STORAGE CLASS
# ==============================================================================

class RSSStorage:
    """Central data store managing sources, channels, post pool, and deliveries."""

    def __init__(self):
        self._sources: Dict[str, SourceItem] = {}
        self._channels: Dict[int, ChannelItem] = {}
        self._posts: Dict[str, PostItem] = {}
        self._users: Dict[int, UserItem] = {}
        self._delivered_signatures: Set[str] = set()  # "src:ext_id:chat_id"
        self._recent_posts: List[Dict[str, Any]] = []
        self._posts_delivered: int = 0
        self._loaded: bool = False
        self._lock = asyncio.Lock()

    @property
    def db_path(self) -> str:
        return get_db_path()

    @property
    def data_dir(self) -> str:
        return os.path.dirname(self.db_path)

    # Aliases for backward compatibility
    @property
    def _feeds(self) -> Dict[str, SourceItem]:
        return self._sources

    @property
    def _destinations(self) -> Dict[int, ChannelItem]:
        return self._channels

    @property
    def _subscribers(self) -> Dict[int, Dict[str, Any]]:
        return {
            cid: {
                "chat_id": cid,
                "title": c.title,
                "type": "channel",
                "feeds": c.selected_sources,
                "can_post": c.can_post,
                "added_by": c.owner_user_id,
            }
            for cid, c in self._channels.items()
        }

    async def init(self):
        """Initializes database, connecting Firebase and loading local state."""
        if self._loaded:
            return
        os.makedirs(self.data_dir, exist_ok=True)
        try:
            await firebase_service.initialize()
        except Exception as e:
            logger.info(f"Firebase initialization skipped or unavailable: {e}. Running in local storage mode.")

        await self._load_data()
        self._seed_default_sources_if_empty()
        self._loaded = True

    def _seed_default_sources_if_empty(self):
        """Seeds standard, verified Uzbek news feeds if no sources exist."""
        if not self._sources:
            default_sources = [
                SourceItem(
                    id="src_kunuz",
                    name="Kun.uz",
                    url="https://kun.uz/news/rss",
                    type="rss",
                    category="Yangiliklar",
                    active=True,
                ),
                SourceItem(
                    id="src_daryouz",
                    name="Daryo.uz",
                    url="https://daryo.uz/rss/",
                    type="rss",
                    category="Yangiliklar",
                    active=True,
                ),
                SourceItem(
                    id="src_gazetauz",
                    name="Gazeta.uz",
                    url="https://www.gazeta.uz/uz/rss/",
                    type="rss",
                    category="Yangiliklar",
                    active=True,
                ),
            ]
            for s in default_sources:
                self._sources[s.id] = s
            logger.info(f"Seeded {len(default_sources)} default news sources.")

    async def _load_data(self):
        """Loads state from local JSON file or Firestore."""
        # 1. Local JSON read
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        self._normalize_and_load(data)
                        logger.info(
                            f"Loaded local database: {len(self._sources)} sources, "
                            f"{len(self._channels)} channels, {len(self._posts)} posts in pool."
                        )
            except Exception as e:
                logger.error(f"Error loading local database {self.db_path}: {e}")

        # 2. Sync with Firestore if active
        if firebase_service.is_initialized():
            try:
                fs_sources = await firebase_service.db.list_documents("sources", limit=500)
                for s in fs_sources:
                    item = SourceItem.from_dict(s)
                    self._sources[item.id] = item

                fs_channels = await firebase_service.db.list_documents("channels", limit=500)
                for c in fs_channels:
                    citem = ChannelItem.from_dict(c)
                    if citem.chat_id != 0:
                        self._channels[citem.chat_id] = citem

                fs_posts = await firebase_service.db.list_documents("posts", limit=1000)
                for p in fs_posts:
                    pitem = PostItem.from_dict(p)
                    self._posts[pitem.post_id] = pitem

                fs_users = await firebase_service.db.list_documents("users", limit=500)
                for u in fs_users:
                    uitem = UserItem.from_dict(u)
                    if uitem.user_id != 0:
                        self._users[uitem.user_id] = uitem

                fs_delivered = await firebase_service.db.list_documents("delivered_posts", limit=2000)
                for d in fs_delivered:
                    sig = str(d.get("signature") or d.get("_id") or "")
                    if sig:
                        self._delivered_signatures.add(sig)

                logger.info("Synchronized data with Firebase Firestore.")
            except Exception as e:
                logger.warning(f"Failed to sync with Firestore: {e}")

    def _normalize_and_load(self, data: Any):
        """Parses and normalizes dictionary content into typed in-memory objects."""
        if not isinstance(data, dict):
            return

        # Sources
        raw_sources = data.get("sources", {})
        if isinstance(raw_sources, dict):
            for k, v in raw_sources.items():
                if isinstance(v, dict):
                    v.setdefault("id", k)
                    src = SourceItem.from_dict(v)
                    self._sources[src.id] = src

        # Legacy feeds mapping
        raw_feeds = data.get("feeds", {})
        if isinstance(raw_feeds, dict):
            for k, v in raw_feeds.items():
                if isinstance(v, dict) and k not in self._sources:
                    src = SourceItem(
                        id=k,
                        name=str(v.get("title") or "Nomsiz RSS"),
                        url=str(v.get("url") or v.get("link") or ""),
                        type="rss",
                        category="Yangiliklar",
                        active=True,
                        last_fetch_at=v.get("last_checked"),
                        etag=v.get("etag"),
                        last_modified=v.get("last_modified"),
                    )
                    self._sources[src.id] = src

        # Channels (and legacy destinations)
        raw_channels = data.get("channels", data.get("destinations", {}))
        if isinstance(raw_channels, dict):
            for k, v in raw_channels.items():
                if isinstance(v, dict):
                    try:
                        cid = int(v.get("chat_id") or k)
                        v["chat_id"] = cid
                        channel = ChannelItem.from_dict(v)
                        if channel.chat_id != 0:
                            self._channels[channel.chat_id] = channel
                    except (ValueError, TypeError):
                        pass

        # Posts (5-day retention pool)
        raw_posts = data.get("posts", {})
        if isinstance(raw_posts, dict):
            for k, v in raw_posts.items():
                if isinstance(v, dict):
                    v.setdefault("post_id", k)
                    post = PostItem.from_dict(v)
                    self._posts[post.post_id] = post

        # Users
        raw_users = data.get("users", {})
        if isinstance(raw_users, dict):
            for k, v in raw_users.items():
                if isinstance(v, dict):
                    try:
                        uid = int(v.get("user_id") or k)
                        v["user_id"] = uid
                        user = UserItem.from_dict(v)
                        if user.user_id != 0:
                            self._users[user.user_id] = user
                    except (ValueError, TypeError):
                        pass

        # Delivered signatures
        raw_delivered = data.get("delivered_signatures", data.get("delivered_keys", []))
        if isinstance(raw_delivered, list):
            self._delivered_signatures = set(str(x) for x in raw_delivered if x)

        self._posts_delivered = int(data.get("posts_delivered", len(self._delivered_signatures)))
        self._recent_posts = data.get("recent_posts", [])

    async def _save_local(self):
        """Atomically saves in-memory state to disk in JSON format with tempfile swap."""
        payload = {
            "version": 2,
            "sources": {k: v.to_dict() for k, v in self._sources.items()},
            "channels": {str(k): v.to_dict() for k, v in self._channels.items()},
            "posts": {k: v.to_dict() for k, v in self._posts.items()},
            "users": {str(k): v.to_dict() for k, v in self._users.items()},
            "delivered_signatures": list(self._delivered_signatures),
            "posts_delivered": self._posts_delivered,
            "recent_posts": self._recent_posts[-100:],
            "updated_at": datetime.utcnow().isoformat(),
        }
        tmp_path = f"{self.db_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.db_path)
        except Exception as e:
            logger.error(f"Failed to write local database to {self.db_path}: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # ==========================================================================
    # SOURCE OPERATIONS (Super Admin Only)
    # ==========================================================================

    async def get_all_sources(self) -> List[SourceItem]:
        await self.init()
        return list(self._sources.values())

    async def get_active_sources(self) -> List[SourceItem]:
        await self.init()
        return [s for s in self._sources.values() if s.active]

    async def get_source(self, source_id: str) -> Optional[SourceItem]:
        await self.init()
        return self._sources.get(source_id)

    async def add_source(
        self,
        name: str,
        url: str,
        source_type: str = "rss",
        category: str = "Yangiliklar",
    ) -> SourceItem:
        """Adds a new verified source into the system. Only Super Admin can call this."""
        await self.init()
        async with self._lock:
            sid = f"src_{make_feed_id(url)}"
            source = SourceItem(
                id=sid,
                name=name,
                url=url,
                type=source_type,
                category=category,
                active=True,
            )
            self._sources[sid] = source
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("sources", sid, source.to_dict())
                except Exception as e:
                    logger.warning(f"Firestore set_document failed for source {sid}: {e}")

            logger.info(f"Source added: '{name}' ({url}) as ID {sid}")
            return source

    async def update_source(self, source_id: str, **kwargs) -> Optional[SourceItem]:
        await self.init()
        async with self._lock:
            source = self._sources.get(source_id)
            if not source:
                return None
            for k, v in kwargs.items():
                if hasattr(source, k):
                    setattr(source, k, v)
            source.updated_at = datetime.utcnow().isoformat()
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("sources", source_id, source.to_dict())
                except Exception as e:
                    logger.warning(f"Firestore update failed for source {source_id}: {e}")
            return source

    async def delete_source(self, source_id: str) -> bool:
        await self.init()
        async with self._lock:
            if source_id in self._sources:
                del self._sources[source_id]
                # Remove from channel selections
                for ch in self._channels.values():
                    if source_id in ch.selected_sources:
                        ch.selected_sources.remove(source_id)
                        ch.updated_at = datetime.utcnow().isoformat()
                await self._save_local()

                if firebase_service.is_initialized():
                    try:
                        await firebase_service.db.delete_document("sources", source_id)
                    except Exception as e:
                        logger.warning(f"Firestore delete failed for source {source_id}: {e}")
                return True
            return False

    async def toggle_source(self, source_id: str) -> Optional[bool]:
        source = await self.get_source(source_id)
        if not source:
            return None
        new_active = not source.active
        await self.update_source(source_id, active=new_active)
        return new_active

    # ==========================================================================
    # CHANNEL OPERATIONS (Normal Users manage their own; Super Admin views all)
    # ==========================================================================

    async def get_all_channels(self) -> List[ChannelItem]:
        await self.init()
        return list(self._channels.values())

    async def get_channel(self, chat_id: int) -> Optional[ChannelItem]:
        await self.init()
        ch = self._channels.get(int(chat_id))
        if ch:
            ch.reset_daily_if_needed()
        return ch

    async def get_channels_for_user(self, user_id: int) -> List[ChannelItem]:
        """Returns only channels owned by user_id. Prevents IDOR!"""
        await self.init()
        today = get_today_tashkent_str()
        results = []
        for ch in self._channels.values():
            if ch.owner_user_id == int(user_id):
                ch.reset_daily_if_needed(today)
                results.append(ch)
        return results

    async def register_or_update_channel(
        self,
        chat_id: int,
        title: str,
        username: Optional[str] = None,
        owner_user_id: int = 0,
        can_post: bool = True,
    ) -> ChannelItem:
        """Saves channel upon my_chat_member or verification."""
        await self.init()
        async with self._lock:
            cid = int(chat_id)
            existing = self._channels.get(cid)
            today = get_today_tashkent_str()

            if existing:
                existing.title = title
                if username:
                    existing.username = username
                if owner_user_id > 0:
                    existing.owner_user_id = owner_user_id
                existing.can_post = can_post
                existing.updated_at = datetime.utcnow().isoformat()
                existing.reset_daily_if_needed(today)
                channel = existing
            else:
                # Default all active sources selected initially for great UX
                default_sources = [s.id for s in self._sources.values() if s.active]
                channel = ChannelItem(
                    chat_id=cid,
                    title=title,
                    username=username,
                    owner_user_id=owner_user_id,
                    active=True,
                    can_post=can_post,
                    daily_limit=3,
                    plan="free",
                    schedule_mode="instant",
                    schedule_times=["09:00", "14:00", "19:00"],
                    selected_sources=default_sources,
                    today_delivered_count=0,
                    today_date=today,
                )
                self._channels[cid] = channel

            await self._save_local()
            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("channels", str(cid), channel.to_dict())
                except Exception as e:
                    logger.warning(f"Firestore set_document failed for channel {cid}: {e}")

            return channel

    async def update_channel_sources(self, chat_id: int, selected_sources: List[str], user_id: int) -> bool:
        """Updates sources subscribed by this channel with ownership check."""
        await self.init()
        async with self._lock:
            channel = self._channels.get(int(chat_id))
            if not channel or (channel.owner_user_id != user_id and not config.is_super_admin(user_id)):
                return False
            channel.selected_sources = selected_sources
            channel.updated_at = datetime.utcnow().isoformat()
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("channels", str(chat_id), channel.to_dict())
                except Exception:
                    pass
            return True

    async def update_channel_settings(
        self,
        chat_id: int,
        user_id: int,
        daily_limit: Optional[int] = None,
        schedule_mode: Optional[str] = None,
        schedule_times: Optional[List[str]] = None,
        active: Optional[bool] = None,
        is_super_admin: bool = False,
    ) -> Optional[ChannelItem]:
        """Updates daily limits, schedules, and pause/resume with strict limit bounds."""
        await self.init()
        async with self._lock:
            channel = self._channels.get(int(chat_id))
            if not channel:
                return None
            if channel.owner_user_id != user_id and not is_super_admin:
                return None

            if daily_limit is not None:
                channel.set_daily_limit(daily_limit, is_super_admin=is_super_admin)
            if schedule_mode is not None:
                channel.schedule_mode = schedule_mode
            if schedule_times is not None:
                channel.schedule_times = schedule_times
            if active is not None:
                channel.active = active

            channel.updated_at = datetime.utcnow().isoformat()
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("channels", str(chat_id), channel.to_dict())
                except Exception:
                    pass
            return channel

    async def disconnect_channel(self, chat_id: int, user_id: int) -> bool:
        """Disconnects channel with ownership check."""
        await self.init()
        async with self._lock:
            channel = self._channels.get(int(chat_id))
            if not channel or (channel.owner_user_id != user_id and not config.is_super_admin(user_id)):
                return False
            del self._channels[int(chat_id)]
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.delete_document("channels", str(chat_id))
                except Exception:
                    pass
            return True

    # ==========================================================================
    # USER & CONTRACT PLAN OPERATIONS
    # ==========================================================================

    async def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: str = "",
    ) -> UserItem:
        await self.init()
        async with self._lock:
            uid = int(user_id)
            if uid in self._users:
                user = self._users[uid]
                if username:
                    user.username = username
                if first_name:
                    user.first_name = first_name
                user.updated_at = datetime.utcnow().isoformat()
            else:
                user = UserItem(
                    user_id=uid,
                    username=username,
                    first_name=first_name,
                    plan="free",
                )
                self._users[uid] = user
            await self._save_local()
            return user

    async def get_all_users(self) -> List[UserItem]:
        await self.init()
        return list(self._users.values())

    async def set_user_contract_plan(
        self,
        user_id: int,
        plan: str = "contract",
        custom_limit: int = 10,
    ) -> Optional[UserItem]:
        """Super Admin sets contract plan and custom limit for user and their channels."""
        await self.init()
        async with self._lock:
            uid = int(user_id)
            user = self._users.get(uid)
            if not user:
                user = UserItem(user_id=uid, plan=plan, custom_limit=custom_limit)
                self._users[uid] = user
            else:
                user.plan = plan
                user.custom_limit = custom_limit
                user.updated_at = datetime.utcnow().isoformat()

            # Update channels owned by this user
            for ch in self._channels.values():
                if ch.owner_user_id == uid:
                    ch.plan = plan
                    ch.daily_limit = custom_limit
                    ch.updated_at = datetime.utcnow().isoformat()

            await self._save_local()
            return user

    # ==========================================================================
    # 5-DAY RETENTION POST POOL OPERATIONS
    # ==========================================================================

    async def save_post_to_pool(self, post: PostItem) -> bool:
        """Saves a normalized post into the 5-Day Retention Post Pool."""
        await self.init()
        async with self._lock:
            if post.post_id in self._posts:
                return False  # Already in pool
            self._posts[post.post_id] = post
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("posts", post.post_id, post.to_dict())
                except Exception:
                    pass
            return True

    async def get_post_from_pool(self, post_id: str) -> Optional[PostItem]:
        await self.init()
        return self._posts.get(post_id)

    async def get_queued_posts(self) -> List[PostItem]:
        """Returns all unexpired, queued posts awaiting distribution."""
        await self.init()
        now = datetime.utcnow()
        queued = []
        for p in self._posts.values():
            if p.status == "queued":
                if p.is_expired(now):
                    p.status = "expired"
                else:
                    queued.append(p)
        return queued

    async def update_post_status(
        self,
        post_id: str,
        status: str,
        assigned_channel_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> bool:
        await self.init()
        async with self._lock:
            post = self._posts.get(post_id)
            if not post:
                return False
            post.status = status
            if assigned_channel_id:
                post.assigned_channel_id = assigned_channel_id
            if status == "delivered":
                post.delivered_at = datetime.utcnow().isoformat()
            if error:
                post.last_error = error
                post.attempts += 1
            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("posts", post_id, post.to_dict())
                except Exception:
                    pass
            return True

    async def cleanup_expired_posts(self) -> int:
        """
        Cleans up expired posts (>5 days old) according to requirement 38.
        Keeps duplicate signatures intact to prevent ever re-sending historical news.
        """
        await self.init()
        async with self._lock:
            now = datetime.utcnow()
            expired_ids = []
            for pid, post in list(self._posts.items()):
                if post.is_expired(now):
                    post.status = "expired"
                    expired_ids.append(pid)

            if expired_ids:
                # Remove oldest expired posts from in-memory pool if pool exceeds 3000 items
                if len(self._posts) > 3000:
                    for pid in expired_ids[:500]:
                        self._posts.pop(pid, None)
                await self._save_local()
                logger.info(f"Cleaned up {len(expired_ids)} expired posts older than 5 days.")
            return len(expired_ids)

    # ==========================================================================
    # DUPLICATE PROTECTION & DELIVERY TRACKING
    # ==========================================================================

    def make_delivery_signature(self, source_id: str, external_post_id: str, channel_id: int) -> str:
        return f"{source_id}:{external_post_id}:{channel_id}"

    async def is_post_delivered(self, source_id: str, external_post_id: str, channel_id: int) -> bool:
        """Guarantees strict duplicate prevention per (source, external_id, channel)."""
        await self.init()
        sig = self.make_delivery_signature(source_id, external_post_id, channel_id)
        return sig in self._delivered_signatures

    async def record_delivery(
        self,
        source_id: str,
        external_post_id: str,
        channel_id: int,
        title: str,
        url: str,
        telegram_message_id: Optional[int] = None,
    ):
        """Records delivery to prevent duplication and tracks statistics."""
        await self.init()
        async with self._lock:
            sig = self.make_delivery_signature(source_id, external_post_id, channel_id)
            self._delivered_signatures.add(sig)
            self._posts_delivered += 1

            record = {
                "signature": sig,
                "source_id": source_id,
                "external_post_id": external_post_id,
                "channel_id": channel_id,
                "title": title,
                "url": url,
                "telegram_message_id": telegram_message_id,
                "delivered_at": datetime.utcnow().isoformat(),
            }
            self._recent_posts.append(record)
            if len(self._recent_posts) > 200:
                self._recent_posts = self._recent_posts[-200:]

            # Increment channel today count
            ch = self._channels.get(int(channel_id))
            if ch:
                ch.reset_daily_if_needed()
                ch.today_delivered_count += 1
                ch.total_delivered_count += 1
                ch.last_delivered_at = datetime.utcnow().isoformat()
                ch.updated_at = datetime.utcnow().isoformat()

            await self._save_local()

            if firebase_service.is_initialized():
                try:
                    await firebase_service.db.set_document("delivered_posts", sig, record)
                    await firebase_service.increment_stat("posts_delivered", 1)
                except Exception:
                    pass

    # ==========================================================================
    # STATS & MONITORING
    # ==========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        await self.init()
        active_channels = sum(1 for c in self._channels.values() if c.active and c.can_post)
        active_sources = sum(1 for s in self._sources.values() if s.active)

        queued_posts = sum(1 for p in self._posts.values() if p.status == "queued")
        delivered_posts = sum(1 for p in self._posts.values() if p.status == "delivered")
        expired_posts = sum(1 for p in self._posts.values() if p.status == "expired")
        failed_posts = sum(1 for p in self._posts.values() if p.status == "failed")

        return {
            "total_sources": len(self._sources),
            "active_sources": active_sources,
            "total_destinations": len(self._channels),
            "active_channels": active_channels,
            "total_users": len(self._users),
            "posts_delivered": self._posts_delivered,
            "pool_queued": queued_posts,
            "pool_delivered": delivered_posts,
            "pool_expired": expired_posts,
            "pool_failed": failed_posts,
            "total_in_pool": len(self._posts),
        }

    # ==========================================================================
    # BACKWARD COMPATIBILITY METHODS (for web_service & old calls)
    # ==========================================================================

    async def get_all_feeds(self) -> List[SourceItem]:
        return await self.get_all_sources()

    async def get_all_destinations(self) -> List[ChannelItem]:
        return await self.get_all_channels()

    async def get_destinations_for_user(self, user_id: int) -> List[ChannelItem]:
        return await self.get_channels_for_user(user_id)

    async def get_destination(self, chat_id: int) -> Optional[ChannelItem]:
        return await self.get_channel(chat_id)

    async def save_destination(
        self,
        chat_id: int,
        title: str,
        username: Optional[str] = None,
        chat_type: str = "channel",
        can_post: bool = True,
        added_by: int = 0,
    ) -> ChannelItem:
        return await self.register_or_update_channel(
            chat_id=chat_id,
            title=title,
            username=username,
            owner_user_id=added_by,
            can_post=can_post,
        )

    async def get_sources_for_user(self, user_id: int) -> List[SourceItem]:
        """In new architecture, all active sources are visible to user for selection."""
        return await self.get_active_sources()

    async def get_sources_by_telegram_chat_id(self, chat_id: int) -> List[SourceItem]:
        return []

    async def record_channel_delivery(
        self,
        source_chat_id: str,
        source_message_id: int,
        destination_chat_id: int,
        title: str,
    ):
        await self.record_delivery(
            source_id=f"tg_{source_chat_id}",
            external_post_id=str(source_message_id),
            channel_id=destination_chat_id,
            title=title,
            url="",
        )

    async def update_feed_state(
        self,
        feed_id: str,
        seen_hashes: Optional[List[str]] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        error: Optional[str] = None,
    ):
        source = await self.get_source(feed_id)
        if not source:
            return
        if error:
            source.error_count += 1
            source.last_error = error
        else:
            source.last_success_at = datetime.utcnow().isoformat()
            source.error_count = 0
            source.last_error = None
            if etag:
                source.etag = etag
            if last_modified:
                source.last_modified = last_modified
        source.last_fetch_at = datetime.utcnow().isoformat()
        await self._save_local()

    async def export_opml(self, chat_id: Optional[int] = None) -> str:
        sources = await self.get_all_sources()
        tuples = [(s.name, s.url, s.url) for s in sources if s.type == "rss"]
        return build_opml(tuples)

    async def get_feed_by_id(self, feed_id: str) -> Optional[SourceItem]:
        return await self.get_source(feed_id)

    async def get_subscriptions_for_chat(self, chat_id: int) -> List[SourceItem]:
        ch = await self.get_channel(chat_id)
        if not ch:
            return []
        sources = []
        for sid in ch.selected_sources:
            s = await self.get_source(sid)
            if s:
                sources.append(s)
        return sources

    async def add_subscription(self, chat_id: int, url: str) -> Tuple[SourceItem, bool]:
        """Legacy helper for web_service OPML/import."""
        await self.init()
        sid = f"src_{make_feed_id(url)}"
        source = await self.get_source(sid)
        is_new = False
        if not source:
            source = await self.add_source(name="Imported Feed", url=url)
            is_new = True
        ch = await self.get_channel(chat_id)
        if ch and sid not in ch.selected_sources:
            ch.selected_sources.append(sid)
            await self._save_local()
        return source, is_new

    async def remove_subscription(self, chat_id: int, feed_id: str) -> bool:
        ch = await self.get_channel(chat_id)
        if ch and feed_id in ch.selected_sources:
            ch.selected_sources.remove(feed_id)
            await self._save_local()
            return True
        return False

    async def remove_all_subscriptions(self, chat_id: int) -> int:
        ch = await self.get_channel(chat_id)
        if not ch:
            return 0
        count = len(ch.selected_sources)
        ch.selected_sources.clear()
        await self._save_local()
        return count


# Global singleton instance
rss_storage = RSSStorage()
