"""
HTTP Feed fetcher service for AnjurX | Rss Bot.
Handles async HTTP GET, timeouts, caching headers (ETag, Last-Modified),
content size limit, and automatic feed discovery.
"""
import ssl
import logging
from typing import Optional, Tuple
import aiohttp

from app.services.feed_parser import FeedParser, ParsedFeed

logger = logging.getLogger("anjurxbot.fetcher")

USER_AGENT = "AnjurX-RssBot/2.0 (+https://t.me/AnjurXBot; Telegram RSS Reader)"
MAX_FEED_BYTES = 5 * 1024 * 1024  # 5MB


class FeedFetcher:
    """Async feed fetcher and validator."""

    def __init__(self, timeout_sec: int = 15):
        self.timeout_sec = timeout_sec

    async def fetch_and_parse(
        self,
        url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Tuple[Optional[ParsedFeed], int, Optional[str], Optional[str], bool]:
        """
        Fetches the feed URL, following redirects and autodiscovering feed links if HTML.
        Returns:
            (parsed_feed, status_code, new_etag, new_last_modified, not_modified)
        """
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/xml, "
                "text/xml, application/json, text/html;q=0.9, */*;q=0.8"
            ),
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        timeout = aiohttp.ClientTimeout(total=self.timeout_sec)
        # Create a permissive SSL context for feeds with older certificates
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_ctx)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            try:
                async with session.get(url, headers=headers, allow_redirects=True) as resp:
                    status = resp.status

                    # 304 Not Modified
                    if status == 304:
                        return None, 304, etag, last_modified, True

                    if status != 200:
                        logger.warning(f"Failed to fetch feed {url}, status code: {status}")
                        return None, status, None, None, False

                    new_etag = resp.headers.get("ETag")
                    new_last_modified = resp.headers.get("Last-Modified")

                    # Read body with max size limit
                    content_bytes = await resp.read()
                    if len(content_bytes) > MAX_FEED_BYTES:
                        raise ValueError(f"Feed hajmi belgilangan chegaradan oshib ketdi ({len(content_bytes)} bytes)")

                    # Decode content
                    content_text = ""
                    charset = resp.charset or "utf-8"
                    try:
                        content_text = content_bytes.decode(charset, errors="replace")
                    except Exception:
                        content_text = content_bytes.decode("utf-8", errors="replace")

                    # Parse feed
                    try:
                        feed = FeedParser.parse(content_text, url)
                        return feed, 200, new_etag, new_last_modified, False
                    except ValueError as ve:
                        err_str = str(ve)
                        # Check if autodiscovery redirected to a new feed url
                        if err_str.startswith("AUTODISCOVER:"):
                            discovered_url = err_str.replace("AUTODISCOVER:", "").strip()
                            logger.info(f"Autodiscovered feed URL: {discovered_url} for site: {url}")
                            # Recursive fetch with discovered feed URL
                            return await self.fetch_and_parse(discovered_url)
                        raise ve

            except Exception as e:
                logger.warning(f"Error fetching feed {url}: {e}")
                raise e


# Singleton fetcher instance
feed_fetcher = FeedFetcher()
