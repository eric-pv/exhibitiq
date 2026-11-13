"""Tests for crawler.fetch and crawler.robots (D2-01): safety rules, status classification, robots.txt."""
from __future__ import annotations

import socket

import pytest

from crawler.errors import ErrorCode
from crawler.fetch import FetchError, UrllibFetcher, classify_http_status, host_in_domains
from crawler.models import Request
from crawler.robots import rules_from_failure, rules_from_text
from tests.data.crawl_testkit import LocalSite

KW = dict(timeout=5.0, user_agent="ExhibitIQ-test", max_bytes=1024)


def local_fetcher() -> UrllibFetcher:
    return UrllibFetcher(allow_private_networks=True, proxies={})


def fetch(site: LocalSite, path: str, *, fetcher=None, headers=None, domains=("127.0.0.1",), **kw):
    options = {**KW, **kw}
    return (fetcher or local_fetcher()).fetch(Request(site.base + path, headers=headers or {}), allowed_domains=domains, **options)


# --- classification -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, ErrorCode.ACCESS_BLOCKED, False), (403, ErrorCode.ACCESS_BLOCKED, False), (429, ErrorCode.ACCESS_BLOCKED, False),
        (404, ErrorCode.HTTP_ERROR, False), (410, ErrorCode.HTTP_ERROR, False), (400, ErrorCode.HTTP_ERROR, False),
        (408, ErrorCode.TIMEOUT, True), (500, ErrorCode.HTTP_ERROR, True), (503, ErrorCode.HTTP_ERROR, True),
    ],
)
def test_status_classification(status, code, retryable):
    assert classify_http_status(status) == (code, retryable)


@pytest.mark.parametrize(
    "host,domains,expected",
    [
        ("example.com", ["example.com"], True), ("www.example.com", ["example.com"], True), ("EXAMPLE.com.", ["example.com"], True),
        ("evilexample.com", ["example.com"], False), ("example.com.evil.org", ["example.com"], False),
        ("example.org", ["example.com"], False), (None, ["example.com"], False), ("", ["example.com"], False),
    ],
)
def test_host_in_domains(host, domains, expected):
    assert host_in_domains(host, domains) is expected


# --- real requests against a local server -------------------------------------------------


def test_fetch_returns_body_headers_and_media_type():
    with LocalSite({"/a": (200, {"Content-Type": "Text/HTML; charset=utf-8"}, b"<p>hi</p>")}) as site:
        response = fetch(site, "/a")
    assert response.status == 200 and response.content == b"<p>hi</p>"
    assert response.media_type == "text/html"
    assert response.headers["content-type"].startswith("Text/HTML")
    assert response.final_url == response.url


def test_user_agent_and_identity_encoding_are_sent_and_no_credentials():
    with LocalSite({"/a": (200, {}, b"x")}) as site:
        fetch(site, "/a")
    sent = site.requests[0]["headers"]
    assert sent["user-agent"] == "ExhibitIQ-test"
    assert sent["accept-encoding"] == "identity"
    assert not {"authorization", "cookie", "proxy-authorization"} & set(sent)


@pytest.mark.parametrize("header", ["Authorization", "cookie", "Proxy-Authorization"])
def test_credential_headers_are_refused_before_any_request(header):
    with LocalSite({"/a": (200, {}, b"x")}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/a", headers={header: "secret"})
    assert caught.value.code is ErrorCode.CONFIG_INVALID and not caught.value.retryable
    assert site.requests == []
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("status,code,retryable", [(403, ErrorCode.ACCESS_BLOCKED, False), (429, ErrorCode.ACCESS_BLOCKED, False), (404, ErrorCode.HTTP_ERROR, False), (503, ErrorCode.HTTP_ERROR, True)])
def test_http_errors_become_fetch_errors(status, code, retryable):
    with LocalSite({"/a": (status, {}, b"no")}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/a")
    assert (caught.value.code, caught.value.retryable, caught.value.http_status) == (code, retryable, status)


def test_non_200_success_statuses_are_returned():
    with LocalSite({"/a": (204, {}, b"")}) as site:
        assert fetch(site, "/a").status == 204


def test_body_larger_than_max_bytes_is_refused_not_truncated():
    with LocalSite({"/big": (200, {}, b"x" * 2000), "/ok": (200, {}, b"x" * 1024)}) as site:
        assert len(fetch(site, "/ok").content) == 1024  # exactly at the limit is fine
        with pytest.raises(FetchError) as caught:
            fetch(site, "/big")
    assert caught.value.code is ErrorCode.HTTP_ERROR and not caught.value.retryable
    assert "max_bytes" in caught.value.message


def test_timeout_is_classified_and_retryable():
    with LocalSite({"/slow": (200, {}, None)}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/slow", timeout=0.3)
    assert caught.value.code is ErrorCode.TIMEOUT and caught.value.retryable


def test_connection_refused_is_a_network_error():
    with LocalSite({}) as site:
        base = site.base
    with pytest.raises(FetchError) as caught:  # the server is gone now
        local_fetcher().fetch(Request(base + "/x"), allowed_domains=("127.0.0.1",), **KW)
    assert caught.value.code is ErrorCode.NETWORK_ERROR and caught.value.retryable


# --- scope, redirects, SSRF ---------------------------------------------------------------


def test_redirect_inside_scope_is_followed_and_final_url_reported():
    with LocalSite({"/old": (302, {"Location": "/new"}, b""), "/new": (200, {}, b"moved")}) as site:
        response = fetch(site, "/old")
    assert response.content == b"moved"
    assert response.url.endswith("/old") and response.final_url.endswith("/new")


def test_redirect_out_of_scope_is_refused_and_target_never_requested():
    with LocalSite({"/out": (302, {"Location": "http://localhost.invalid/x"}, b"")}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/out")
    assert caught.value.code is ErrorCode.CONFIG_INVALID and "allowed_domains" in caught.value.message


def test_redirect_to_non_http_scheme_is_refused():
    with LocalSite({"/f": (302, {"Location": "file:///etc/passwd"}, b"")}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/f")
    assert caught.value.code is ErrorCode.CONFIG_INVALID


def test_redirect_loop_is_an_error_not_a_hang():
    with LocalSite({"/a": (302, {"Location": "/b"}, b""), "/b": (302, {"Location": "/a"}, b"")}) as site:
        with pytest.raises(FetchError) as caught:
            fetch(site, "/a")
    assert caught.value.code is ErrorCode.CONFIG_INVALID and not caught.value.retryable


def test_redirect_chain_longer_than_the_limit_is_refused_but_a_short_one_is_followed():
    routes = {f"/h{i}": (302, {"Location": f"/h{i + 1}"}, b"") for i in range(8)}
    routes["/h8"] = (200, {}, b"end")
    routes.update({"/s0": (302, {"Location": "/s1"}, b""), "/s1": (302, {"Location": "/s2"}, b""), "/s2": (200, {}, b"short")})
    with LocalSite(routes) as site:
        assert fetch(site, "/s0").content == b"short"
        with pytest.raises(FetchError) as caught:
            fetch(site, "/h0")
    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert len([r for r in site.requests if r["path"].startswith("/h")]) <= 6


@pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)", "http:///nohost", "https://user:pw@example.com/x"])
def test_bad_urls_are_refused_without_network(url):
    resolver_calls = []
    fetcher = UrllibFetcher(proxies={}, resolver=lambda *a, **k: resolver_calls.append(a) or [])
    with pytest.raises(FetchError) as caught:
        fetcher.fetch(Request(url), allowed_domains=("example.com",), **KW)
    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert resolver_calls == []
    assert "pw" not in str(caught.value)


def test_host_outside_allowed_domains_is_refused():
    with pytest.raises(FetchError) as caught:
        UrllibFetcher(proxies={}).fetch(Request("https://other.org/x"), allowed_domains=("example.com",), **KW)
    assert caught.value.code is ErrorCode.CONFIG_INVALID


def resolver_for(*addresses: str):
    def resolve(host, port, **kw):
        return [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]
    return resolve


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.16.0.1", "169.254.169.254", "0.0.0.0", "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "::ffff:169.254.169.254", "100.64.0.1"])
def test_non_public_addresses_are_refused_by_default(address):
    fetcher = UrllibFetcher(proxies={}, resolver=resolver_for(address))
    with pytest.raises(FetchError) as caught:
        fetcher.fetch(Request("http://www.example.com/x"), allowed_domains=("example.com",), **KW)
    assert caught.value.code is ErrorCode.CONFIG_INVALID and not caught.value.retryable
    assert "non-public" in caught.value.message


def test_one_private_address_among_public_ones_refuses():
    fetcher = UrllibFetcher(proxies={}, resolver=resolver_for("93.184.216.34", "10.0.0.1"))
    with pytest.raises(FetchError):
        fetcher.fetch(Request("http://www.example.com/x"), allowed_domains=("example.com",), **KW)


def test_loopback_server_is_refused_by_default():
    with LocalSite({"/a": (200, {}, b"x")}) as site:
        with pytest.raises(FetchError) as caught:
            UrllibFetcher(proxies={}).fetch(Request(site.base + "/a"), allowed_domains=("127.0.0.1",), **KW)
        assert site.requests == []
    assert caught.value.code is ErrorCode.CONFIG_INVALID


def test_public_address_passes_the_check():
    fetcher = UrllibFetcher(proxies={}, resolver=resolver_for("93.184.216.34"))
    fetcher._check_url("http://www.example.com/x", ("example.com",))  # does not raise


def test_ipv4_mapped_public_address_is_allowed():
    fetcher = UrllibFetcher(proxies={}, resolver=resolver_for("::ffff:93.184.216.34"))
    fetcher._check_url("http://www.example.com/x", ("example.com",))  # does not raise


def test_dns_failure_is_a_network_error():
    def fail(*a, **k):
        raise socket.gaierror("no such host")
    with pytest.raises(FetchError) as caught:
        UrllibFetcher(proxies={}, resolver=fail).fetch(Request("http://www.example.com/x"), allowed_domains=("example.com",), **KW)
    assert caught.value.code is ErrorCode.NETWORK_ERROR and caught.value.retryable


# --- robots.txt ---------------------------------------------------------------------------

UA = "ExhibitIQ-test"


def rules(text: str, cap: float = 30.0):
    return rules_from_text(text, UA, max_crawl_delay=cap)


def test_disallow_rules_apply_to_matching_paths_only():
    r = rules("User-agent: *\nDisallow: /private/\n")
    assert r.allows("https://x.com/public/a", UA)
    assert not r.allows("https://x.com/private/a", UA)


def test_specific_agent_group_beats_wildcard():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: ExhibitIQ-test\nAllow: /\n"
    assert rules(text).allows("https://x.com/a", UA)
    assert not rules(text).allows("https://x.com/a", "other-bot")


def test_empty_robots_allows_everything():
    assert rules("").allows("https://x.com/anything", UA)


def test_crawl_delay_is_read_and_capped():
    text = "User-agent: *\nCrawl-delay: 5\n"
    assert rules(text).crawl_delay == 5.0
    assert rules("User-agent: *\nCrawl-delay: 600\n", cap=30.0).crawl_delay == 30.0
    assert rules("User-agent: *\nDisallow:\n").crawl_delay is None


@pytest.mark.parametrize("status", [401, 403, 429])
def test_denied_robots_means_disallow_all(status):
    code, retryable = classify_http_status(status)
    r = rules_from_failure(FetchError(code, "x", http_status=status, retryable=retryable))
    assert r.mode == "disallow_all" and not r.allows("https://x.com/a", UA)
    assert str(status) in r.reason


@pytest.mark.parametrize("status", [404, 410, 400])
def test_missing_robots_means_allow_all(status):
    r = rules_from_failure(FetchError(ErrorCode.HTTP_ERROR, "x", http_status=status))
    assert r.mode == "allow_all" and r.allows("https://x.com/a", UA)


@pytest.mark.parametrize("error", [FetchError(ErrorCode.HTTP_ERROR, "boom", http_status=503, retryable=True), FetchError(ErrorCode.TIMEOUT, "slow"), FetchError(ErrorCode.NETWORK_ERROR, "down")])
def test_unreachable_robots_means_disallow_all(error):
    r = rules_from_failure(error)
    assert r.mode == "disallow_all" and not r.allows("https://x.com/a", UA)
