"""
RSS, Atom, and JSON Feed parser for AnjurX | Rss Bot.
Supports RSS 0.9x, 1.0 (RDF), 2.0, Atom 0.3/1.0, and JSON Feed 1.0/1.1.
Also provides HTML feed autodiscovery and OPML export/import.
"""
import re
import json
import hashlib
import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import urljoin, urlparse


@dataclass
class ParsedItem:
    id: str
    title: str
    link: str
    summary: str
    author: Optional[str] = None
    published: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    media_type: Optional[str] = None

    @property
    def guid(self) -> str:
        return self.id

    @property
    def description(self) -> str:
        return self.summary

    def get_hash(self) -> str:
        """Returns stable unique hash for this item."""
        basis = self.id or self.link or f"{self.title}_{self.published}"
        return hashlib.sha256(basis.encode("utf-8", errors="ignore")).hexdigest()[:16]


@dataclass
class ParsedFeed:
    title: str
    link: str
    feed_url: str
    description: str = ""
    items: List[ParsedItem] = field(default_factory=list)


def clean_html(raw_html: str) -> str:
    """Strips HTML tags and unescapes entities to produce clean excerpt text."""
    if not raw_html:
        return ""
    # Strip script and style tags
    text = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", "", raw_html, flags=re.IGNORECASE)
    # Convert <br> and <p> to spaces or newlines
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    # Strip all remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Collapse multiple blank lines
    text = re.sub(r"\n\s*\n", "\n", text).strip()
    return text


def truncate_text(text: str, max_length: int = 300) -> str:
    """Truncates text safely with an ellipsis."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rstrip()
    last_space = truncated.rfind(" ")
    if last_space > max_length // 2:
        truncated = truncated[:last_space]
    return truncated + "..."


def escape_tg_html(text: str) -> str:
    """Escapes string for safe inclusion in Telegram HTML messages."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class FeedParser:
    """Universal feed parser and autodiscovery engine."""

    @staticmethod
    def autodiscover_feed_url(html_content: str, base_url: str) -> Optional[str]:
        """
        Extracts <link rel="alternate" type="application/rss+xml|atom+xml" href="...">
        from an HTML document if given a regular website URL.
        """
        link_regex = re.compile(
            r'<link\s+[^>]*?rel=["\']alternate["\'][^>]*?>',
            re.IGNORECASE,
        )
        type_regex = re.compile(
            r'type=["\'](application/(rss\+xml|atom\+xml|json)|text/xml)["\']',
            re.IGNORECASE,
        )
        href_regex = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)

        for match in link_regex.finditer(html_content):
            tag = match.group(0)
            if type_regex.search(tag):
                href_match = href_regex.search(tag)
                if href_match:
                    found_href = href_match.group(1).strip()
                    return urljoin(base_url, found_href)
        return None

    @classmethod
    def parse(cls, content: str, feed_url: str) -> ParsedFeed:
        """
        Parses feed content (RSS, Atom, RDF, or JSON Feed) and returns a ParsedFeed object.
        """
        content_stripped = content.strip()
        if not content_stripped:
            raise ValueError("Bo'sh kontent: Feed ma'lumotlari topilmadi.")

        # Check if JSON Feed
        if content_stripped.startswith("{"):
            try:
                data = json.loads(content_stripped)
                if "items" in data:
                    return cls._parse_json_feed(data, feed_url)
            except Exception:
                pass

        # Try XML Parsing (RSS 2.0, 1.0, Atom 1.0, etc.)
        try:
            # Strip XML declaration if present to avoid encoding mismatches in string parsing
            cleaned_xml = re.sub(r"^<\?xml[^>]*\?>", "", content_stripped).strip()
            root = ET.fromstring(cleaned_xml)
        except ET.ParseError as e:
            # Check if this is an HTML webpage containing feed link
            discovered = cls.autodiscover_feed_url(content_stripped, feed_url)
            if discovered and discovered != feed_url:
                raise ValueError(f"AUTODISCOVER:{discovered}")
            raise ValueError(f"Feed XML formatida xatolik: {e}")

        tag_name = root.tag.lower()

        # Atom feed (<feed> with or without namespace)
        if tag_name.endswith("feed"):
            return cls._parse_atom(root, feed_url)

        # RSS 2.0 or 0.9x (<rss><channel>...</channel></rss>)
        if tag_name.endswith("rss"):
            channel = root.find("channel")
            if channel is not None:
                return cls._parse_rss2(channel, feed_url)

        # RDF / RSS 1.0 (<rdf:RDF>...</rdf:RDF>)
        if tag_name.endswith("rdf"):
            return cls._parse_rdf(root, feed_url)

        # Direct <channel> element
        if tag_name.endswith("channel"):
            return cls._parse_rss2(root, feed_url)

        raise ValueError("Noma'lum feed formati: RSS yoki Atom standarti topilmadi.")

    @classmethod
    def _parse_rss2(cls, channel: ET.Element, feed_url: str) -> ParsedFeed:
        title = channel.findtext("title", default="Nomsiz RSS").strip()
        link = channel.findtext("link", default=feed_url).strip()
        description = clean_html(channel.findtext("description", default=""))

        items: List[ParsedItem] = []
        for elem in channel.findall("item"):
            item_title = elem.findtext("title", default="Nomsiz maqola").strip()
            item_link = elem.findtext("link", default="").strip()
            guid = elem.findtext("guid", default=item_link).strip()
            desc = elem.findtext("description", default="")
            encoded_content = elem.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or elem.findtext("content") or ""
            pub_date = elem.findtext("pubDate", default="")
            author = elem.findtext("author") or elem.findtext("{http://purl.org/dc/elements/1.1/}creator")

            image_url = None
            media_type = None
            enclosure = elem.find("enclosure")
            if enclosure is not None and enclosure.attrib.get("url"):
                image_url = enclosure.attrib.get("url")
                media_type = enclosure.attrib.get("type", "image/jpeg")
            else:
                for sub in elem:
                    if "content" in sub.tag.lower() or "thumbnail" in sub.tag.lower():
                        url_attr = sub.attrib.get("url")
                        if url_attr:
                            image_url = url_attr
                            media_type = sub.attrib.get("type", "image/jpeg")
                            break

            items.append(
                ParsedItem(
                    id=guid or item_link,
                    title=clean_html(item_title),
                    link=item_link,
                    summary=clean_html(desc),
                    author=author.strip() if author else None,
                    published=pub_date.strip() if pub_date else None,
                    content=clean_html(encoded_content) if encoded_content else clean_html(desc),
                    image_url=image_url,
                    media_type=media_type,
                )
            )

        return ParsedFeed(
            title=clean_html(title) or "Nomsiz RSS",
            link=link,
            feed_url=feed_url,
            description=description,
            items=items,
        )

    @classmethod
    def _parse_atom(cls, root: ET.Element, feed_url: str) -> ParsedFeed:
        def find_text_any_ns(elem: ET.Element, tag: str) -> str:
            for child in elem:
                if child.tag.split("}")[-1].lower() == tag.lower():
                    return child.text or ""
            return ""

        def find_link_any_ns(elem: ET.Element) -> str:
            for child in elem:
                if child.tag.split("}")[-1].lower() == "link":
                    href = child.attrib.get("href", "")
                    rel = child.attrib.get("rel", "alternate")
                    if rel in ("alternate", "") and href:
                        return href
            return ""

        feed_title = find_text_any_ns(root, "title").strip() or "Nomsiz Atom"
        feed_link = find_link_any_ns(root) or feed_url
        feed_subtitle = clean_html(find_text_any_ns(root, "subtitle"))

        items: List[ParsedItem] = []
        for child in root:
            if child.tag.split("}")[-1].lower() == "entry":
                item_title = find_text_any_ns(child, "title").strip() or "Nomsiz maqola"
                item_link = find_link_any_ns(child)
                item_id = find_text_any_ns(child, "id").strip() or item_link
                published = find_text_any_ns(child, "updated") or find_text_any_ns(child, "published")
                summary = find_text_any_ns(child, "summary") or find_text_any_ns(child, "content")

                author = None
                for sub in child:
                    if sub.tag.split("}")[-1].lower() == "author":
                        author = find_text_any_ns(sub, "name").strip()
                        break

                content_raw = find_text_any_ns(child, "content") or summary
                image_url = None
                media_type = None
                for sub in child:
                    if sub.tag.split("}")[-1].lower() == "link":
                        rel = sub.attrib.get("rel", "")
                        if "enclosure" in rel or "image" in sub.attrib.get("type", ""):
                            image_url = sub.attrib.get("href")
                            media_type = sub.attrib.get("type", "image/jpeg")
                            break

                items.append(
                    ParsedItem(
                        id=item_id,
                        title=clean_html(item_title),
                        link=item_link,
                        summary=clean_html(summary),
                        author=author,
                        published=published.strip() if published else None,
                        content=clean_html(content_raw),
                        image_url=image_url,
                        media_type=media_type,
                    )
                )

        return ParsedFeed(
            title=clean_html(feed_title),
            link=feed_link,
            feed_url=feed_url,
            description=feed_subtitle,
            items=items,
        )

    @classmethod
    def _parse_rdf(cls, root: ET.Element, feed_url: str) -> ParsedFeed:
        channel_title = "Nomsiz RSS 1.0"
        channel_link = feed_url
        channel_desc = ""

        for child in root:
            if child.tag.split("}")[-1].lower() == "channel":
                for sub in child:
                    tag = sub.tag.split("}")[-1].lower()
                    if tag == "title":
                        channel_title = sub.text or channel_title
                    elif tag == "link":
                        channel_link = sub.text or channel_link
                    elif tag == "description":
                        channel_desc = sub.text or channel_desc

        items: List[ParsedItem] = []
        for child in root:
            if child.tag.split("}")[-1].lower() == "item":
                item_title = ""
                item_link = child.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
                item_desc = ""
                item_date = None
                item_creator = None

                for sub in child:
                    tag = sub.tag.split("}")[-1].lower()
                    if tag == "title":
                        item_title = sub.text or ""
                    elif tag == "link":
                        item_link = sub.text or item_link
                    elif tag == "description":
                        item_desc = sub.text or ""
                    elif tag == "date":
                        item_date = sub.text
                    elif tag == "creator":
                        item_creator = sub.text

                items.append(
                    ParsedItem(
                        id=item_link,
                        title=clean_html(item_title) or "Nomsiz",
                        link=item_link,
                        summary=clean_html(item_desc),
                        author=item_creator,
                        published=item_date,
                    )
                )

        return ParsedFeed(
            title=clean_html(channel_title),
            link=channel_link,
            feed_url=feed_url,
            description=clean_html(channel_desc),
            items=items,
        )

    @classmethod
    def _parse_json_feed(cls, data: dict, feed_url: str) -> ParsedFeed:
        title = data.get("title", "JSON Feed")
        link = data.get("home_page_url", feed_url)
        description = clean_html(data.get("description", ""))

        items: List[ParsedItem] = []
        for it in data.get("items", []):
            item_id = str(it.get("id", ""))
            item_title = it.get("title", "Nomsiz maqola")
            item_url = it.get("url", "")
            summary = it.get("summary", "") or it.get("content_text", "")
            pub = it.get("date_published", "")
            author = None
            if "authors" in it and isinstance(it["authors"], list) and it["authors"]:
                author = it["authors"][0].get("name")
            elif "author" in it and isinstance(it["author"], dict):
                author = it["author"].get("name")

            content_html = it.get("content_html") or it.get("content_text") or summary
            img = it.get("image") or it.get("banner_image")

            items.append(
                ParsedItem(
                    id=item_id or item_url,
                    title=clean_html(item_title),
                    link=item_url,
                    summary=clean_html(summary),
                    author=author,
                    published=pub,
                    content=clean_html(content_html),
                    image_url=img,
                    media_type="image/jpeg" if img else None,
                )
            )

        return ParsedFeed(
            title=clean_html(title),
            link=link,
            feed_url=feed_url,
            description=description,
            items=items,
        )


def build_opml(feeds: List[dict], title: str = "AnjurX | Rss Bot Subscriptions") -> str:
    """Generates standard OPML 2.0 XML string for subscription export."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<opml version="2.0">',
        "  <head>",
        f"    <title>{escape_tg_html(title)}</title>",
        "  </head>",
        "  <body>",
    ]
    for feed in feeds:
        feed_title = html.escape(feed.get("title", "RSS Feed"), quote=True)
        xml_url = html.escape(feed.get("url", ""), quote=True)
        html_url = html.escape(feed.get("link", xml_url), quote=True)
        lines.append(
            f'    <outline type="rss" text="{feed_title}" title="{feed_title}" xmlUrl="{xml_url}" htmlUrl="{html_url}"/>'
        )
    lines.append("  </body>")
    lines.append("</opml>")
    return "\n".join(lines)


def parse_opml(opml_xml: str) -> List[Tuple[str, str]]:
    """
    Parses OPML XML content and extracts list of (url, title).
    """
    results: List[Tuple[str, str]] = []
    try:
        root = ET.fromstring(opml_xml)
        for outline in root.iter("outline"):
            xml_url = outline.attrib.get("xmlUrl") or outline.attrib.get("url")
            title = outline.attrib.get("title") or outline.attrib.get("text") or "RSS Feed"
            if xml_url and xml_url.startswith(("http://", "https://")):
                results.append((xml_url.strip(), title.strip()))
    except Exception:
        pass
    return results
