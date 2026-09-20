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
from app.services.recovery_queue import recovery_queue
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
class CategoryItem:
    """Represents a hierarchical category for news sources."""
    id: str  # e.g. "cat_ozbekiston"
    name: str  # Display name e.g. "O‘zbekiston"
    slug: str  # e.g. "ozbekiston"
    description: str = ""
    icon: str = "newspaper"
    active: bool = True
    sort_order: int = 1
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CategoryItem":
        return cls(
            id=str(d.get("id") or ""),
            name=str(d.get("name") or ""),
            slug=str(d.get("slug") or ""),
            description=str(d.get("description") or ""),
            icon=str(d.get("icon") or "newspaper"),
            active=bool(d.get("active", True)),
            sort_order=int(d.get("sort_order", 1)) if str(d.get("sort_order", 1)).isdigit() else 1,
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
        )


@dataclass
class SourceItem:
    """Represents a Super Admin managed news source (RSS/Atom/JSON feed)."""
    id: str  # e.g. "src_kunuz" or "src_<hash>"
    name: str  # Display name e.g. "Kun.uz"
    url: str  # Feed URL
    feed_url: Optional[str] = None
    website_url: Optional[str] = None
    type: str = "rss"  # "rss", "atom", "json"
    category_id: Optional[str] = None
    category: str = "Yangiliklar"
    description: Optional[str] = None
    language: str = "uz"
    country: str = "UZ"
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
        url = str(d.get("url") or d.get("feed_url") or d.get("url_or_id") or d.get("link") or "")
        feed_url = str(d.get("feed_url") or url)
        website_url = d.get("website_url")
        stype = str(d.get("type") or "rss")
        cat_id = d.get("category_id")
        cat = str(d.get("category") or "Yangiliklar")
        desc = d.get("description")
        lang = str(d.get("language") or "uz")
        country = str(d.get("country") or "UZ")
        act = bool(d.get("active", True))
        err_cnt = int(d.get("error_count", 0)) if str(d.get("error_count", 0)).isdigit() else 0
        posts_cnt = int(d.get("posts_count", 0)) if str(d.get("posts_count", 0)).isdigit() else 0

        return cls(
            id=sid,
            name=name,
            url=url,
            feed_url=feed_url,
            website_url=website_url,
            type=stype,
            category_id=cat_id,
            category=cat,
            description=desc,
            language=lang,
            country=country,
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
    schedule_mode: str = "instant"  # "instant" or "custom" / "scheduled"
    schedule_times: List[str] = field(default_factory=lambda: ["09:00", "14:00", "19:00"])
    selected_sources: List[str] = field(default_factory=list)  # list of source_ids
    post_language: str = "uz"  # "uz", "uz_cyrl", "ru", "en", or "auto"
    is_premium_eligible: bool = False  # Set by Super Admin
    premium_enabled: bool = False  # Toggled by eligible channel owner
    footer_type: str = "none"  # "none", "text", "text_link", "inline_button"
    footer_text: Optional[str] = None
    footer_url: Optional[str] = None
    today_delivered_count: int = 0
    today_delivered_slots: List[str] = field(default_factory=list)
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
            self.today_delivered_slots = []
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
            cid = int(d.get("chat_id") or d.get("id") or d.get("_id") or 0)
        except (ValueError, TypeError):
            cid = 0

        owner = 0
        try:
            owner = int(d.get("owner_user_id") or d.get("added_by") or d.get("user_id") or d.get("owner_id") or 0)
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

        raw_slots = d.get("today_delivered_slots", [])
        slots = [str(s) for s in raw_slots if s] if isinstance(raw_slots, list) else []

        mode = str(d.get("schedule_mode") or "instant")
        if mode == "scheduled":
            mode = "custom"

        raw_lang = str(d.get("post_language") or "uz").lower().strip()
        post_lang = raw_lang if raw_lang in ("uz", "uz_cyrl", "ru", "en", "auto") else "uz"

        return cls(
            chat_id=cid,
            title=str(d.get("title") or f"Kanal {cid}"),
            username=d.get("username"),
            owner_user_id=owner,
            active=bool(d.get("active", True)),
            can_post=bool(d.get("can_post", True)),
            daily_limit=limit,
            plan=plan,
            schedule_mode=mode,
            schedule_times=times,
            selected_sources=srcs,
            post_language=post_lang,
            is_premium_eligible=bool(d.get("is_premium_eligible", False)),
            premium_enabled=bool(d.get("premium_enabled", False)),
            footer_type=str(d.get("footer_type") or "none"),
            footer_text=d.get("footer_text"),
            footer_url=d.get("footer_url"),
            today_delivered_count=int(d.get("today_delivered_count", 0)),
            today_delivered_slots=slots,
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


@dataclass
class CentralPoolChannel:
    """Represents a Central Content Channel where editors post raw content."""
    chat_id: int
    title: str
    username: Optional[str] = None
    added_by: int = 8157452043
    active: bool = True
    bot_is_admin: bool = False
    can_post: bool = True
    post_count: int = 0
    last_post_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def id(self) -> str:
        return str(self.chat_id)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = str(self.chat_id)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CentralPoolChannel":
        cid = 0
        try:
            cid = int(d.get("chat_id") or d.get("id") or 0)
        except (ValueError, TypeError):
            cid = 0

        added = 8157452043
        try:
            added = int(d.get("added_by") or 8157452043)
        except (ValueError, TypeError):
            added = 8157452043

        return cls(
            chat_id=cid,
            title=str(d.get("title") or f"Markaziy Kanal {cid}"),
            username=d.get("username"),
            added_by=added,
            active=bool(d.get("active", True)),
            bot_is_admin=bool(d.get("bot_is_admin", False)),
            can_post=bool(d.get("can_post", True)),
            post_count=int(d.get("post_count", 0)),
            last_post_at=d.get("last_post_at"),
            created_at=str(d.get("created_at") or datetime.utcnow().isoformat()),
            updated_at=str(d.get("updated_at") or datetime.utcnow().isoformat()),
        )


@dataclass
class PremiumPostItem:
    """Represents a human-curated premium post collected from a Central Content Channel."""
    id: str  # "prem_{central_chat_id}_{central_message_id}"
    central_chat_id: int
    central_message_id: int
    media_type: str  # text, photo, video, document, audio, voice, animation, media_group
    text: str  # message text or caption
    media_file_id: Optional[str] = None
    media_group_id: Optional[str] = None
    media_items: List[Dict[str, Any]] = field(default_factory=list)  # for albums
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    status: str = "ready"  # draft, ready, active, reserved, delivered, archived
    delivered_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PremiumPostItem":
        pid = str(d.get("id") or f"prem_{d.get('central_chat_id')}_{d.get('central_message_id')}")
        cid = int(d.get("central_chat_id", 0))
        mid = int(d.get("central_message_id", 0))
        raw_items = d.get("media_items", [])
        items = list(raw_items) if isinstance(raw_items, list) else []

        return cls(
            id=pid,
            central_chat_id=cid,
            central_message_id=mid,
            media_type=str(d.get("media_type") or "text"),
            text=str(d.get("text") or ""),
            media_file_id=d.get("media_file_id"),
            media_group_id=d.get("media_group_id"),
            media_items=items,
            author_id=int(d["author_id"]) if d.get("author_id") is not None else None,
            author_name=d.get("author_name"),
            status=str(d.get("status") or "ready"),
            delivered_count=int(d.get("delivered_count", 0)),
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
        self._categories: Dict[str, CategoryItem] = {}
        self._sources: Dict[str, SourceItem] = {}
        self._channels: Dict[int, ChannelItem] = {}
        self._posts: Dict[str, PostItem] = {}
        self._users: Dict[int, UserItem] = {}
        self._central_channels: Dict[int, CentralPoolChannel] = {}
        self._premium_posts: Dict[str, PremiumPostItem] = {}
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
        """Seeds standard categories and verified Uzbek news feeds if none exist."""
        if not self._categories:
            default_cats = [
                CategoryItem(id="cat_ozbekiston", name="O‘zbekiston", slug="ozbekiston", icon="flag", sort_order=1),
                CategoryItem(id="cat_jahon", name="Jahon", slug="jahon", icon="globe", sort_order=2),
                CategoryItem(id="cat_texnologiya", name="Texnologiya va IT", slug="texnologiya", icon="cpu", sort_order=3),
                CategoryItem(id="cat_iqtisodiyot", name="Iqtisodiyot va Moliya", slug="iqtisodiyot", icon="trending-up", sort_order=4),
                CategoryItem(id="cat_sport", name="Sport", slug="sport", icon="trophy", sort_order=5),
            ]
            for c in default_cats:
                self._categories[c.id] = c

        # Do not seed mock/demo sources. Production sources must come from Firestore.
        pass

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
                            f"Loaded local database: {len(self._categories)} categories, "
                            f"{len(self._sources)} sources, {len(self._channels)} channels."
                        )
            except Exception as e:
                logger.error(f"Error loading local database {self.db_path}: {e}")

        # 2. Resilient Firestore Connection & Lightweight Seed if local state empty
        if firebase_service.is_initialized():
            try:
                await firebase_service.check_health()

                # Only load essential categories & sources if local database was completely empty (fresh container)
                if not self._categories:
                    fs_cats = await firebase_service.db.list_documents("source_categories", limit=50)
                    for c in fs_cats:
                        citem = CategoryItem.from_dict(c)
                        if citem.id:
                            self._categories[citem.id] = citem

                if not self._sources:
                    fs_sources = await firebase_service.db.list_documents("sources", limit=100)
                    for s in fs_sources:
                        item = SourceItem.from_dict(s)
                        self._sources[item.id] = item

                if not self._channels:
                    fs_channels = await firebase_service.db.list_documents("channels", limit=100)
                    for c in fs_channels:
                        citem = ChannelItem.from_dict(c)
                        if citem.chat_id != 0:
                            self._channels[citem.chat_id] = citem

                if not self._central_channels:
                    fs_central = await firebase_service.db.list_documents("central_channels", limit=50)
                    for cc in fs_central:
                        ccitem = CentralPoolChannel.from_dict(cc)
                        if ccitem.chat_id != 0:
                            self._central_channels[ccitem.chat_id] = ccitem

                if not self._premium_posts:
                    fs_premium = await firebase_service.db.list_documents("premium_posts", limit=100)
                    for pp in fs_premium:
                        ppitem = PremiumPostItem.from_dict(pp)
                        if ppitem.id:
                            self._premium_posts[ppitem.id] = ppitem

                # Ensure pool limit is strictly <= 500
                if len(self._posts) > 500:
                    await self.cleanup_post_pool(500)

                # Flush recovery queue in background if pending items exist
                asyncio.create_task(firebase_service.flush_recovery_queue(batch_size=20))
                logger.info("Firestore health checked and background recovery worker initiated.")
            except Exception as e:
                logger.warning(f"Firestore startup check deferred: {e}")

    def _normalize_and_load(self, data: Any):
        """Parses and normalizes dictionary content into typed in-memory objects."""
        if not isinstance(data, dict):
            return

        # Categories
        raw_categories = data.get("categories", {})
        if isinstance(raw_categories, dict):
            for k, v in raw_categories.items():
                if isinstance(v, dict):
                    v.setdefault("id", k)
                    cat = CategoryItem.from_dict(v)
                    self._categories[cat.id] = cat

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
                        feed_url=str(v.get("url") or v.get("link") or ""),
                        type="rss",
                        category_id="cat_ozbekiston",
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

        # Central Channels (Content Pool)
        raw_central = data.get("central_channels", {})
        if isinstance(raw_central, dict):
            for k, v in raw_central.items():
                if isinstance(v, dict):
                    try:
                        cid = int(v.get("chat_id") or k)
                        v["chat_id"] = cid
                        cchan = CentralPoolChannel.from_dict(v)
                        if cchan.chat_id != 0:
                            self._central_channels[cchan.chat_id] = cchan
                    except (ValueError, TypeError):
                        pass

        # Premium Posts (Isolated from RSS 500 pool)
        raw_premium = data.get("premium_posts", {})
        if isinstance(raw_premium, dict):
            for k, v in raw_premium.items():
                if isinstance(v, dict):
                    v.setdefault("id", k)
                    ppost = PremiumPostItem.from_dict(v)
                    self._premium_posts[ppost.id] = ppost

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
            "categories": {k: v.to_dict() for k, v in self._categories.items()},
            "sources": {k: v.to_dict() for k, v in self._sources.items()},
            "channels": {str(k): v.to_dict() for k, v in self._channels.items()},
            "posts": {k: v.to_dict() for k, v in self._posts.items()},
            "users": {str(k): v.to_dict() for k, v in self._users.items()},
            "central_channels": {str(k): v.to_dict() for k, v in self._central_channels.items()},
            "premium_posts": {k: v.to_dict() for k, v in self._premium_posts.items()},
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
    # CATEGORY OPERATIONS
    # ==========================================================================

    async def get_all_categories(self, active_only: bool = False) -> List[CategoryItem]:
        await self.init()
        cats = list(self._categories.values())
        if active_only:
            cats = [c for c in cats if c.active]
        cats.sort(key=lambda c: c.sort_order)
        return cats

    async def get_category(self, cat_id: str) -> Optional[CategoryItem]:
        await self.init()
        return self._categories.get(cat_id)

    async def get_sources_by_category(self, cat_id: str, active_only: bool = True) -> List[SourceItem]:
        await self.init()
        cat = self._categories.get(cat_id)
        cat_name = cat.name.lower() if cat else ""
        res = []
        for s in self._sources.values():
            if active_only and not s.active:
                continue
            if s.category_id == cat_id or (cat_name and s.category.lower() == cat_name):
                res.append(s)
        return res

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
        """Returns channels owned by user_id. Prevents IDOR! Super admin also sees unassigned."""
        await self.init()
        today = get_today_tashkent_str()
        results = []
        uid = int(user_id)
        is_super = config.is_super_admin(uid)
        for ch in self._channels.values():
            if ch.owner_user_id == uid or (is_super and ch.owner_user_id == 0):
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
            await firebase_service.save_channel_resilient(cid, channel.to_dict())
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
            await firebase_service.save_channel_resilient(int(chat_id), channel.to_dict())
            return True

    async def update_channel_settings(
        self,
        chat_id: int,
        user_id: int,
        daily_limit: Optional[int] = None,
        schedule_mode: Optional[str] = None,
        schedule_times: Optional[List[str]] = None,
        active: Optional[bool] = None,
        post_language: Optional[str] = None,
        is_super_admin: bool = False,
    ) -> Optional[ChannelItem]:
        """Updates daily limits, schedules, post language, and pause/resume with strict limit bounds."""
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
            if post_language is not None:
                clean_lang = post_language.lower().strip()
                if clean_lang in ("uz", "uz_cyrl", "ru", "en", "auto"):
                    channel.post_language = clean_lang

            channel.updated_at = datetime.utcnow().isoformat()
            await self._save_local()
            await firebase_service.save_channel_resilient(int(chat_id), channel.to_dict())
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

            if firebase_service.is_initialized() and not firebase_service.is_quota_exhausted():
                try:
                    await firebase_service.db.delete_document("channels", str(chat_id))
                except Exception:
                    pass
            return True

    # ==========================================================================
    # USER & CONTRACT PLAN OPERATIONS
    # ==========================================================================

    async def get_user(self, user_id: int) -> Optional[UserItem]:
        await self.init()
        async with self._lock:
            return self._users.get(int(user_id))

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
            await firebase_service.save_user_resilient(uid, user.to_dict())
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
                    await firebase_service.save_channel_resilient(ch.chat_id, ch.to_dict())

            await self._save_local()
            await firebase_service.save_user_resilient(uid, user.to_dict())
            return user

    # ==========================================================================
    # POST POOL (MAXIMUM 500 POSTS) OPERATIONS
    # ==========================================================================

    async def save_post_to_pool(self, post: PostItem) -> bool:
        """
        Saves a post into the Post Pool (Max 500 items).
        If post already exists by post_id or duplicate source+external_post_id: SKIPS.
        If pool exceeds 500, immediately runs targeted cleanup prioritizing newest posts.
        """
        await self.init()
        async with self._lock:
            if post.post_id in self._posts:
                return False  # Already in pool

            # Duplicate check across all active pool items
            for p in self._posts.values():
                if p.source_id == post.source_id and p.external_post_id == post.external_post_id:
                    return False

            self._posts[post.post_id] = post
            await self._save_local()

            # Resilient Cloud Save with SQLite recovery fallback
            await firebase_service.save_post_resilient(post.to_dict())

        # Enforce pool limit of 500
        if len(self._posts) > 500:
            await self.cleanup_post_pool(500)

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
            if p.status in ("queued", "translation_pending"):
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

            # Resilient Cloud Save with SQLite recovery fallback
            await firebase_service.save_post_resilient(post.to_dict())
            return True

    async def cleanup_post_pool(self, max_limit: int = 500) -> int:
        """
        Maintains Post Pool at <= max_limit (500) items.
        Strict cleanup order:
        1. Expired posts
        2. Oldest delivered posts (if > 500)
        3. Oldest queued / assigned / failed posts (if still > 500)
        4. Newest posts prioritized and preserved!
        Batch deletes from Firestore and local pool.
        """
        await self.init()
        async with self._lock:
            total = len(self._posts)
            now = datetime.utcnow()
            to_delete_ids: List[str] = []
            remaining: List[PostItem] = []

            # Step 1: Expired posts first
            for pid, post in list(self._posts.items()):
                if post.status == "expired" or post.is_expired(now):
                    to_delete_ids.append(pid)
                else:
                    remaining.append(post)

            # Step 2: If still > max_limit, delete oldest delivered
            if len(remaining) > max_limit:
                delivered = [p for p in remaining if p.status == "delivered"]
                delivered.sort(key=lambda p: p.delivered_at or p.fetched_at or "")
                excess = len(remaining) - max_limit
                del_to_remove = delivered[:excess]
                del_ids = {p.post_id for p in del_to_remove}
                to_delete_ids.extend(del_ids)
                remaining = [p for p in remaining if p.post_id not in del_ids]

            # Step 3: If still > max_limit, delete oldest queued / assigned / failed
            if len(remaining) > max_limit:
                remaining.sort(key=lambda p: p.fetched_at or "")
                excess = len(remaining) - max_limit
                oldest_to_remove = remaining[:excess]
                old_ids = {p.post_id for p in oldest_to_remove}
                to_delete_ids.extend(old_ids)
                remaining = remaining[excess:]

            if to_delete_ids:
                for pid in to_delete_ids:
                    self._posts.pop(pid, None)

                await self._save_local()

                # Controlled deletion from Firestore: NEVER run huge delete storms
                # If Firestore is quota-exhausted, keep local pool clean and defer cloud deletes
                if firebase_service.is_initialized() and not firebase_service.is_quota_exhausted():
                    try:
                        # Process at most 25 deletes per cleanup cycle
                        for pid in to_delete_ids[:25]:
                            await firebase_service.db.delete_document("posts", pid)
                            await asyncio.sleep(0.04)
                    except Exception as e:
                        logger.debug(f"Firestore batch post delete notice: {e}")

                logger.info(f"[Post Pool Cleanup] Cleaned up {len(to_delete_ids)} posts. Pool size now: {len(self._posts)} <= {max_limit}")
            return len(to_delete_ids)

    async def cleanup_expired_posts(self) -> int:
        """Enforces the 500-post pool limit and cleans expired/excess posts."""
        return await self.cleanup_post_pool(500)

    # ==========================================================================
    # DUPLICATE PROTECTION & DELIVERY TRACKING
    # ==========================================================================

    def make_delivery_signature(self, source_id: str, external_post_id: str, channel_id: int) -> str:
        return f"{source_id}:{external_post_id}:{channel_id}"

    async def is_post_delivered(self, source_id: str, external_post_id: str, channel_id: int) -> bool:
        """Guarantees strict duplicate prevention per (source, external_id, channel)."""
        await self.init()
        sig = self.make_delivery_signature(source_id, external_post_id, channel_id)
        if sig in self._delivered_signatures:
            return True
        post_uid = f"post_{source_id}_{external_post_id}"
        if recovery_queue.is_delivery_already_sent(post_uid, channel_id):
            return True
        return False

    async def record_delivery(
        self,
        source_id: str,
        external_post_id: str,
        channel_id: int,
        title: str,
        url: str,
        telegram_message_id: Optional[int] = None,
        target_language: Optional[str] = None,
        post_id: Optional[str] = None,
    ):
        """Records delivery to prevent duplication and tracks statistics."""
        await self.init()
        async with self._lock:
            sig = self.make_delivery_signature(source_id, external_post_id, channel_id)
            self._delivered_signatures.add(sig)
            self._posts_delivered += 1

            post_uid = post_id or f"post_{source_id}_{external_post_id}"

            # Register delivery intent and confirm Telegram message sent locally
            intent_id, _ = recovery_queue.register_delivery_intent(post_uid, int(channel_id))
            recovery_queue.mark_delivery_intent_sent(intent_id, telegram_message_id)

            record = {
                "signature": sig,
                "post_id": post_uid,
                "source_id": source_id,
                "external_post_id": external_post_id,
                "channel_id": channel_id,
                "title": title,
                "url": url,
                "telegram_message_id": telegram_message_id,
                "target_language": target_language or "auto",
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
                await firebase_service.save_channel_resilient(ch.chat_id, ch.to_dict())

            await self._save_local()

            # Resilient Cloud Save with SQLite recovery fallback
            await firebase_service.record_delivery_resilient(record)
            await firebase_service.increment_stat_resilient("posts_delivered", 1)

    # ==========================================================================
    # STATS & MONITORING
    # ==========================================================================

    async def get_stats(self) -> Dict[str, Any]:
        await self.init()
        active_channels = sum(1 for c in self._channels.values() if c.active and c.can_post)
        active_sources = sum(1 for s in self._sources.values() if s.active)

        queued_posts = sum(1 for p in self._posts.values() if p.status == "queued")
        assigned_posts = sum(1 for p in self._posts.values() if p.status == "assigned")
        delivered_posts = sum(1 for p in self._posts.values() if p.status == "delivered")
        expired_posts = sum(1 for p in self._posts.values() if p.status == "expired")
        failed_posts = sum(1 for p in self._posts.values() if p.status == "failed")

        diag = firebase_service.get_diagnostics()

        return {
            "total_sources": len(self._sources),
            "active_sources": active_sources,
            "total_destinations": len(self._channels),
            "active_channels": active_channels,
            "total_users": len(self._users),
            "posts_delivered": self._posts_delivered,
            "total_posts": len(self._posts),
            "queued_posts": queued_posts,
            "assigned_posts": assigned_posts,
            "delivered_posts": delivered_posts,
            "expired_posts": expired_posts,
            "failed_posts": failed_posts,
            "pool_queued": queued_posts,
            "pool_assigned": assigned_posts,
            "pool_delivered": delivered_posts,
            "pool_expired": expired_posts,
            "pool_failed": failed_posts,
            "total_in_pool": len(self._posts),
            "pool_max": 500,
            "firestore_health": diag,
            "is_stale": diag.get("is_stale", False),
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

    # ==========================================================================
    # CENTRAL CONTENT POOL & PREMIUM POST OPERATIONS
    # ==========================================================================

    async def get_all_central_channels(self, active_only: bool = False) -> List[CentralPoolChannel]:
        await self.init()
        async with self._lock:
            if active_only:
                return [c for c in self._central_channels.values() if c.active]
            return list(self._central_channels.values())

    async def get_central_channel(self, chat_id: int) -> Optional[CentralPoolChannel]:
        await self.init()
        async with self._lock:
            return self._central_channels.get(chat_id)

    async def save_central_channel(self, channel: CentralPoolChannel):
        await self.init()
        async with self._lock:
            self._central_channels[channel.chat_id] = channel
            await self._save_local()
            # Also save resiliently to Firestore
            await firebase_service.save_entity_resilient(
                "central_channels",
                str(channel.chat_id),
                channel.to_dict()
            )

    async def delete_central_channel(self, chat_id: int) -> bool:
        await self.init()
        async with self._lock:
            if chat_id in self._central_channels:
                del self._central_channels[chat_id]
                await self._save_local()
                return True
            return False

    async def get_all_premium_posts(self, status: Optional[str] = None) -> List[PremiumPostItem]:
        await self.init()
        async with self._lock:
            posts = list(self._premium_posts.values())
            if status:
                posts = [p for p in posts if p.status == status]
            return sorted(posts, key=lambda p: p.created_at, reverse=True)

    async def get_ready_premium_posts(self) -> List[PremiumPostItem]:
        """Returns premium posts that are active/ready for delivery."""
        await self.init()
        async with self._lock:
            posts = [p for p in self._premium_posts.values() if p.status in ("ready", "active", "delivered")]
            return sorted(posts, key=lambda p: p.created_at, reverse=False)

    async def get_premium_post(self, post_id: str) -> Optional[PremiumPostItem]:
        await self.init()
        async with self._lock:
            return self._premium_posts.get(post_id)

    async def save_premium_post(self, post: PremiumPostItem):
        await self.init()
        async with self._lock:
            self._premium_posts[post.id] = post
            # Update central channel's post count
            if post.central_chat_id in self._central_channels:
                ch = self._central_channels[post.central_chat_id]
                ch.post_count = sum(1 for p in self._premium_posts.values() if p.central_chat_id == post.central_chat_id)
                ch.last_post_at = post.created_at
                ch.updated_at = datetime.utcnow().isoformat()
            await self._save_local()
            # Also save to Firestore
            await firebase_service.save_entity_resilient(
                "premium_posts",
                post.id,
                post.to_dict()
            )

    async def is_premium_post_delivered(self, post_id: str, channel_id: int) -> bool:
        sig = f"prem:{post_id}:{channel_id}"
        async with self._lock:
            return sig in self._delivered_signatures

    async def record_premium_delivery(
        self,
        post: PremiumPostItem,
        channel: ChannelItem,
        telegram_message_id: Optional[int] = None,
        target_language: str = "uz"
    ):
        await self.init()
        sig = f"prem:{post.id}:{channel.chat_id}"
        now_iso = datetime.utcnow().isoformat()
        async with self._lock:
            self._delivered_signatures.add(sig)
            self._posts_delivered += 1
            post.delivered_count += 1
            if post.status == "ready":
                post.status = "delivered"
            post.updated_at = now_iso

            channel.today_delivered_count += 1
            channel.total_delivered_count += 1
            channel.last_delivered_at = now_iso
            channel.updated_at = now_iso

            record = {
                "signature": sig,
                "source_id": f"central_{post.central_chat_id}",
                "external_post_id": str(post.central_message_id),
                "post_id": post.id,
                "channel_id": channel.chat_id,
                "channel_title": channel.title,
                "title": post.text[:80] if post.text else f"Premium Post #{post.central_message_id}",
                "url": f"https://t.me/c/{str(post.central_chat_id).replace('-100', '')}/{post.central_message_id}",
                "telegram_message_id": telegram_message_id,
                "delivered_at": now_iso,
                "target_language": target_language,
            }
            self._recent_posts.append(record)
            if len(self._recent_posts) > 100:
                self._recent_posts = self._recent_posts[-100:]

            await self._save_local()
            await firebase_service.record_delivery_resilient(record)
            await firebase_service.increment_stat_resilient("posts_delivered", 1)


# Global singleton instance
rss_storage = RSSStorage()
