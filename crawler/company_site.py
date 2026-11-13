"""A company's own website as a source of facts about the company (D2-02 enrichment, Issue #114 item 1A).

Reads only what a site states about itself, in a way that works for any site:

- **Profile** (any HTML page): the page title, the site's own description (``<meta name="description">``, else
  ``og:description``), ``og:site_name``, the canonical URL, and **explicit** distribution statements: sentences that
  say the company is an authorized / official / exclusive distributor, dealer, reseller or agent, or a distributor /
  dealer / reseller / agent *of* or *for* someone. Words like "authorized" alone (often legal text) are not enough.
- **News** (RSS or Atom feeds the page links to with ``<link rel="alternate">``): each item's title, link and
  publication date. The article pages are not fetched.

Nothing is inferred: no statement found means nothing is recorded. Following a feed goes through the runner, so
``allowed_domains``, robots.txt and the rate limit apply as for any page.

Records: ``{"record_type": "profile", "page_url", "title", "description", "site_name", "canonical_url",
"distribution_statements": [...]}`` and ``{"record_type": "news", "feed_url", "title", "url", "published"}``
(``published`` as ``YYYY-MM-DD`` when the feed gives a parseable date).

Options: ``follow_feeds`` (default true).
"""
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import timezone
from email.utils import parsedate_to_datetime
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

from crawler.adapters import AdapterRegistry, ParseError, SourceAdapter, default_registry
from crawler.models import ParseResult, Request, Response
from crawler.source_config import ConfigError, SourceConfig

ADAPTER_NAME = "company-site"
MAX_STATEMENT = 300
MAX_NEWS_ITEMS = 100
_ROLE = r"(?:distributors?|dealers?|resellers?|agents?|representatives?)"
# explicit statements only: "authorized/official/exclusive <role>", or "<role> of/for <Name>" (a capitalised name: a brand, not a product word)
DISTRIBUTION = re.compile(
    rf"\b(?:(?:authori[sz]ed|official|exclusive|sole|certified)\s+(?:\w+\s+)?{_ROLE}|{_ROLE}\s+(?:of|for)\s+(?-i:[A-Z0-9]))",
    re.IGNORECASE,
)
FEED_TYPES = ("application/rss+xml", "application/atom+xml")


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.title = ""
        self.text: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "link":
            self.links.append(a)
        elif tag == "title":
            self._in_title = True
        elif tag in ("script", "style", "noscript", "template"):
            self._skip += 1
        elif tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "td", "section", "article"):
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.text.append(data)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def distribution_statements(text: str) -> list[str]:
    """Sentences of ``text`` that state a distribution role explicitly (deduplicated, in order)."""
    found: list[str] = []
    for block in text.split("\n"):
        for sentence in re.split(r"(?<=[.!?])\s+", _clean(block)):
            if DISTRIBUTION.search(sentence) and len(sentence) >= 15:
                statement = sentence[:MAX_STATEMENT]
                if statement not in found:
                    found.append(statement)
    return found


def parse_profile(content: bytes, page_url: str) -> tuple[dict[str, Any], list[str]]:
    """The profile record of an HTML page and the feed URLs it links to."""
    parser = _Page()
    parser.feed(content.decode("utf-8", errors="replace"))
    parser.close()
    description = _clean(parser.meta.get("description", "")) or _clean(parser.meta.get("og:description", ""))
    record: dict[str, Any] = {"record_type": "profile", "page_url": page_url}
    for key, value in (("title", _clean(parser.title)), ("description", description), ("site_name", _clean(parser.meta.get("og:site_name", "")))):
        if value:
            record[key] = value[:4000]
    canonical = next((link.get("href") for link in parser.links if "canonical" in link.get("rel", "").lower().split()), None)
    if canonical:
        record["canonical_url"] = urljoin(page_url, canonical)
    record["distribution_statements"] = distribution_statements("".join(parser.text))
    feeds = [urljoin(page_url, link["href"]) for link in parser.links
             if "alternate" in link.get("rel", "").lower().split() and link.get("type", "").lower() in FEED_TYPES and link.get("href")
             and "comments" not in link.get("href", "").lower()]
    return record, list(dict.fromkeys(feeds))


def _date(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        try:
            moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc)
    return moment.date().isoformat()


def parse_feed(content: bytes, feed_url: str) -> list[dict[str, Any]]:
    """Items of an RSS 2.0 or Atom feed. Raises ``ParseError`` if the bytes are not one."""
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ParseError(f"not a readable feed: {exc}") from None
    atom = "{http://www.w3.org/2005/Atom}"
    items: list[dict[str, Any]] = []
    if root.tag == "rss" or root.find("channel") is not None:
        for item in root.iter("item"):
            items.append({"title": _clean(item.findtext("title") or ""), "url": (item.findtext("link") or "").strip(), "published": _date(item.findtext("pubDate"))})
    elif root.tag == f"{atom}feed":
        for entry in root.iter(f"{atom}entry"):
            link = next((l.get("href") for l in entry.findall(f"{atom}link") if l.get("rel", "alternate") == "alternate"), None)
            items.append({"title": _clean(entry.findtext(f"{atom}title") or ""), "url": (link or "").strip(),
                          "published": _date(entry.findtext(f"{atom}published") or entry.findtext(f"{atom}updated"))})
    else:
        raise ParseError(f"not an RSS or Atom feed (root element {root.tag!r})")
    records = []
    for item in items[:MAX_NEWS_ITEMS]:
        if item["title"] and re.match(r"^https?://", item["url"]):
            record = {"record_type": "news", "feed_url": feed_url, "title": item["title"][:500], "url": item["url"]}
            if item["published"]:
                record["published"] = item["published"]
            records.append(record)
    return records


class CompanySiteAdapter(SourceAdapter):
    name = ADAPTER_NAME
    version = "1.0.0"

    def validate_options(self, options: Mapping[str, Any]) -> None:
        unknown = sorted(set(options) - {"follow_feeds"})
        if unknown:
            raise ConfigError(f"{ADAPTER_NAME}: unknown option(s): {', '.join(unknown)}")
        if not isinstance(options.get("follow_feeds", True), bool):
            raise ConfigError(f"{ADAPTER_NAME}: follow_feeds must be true or false")

    def parse(self, response: Response, request: Request, config: SourceConfig) -> ParseResult:
        head = response.content[:500].lstrip().lower()
        is_feed = request.meta.get("kind") == "feed" or head.startswith(b"<?xml") and (b"<rss" in head or b"<feed" in head)
        if is_feed:
            return ParseResult(records=parse_feed(response.content, response.final_url))
        if (response.media_type or "text/html") not in ("text/html", "application/xhtml+xml"):
            raise ParseError(f"not an HTML page or a feed ({response.media_type})")
        record, feeds = parse_profile(response.content, response.final_url)
        follow = [Request(url, meta={"kind": "feed"}) for url in feeds] if config.options.get("follow_feeds", True) else []
        return ParseResult(records=[record], follow=follow)


def register_company_site(registry: AdapterRegistry | None = None) -> None:
    target = registry or default_registry
    if ADAPTER_NAME not in target:
        target.register(CompanySiteAdapter)


register_company_site()

__all__ = ["ADAPTER_NAME", "CompanySiteAdapter", "DISTRIBUTION", "distribution_statements", "parse_feed", "parse_profile", "register_company_site"]
