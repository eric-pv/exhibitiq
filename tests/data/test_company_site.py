"""Tests for crawler.company_site: what a company's own website says about itself."""
from __future__ import annotations

import pytest

from crawler.adapters import ParseError
from crawler.company_site import CompanySiteAdapter, distribution_statements, parse_feed, parse_profile
from crawler.models import Request, Response
from crawler.source_config import ConfigError
from tests.data.crawl_testkit import make_config

PAGE = b"""<html><head><title>Acme Training | Simulators</title>
<meta name="description" content="Acme builds use-of-force simulators for police &amp; military.">
<meta property="og:site_name" content="Acme Training">
<link rel="canonical" href="/en/">
<link rel="alternate" type="application/rss+xml" href="https://www.acme.example.com/feed/">
<link rel="alternate" type="application/rss+xml" href="https://www.acme.example.com/comments/feed/">
<script>var s = "We are the authorized distributor of Hidden Corp.";</script></head>
<body><p>We are the authorized distributor of Beta Optics in Taiwan.</p>
<p>Products are not authorized for sale outside the US.</p><p>Acme is the exclusive dealer for Gamma Systems.</p>
<p>Find a distributor near you.</p></body></html>"""

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Acme</title>
<item><title>Acme launches VR trainer</title><link>https://www.acme.example.com/news/vr</link><pubDate>Tue, 03 Mar 2026 10:00:00 +0000</pubDate></item>
<item><title>Old VR news</title><link>https://www.acme.example.com/news/old</link><pubDate>Mon, 04 Mar 2024 10:00:00 +0000</pubDate></item>
<item><title>Holiday party</title><link>https://www.acme.example.com/news/party</link><pubDate>Mon, 02 Feb 2026 10:00:00 +0000</pubDate></item>
<item><title>No date</title><link>https://www.acme.example.com/news/x</link></item>
<item><title></title><link>https://www.acme.example.com/news/empty</link></item>
<item><title>Bad link</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom item</title>
<link rel="alternate" href="https://acme.example.com/a"/><updated>2026-02-01T00:00:00Z</updated></entry></feed>"""


def test_profile_reads_only_what_the_site_states() -> None:
    record, feeds = parse_profile(PAGE, "https://www.acme.example.com/")
    assert record["title"] == "Acme Training | Simulators"
    assert record["description"] == "Acme builds use-of-force simulators for police & military."
    assert record["site_name"] == "Acme Training" and record["canonical_url"] == "https://www.acme.example.com/en/"
    assert record["distribution_statements"] == ["We are the authorized distributor of Beta Optics in Taiwan.", "Acme is the exclusive dealer for Gamma Systems."]
    assert feeds == ["https://www.acme.example.com/feed/"]  # comment feeds are not news


def test_og_description_is_the_fallback_and_nothing_is_invented() -> None:
    record, feeds = parse_profile(b'<html><head><meta property="og:description" content="OG text"></head><body>Hello</body></html>', "https://x.example.com/")
    assert record == {"record_type": "profile", "page_url": "https://x.example.com/", "description": "OG text", "distribution_statements": []}
    assert feeds == []


@pytest.mark.parametrize("text, found", [
    ("Official reseller of Delta radios.", True), ("We are an authorized Axon dealer.", True), ("Agents for Epsilon Corp.", True),
    ("Become a distributor.", False), ("As authorised by law.", False), ("Find a dealer near you.", False), ("distributor of ammunition", False),
])
def test_distribution_statements_must_be_explicit(text: str, found: bool) -> None:
    assert bool(distribution_statements(text)) is found


def test_feeds_rss_and_atom() -> None:
    items = parse_feed(FEED, "https://www.acme.example.com/feed/")
    assert items == [
        {"record_type": "news", "feed_url": "https://www.acme.example.com/feed/", "title": "Acme launches VR trainer", "url": "https://www.acme.example.com/news/vr", "published": "2026-03-03"},
        {"record_type": "news", "feed_url": "https://www.acme.example.com/feed/", "title": "Old VR news", "url": "https://www.acme.example.com/news/old", "published": "2024-03-04"},
        {"record_type": "news", "feed_url": "https://www.acme.example.com/feed/", "title": "Holiday party", "url": "https://www.acme.example.com/news/party", "published": "2026-02-02"},
        {"record_type": "news", "feed_url": "https://www.acme.example.com/feed/", "title": "No date", "url": "https://www.acme.example.com/news/x"},
    ]
    assert parse_feed(ATOM, "f")[0] == {"record_type": "news", "feed_url": "f", "title": "Atom item", "url": "https://acme.example.com/a", "published": "2026-02-01"}
    with pytest.raises(ParseError, match="not a readable feed"):
        parse_feed(b"<rss", "f")
    with pytest.raises(ParseError, match="not an RSS or Atom"):
        parse_feed(b"<html/>", "f")


def _config(**options):
    return make_config(name="site", adapter="company-site", start_urls=("https://www.acme.example.com/",), allowed_domains=("acme.example.com",),
                       source_type="exhibitor_website", options=options)


def test_adapter_follows_feeds_unless_told_not_to() -> None:
    adapter = CompanySiteAdapter()
    page = Response("https://www.acme.example.com/", "https://www.acme.example.com/", 200, {}, PAGE, "text/html")
    result = adapter.parse(page, Request(page.url), _config())
    assert [r["record_type"] for r in result.records] == ["profile"] and [f.url for f in result.follow] == ["https://www.acme.example.com/feed/"]
    assert adapter.parse(page, Request(page.url), _config(follow_feeds=False)).follow == []
    feed = Response("https://www.acme.example.com/feed/", "https://www.acme.example.com/feed/", 200, {}, FEED, "application/rss+xml")
    assert len(adapter.parse(feed, Request(feed.url, meta={"kind": "feed"}), _config()).records) == 4
    with pytest.raises(ParseError, match="not an HTML page"):
        adapter.parse(Response("u", "u", 200, {}, b"%PDF", "application/pdf"), Request("u"), _config())


def test_options() -> None:
    with pytest.raises(ConfigError):
        CompanySiteAdapter().validate_options({"surprise": 1})
    with pytest.raises(ConfigError):
        CompanySiteAdapter().validate_options({"follow_feeds": "yes"})
