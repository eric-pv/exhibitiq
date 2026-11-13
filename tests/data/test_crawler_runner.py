"""Tests for crawler.runner (D2-01): scope, politeness, retries, stop-on-block, evidence, status, isolation."""
from __future__ import annotations

import json

import pytest

from crawler.adapters import AdapterRegistry, ParseError
from crawler.errors import ErrorCode
from crawler.fetch import FetchError
from crawler.models import ParseResult, Request
from crawler.runner import RunOptions, run_all, run_source
from etl.hashing import sha256_of_bytes
from etl.schema_registry import SchemaSet
from tests.data.crawl_testkit import FakeClock, FakeFetcher, fixed_rand, make_config, page, scripted_adapter

START = "https://www.example.com/list"
ROBOTS = "https://www.example.com/robots.txt"
SCHEMAS = SchemaSet()


def rows_adapter(**kw):
    """Each page yields one record with its URL; page bodies of the form 'follow:<url>,<url>' add links."""

    def parse(response, request, config):
        body = response.content.decode()
        follow = [Request(u) for u in body[7:].split(",")] if body.startswith("follow:") else []
        return ParseResult(records=[{"url": request.url, "n": len(body)}], follow=follow)

    return scripted_adapter(parse, **kw)


def run(script, *, adapter=None, config=None, options=None, **kw):
    clock = kw.pop("clock", None) or FakeClock()
    fetcher = FakeFetcher(script)
    result = run_source(config or make_config(), adapter or rows_adapter(), fetcher, clock=clock, options=options or RunOptions(backoff_base_seconds=1.0), rand=fixed_rand, **kw)
    return result, fetcher, clock


def codes(result):
    return [e.code for e in result.errors]


def assert_valid_crawl_run(result):
    assert SCHEMAS.errors("crawl_run", result.crawl_run) == [], result.crawl_run


# --- happy path ---------------------------------------------------------------------------


def test_successful_run_produces_snapshot_record_and_valid_crawl_run():
    result, fetcher, _ = run({ROBOTS: 404, START: page(START, "<p>hello</p>")})
    assert result.status == "succeeded" and result.errors == []
    assert fetcher.calls == [ROBOTS, START]
    (snap,) = result.snapshots
    assert snap.content == b"<p>hello</p>" and snap.size == 12
    assert snap.content_sha256 == sha256_of_bytes(b"<p>hello</p>")
    assert snap.url == START and snap.http_status == 200 and snap.media_type == "text/html"
    assert snap.source_id.startswith("src_") and snap.crawl_run_id == result.crawl_run["crawl_run_id"]
    (record,) = result.records
    assert record.data == {"url": START, "n": 12} and record.source_id == snap.source_id and record.snapshot_sha256 == snap.content_sha256
    assert_valid_crawl_run(result)
    run_record = result.crawl_run
    assert run_record["status"] == "succeeded" and run_record["crawler"] == {"name": "scripted", "version": "1.2.3"}
    assert run_record["exhibition_id"] == "example-expo" and run_record["edition_id"] == "example-expo-2026"
    # robots.txt (404) counts as an attempt but not as a success; the page is the one success
    assert run_record["stats"] == {"requests_attempted": 2, "requests_succeeded": 1, "records_extracted": 1, "error_count": 0}


def test_log_text_is_json_lines_with_run_events():
    result, _, _ = run({ROBOTS: 404, START: "x"})
    events = [json.loads(line) for line in result.log_text.splitlines()]
    names = [e["event"] for e in events]
    assert names[0] == "run_started" and names[-1] == "run_finished"
    assert "robots" in names


def test_log_stream_argument_is_used_instead_of_buffer():
    import io

    stream = io.StringIO()
    result, _, _ = run({ROBOTS: 404, START: "x"}, log_stream=stream)
    assert stream.getvalue() and result.log_text == ""


def test_run_options_pass_through_to_crawl_run():
    result, _, _ = run({ROBOTS: 404, START: "x"}, options=RunOptions(trigger="schedule", code_commit="a" * 40, github_run_url="https://github.com/o/r/actions/runs/1"))
    assert result.crawl_run["trigger"] == "schedule" and result.crawl_run["code_commit"] == "a" * 40
    assert result.crawl_run["github_run_url"].endswith("/runs/1")
    assert_valid_crawl_run(result)


def test_sink_receives_each_snapshot_before_parse():
    order = []

    class Sink:
        def save(self, snapshot):
            order.append(("save", snapshot.url))

    def parse(response, request, config):
        order.append(("parse", request.url))
        return ParseResult()

    run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(parse), sink=Sink())
    assert order == [("save", START), ("parse", START)]


def test_snapshot_ids_are_unique_and_valid():
    script = {ROBOTS: 404, START: "follow:https://www.example.com/a,https://www.example.com/b", "https://www.example.com/a": "a", "https://www.example.com/b": "b"}
    result, _, _ = run(script)
    ids = [s.source_id for s in result.snapshots]
    assert len(ids) == 3 == len(set(ids))
    for snapshot in result.snapshots:
        assert snapshot.source_id[4] in "01234567"  # ULID first character; full pattern is covered in test_ids
    assert all(len(i) == 4 + 26 for i in ids)


# --- crawling: follow links, dedupe, scope ------------------------------------------------


def test_follow_links_breadth_first_and_dedupe():
    a, b = "https://www.example.com/a", "https://www.example.com/b"
    script = {ROBOTS: 404, START: f"follow:{a},{b}", a: f"follow:{b},{START}#frag", b: "leaf"}
    result, fetcher, _ = run(script)
    assert fetcher.calls == [ROBOTS, START, a, b]  # each URL once, fragment ignored, BFS order
    assert result.status == "succeeded" and len(result.snapshots) == 3


def test_out_of_scope_links_are_skipped_not_fetched():
    outside = "https://www.other.org/x"
    result, fetcher, _ = run({ROBOTS: 404, START: f"follow:{outside},ftp://www.example.com/f,https://evilexample.com/y"})
    assert fetcher.calls == [ROBOTS, START]
    assert len(result.skipped) == 3 and all("outside allowed_domains" in s for s in result.skipped)
    assert result.errors == [] and result.status == "succeeded"


def test_url_case_in_host_and_fragments_normalize():
    result, fetcher, _ = run({ROBOTS: 404, START: "follow:HTTPS://WWW.EXAMPLE.COM/list#top"})
    assert fetcher.calls == [ROBOTS, START]


def test_redirect_to_out_of_scope_final_url_is_an_error_without_parsing():
    out = page(START, "secret", final_url="https://www.other.org/landing")
    result, _, _ = run({ROBOTS: 404, START: out})
    assert codes(result) == [ErrorCode.CONFIG_INVALID] and result.records == [] and result.snapshots == []
    assert result.status == "failed"


def test_max_requests_truncates_and_marks_partial():
    urls = [f"https://www.example.com/p{i}" for i in range(5)]
    script = {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: "x" for u in urls}}
    result, fetcher, _ = run(script, options=RunOptions(max_requests=3))
    assert len(result.snapshots) == 3 and result.status == "partial"
    assert fetcher.calls.count(ROBOTS) == 1 and len(fetcher.calls) == 4
    assert "max_requests=3" in result.crawl_run["notes"] and "incomplete" in result.crawl_run["notes"]
    assert_valid_crawl_run(result)


def test_exactly_max_requests_pages_is_not_truncated():
    result, _, _ = run({ROBOTS: 404, START: "x"}, options=RunOptions(max_requests=1))
    assert result.status == "succeeded" and "notes" not in result.crawl_run


# --- robots.txt ---------------------------------------------------------------------------


def test_disallowed_url_is_not_fetched_and_recorded():
    blocked = "https://www.example.com/private/x"
    script = {ROBOTS: "User-agent: *\nDisallow: /private/\n", START: f"follow:{blocked}", blocked: "nope"}
    result, fetcher, _ = run(script)
    assert blocked not in fetcher.calls
    assert codes(result) == [ErrorCode.ACCESS_BLOCKED] and "robots.txt" in result.errors[0].message
    assert result.status == "partial" and len(result.snapshots) == 1
    assert any("robots.txt" in s for s in result.skipped)


def test_robots_is_fetched_once_per_origin():
    a = "https://www.example.com/a"
    result, fetcher, _ = run({ROBOTS: 404, START: f"follow:{a}", a: "x"})
    assert fetcher.calls.count(ROBOTS) == 1


def test_robots_fetch_for_second_origin():
    sub = "https://shop.example.com/a"
    result, fetcher, _ = run({ROBOTS: 404, "https://shop.example.com/robots.txt": 404, START: f"follow:{sub}", sub: "x"})
    assert "https://shop.example.com/robots.txt" in fetcher.calls and result.status == "succeeded"


@pytest.mark.parametrize("script_value", [403, 429, 401, 503])
def test_unavailable_robots_blocks_the_whole_origin(script_value):
    result, fetcher, _ = run({ROBOTS: script_value, START: "x"})
    assert START not in fetcher.calls and result.snapshots == []
    assert ErrorCode.ACCESS_BLOCKED in codes(result) and result.status == "failed"


def test_missing_robots_allows_crawling():
    result, _, _ = run({ROBOTS: 404, START: "x"})
    assert result.status == "succeeded"


def test_respect_robots_false_skips_robots_entirely():
    result, fetcher, _ = run({START: "x"}, options=RunOptions(respect_robots=False))
    assert fetcher.calls == [START] and result.status == "succeeded"


def test_crawl_delay_slows_requests():
    a = "https://www.example.com/a"
    result, _, clock = run({ROBOTS: "User-agent: *\nCrawl-delay: 10\n", START: f"follow:{a}", a: "x"})
    assert max(clock.sleeps) == pytest.approx(10.0)


def test_crawl_delay_is_capped_by_options():
    a = "https://www.example.com/a"
    _, _, clock = run({ROBOTS: "User-agent: *\nCrawl-delay: 500\n", START: f"follow:{a}", a: "x"}, options=RunOptions(max_crawl_delay_seconds=7.0))
    assert max(clock.sleeps) == pytest.approx(7.0)


# --- rate limiting ------------------------------------------------------------------------


def test_requests_are_spaced_by_the_configured_rate():
    urls = [f"https://www.example.com/p{i}" for i in range(3)]
    script = {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: "x" for u in urls}}
    result, fetcher, clock = run(script, config=make_config(rate_limit_per_second=0.5))
    assert len(fetcher.calls) == 5
    assert clock.sleeps == [pytest.approx(2.0)] * 4  # every request after the first waits 1/0.5 s (fake time: no other time passes)


def test_slow_requests_need_no_extra_wait():
    # when the previous request already took longer than the interval, no sleep is needed
    class SlowFetcher(FakeFetcher):
        def fetch(self, request, **kw):
            clock.tick(5.0)
            return super().fetch(request, **kw)

    clock = FakeClock()
    fetcher = SlowFetcher({ROBOTS: 404, START: "x"})
    run_source(make_config(rate_limit_per_second=1.0), rows_adapter(), fetcher, clock=clock, rand=fixed_rand)
    assert clock.sleeps == []


def test_retries_also_respect_the_rate_limit():
    result, _, clock = run({ROBOTS: 404, START: [503, "ok"]}, config=make_config(rate_limit_per_second=0.5))
    # robots at t=0; page waits 2 (t=2, fails); back-off 1 (t=3); spacing wait 1 (t=4); page ok
    assert result.status == "succeeded"
    assert clock.sleeps == [pytest.approx(2.0), pytest.approx(1.0), pytest.approx(1.0)]


# --- retries and errors -------------------------------------------------------------------


def test_transient_errors_are_retried_with_exponential_backoff_then_succeed():
    result, fetcher, clock = run({ROBOTS: 404, START: [503, 503, "ok"]}, config=make_config(max_retries=3, rate_limit_per_second=1000.0), options=RunOptions(backoff_base_seconds=1.0))
    assert fetcher.calls.count(START) == 3 and result.status == "succeeded" and result.errors == []
    assert [s for s in clock.sleeps if s >= 1.0] == [1.0, 2.0]
    stats = result.crawl_run["stats"]
    assert stats["requests_attempted"] == 4 and stats["requests_succeeded"] == 1  # robots, 2 failed attempts, 1 success


def test_backoff_is_capped():
    _, _, clock = run({ROBOTS: 404, START: 503}, config=make_config(max_retries=6, rate_limit_per_second=1000.0), options=RunOptions(backoff_base_seconds=1.0, backoff_max_seconds=4.0))
    assert [s for s in clock.sleeps if s >= 1.0] == [1.0, 2.0, 4.0, 4.0, 4.0, 4.0]


def test_retries_are_bounded_and_final_failure_is_recorded_once():
    result, fetcher, _ = run({ROBOTS: 404, START: 503}, config=make_config(max_retries=2))
    assert fetcher.calls.count(START) == 3
    assert len(result.errors) == 1 and result.errors[0].code is ErrorCode.HTTP_ERROR and result.errors[0].http_status == 503
    assert result.status == "failed"


def test_zero_retries_means_one_attempt():
    _, fetcher, _ = run({ROBOTS: 404, START: 503}, config=make_config(max_retries=0))
    assert fetcher.calls.count(START) == 1


@pytest.mark.parametrize("script_value", [404, 410, 400])
def test_permanent_errors_are_not_retried(script_value):
    result, fetcher, _ = run({ROBOTS: 404, START: script_value})
    assert fetcher.calls.count(START) == 1 and codes(result) == [ErrorCode.HTTP_ERROR]


def test_network_error_and_timeout_are_retried():
    err = FetchError(ErrorCode.NETWORK_ERROR, "down")
    timeout = FetchError(ErrorCode.TIMEOUT, "slow")
    result, fetcher, _ = run({ROBOTS: 404, START: [err, timeout, "ok"]}, config=make_config(max_retries=2))
    assert fetcher.calls.count(START) == 3 and result.status == "succeeded"


def test_config_invalid_from_fetcher_is_not_retried():
    result, fetcher, _ = run({ROBOTS: 404, START: FetchError(ErrorCode.CONFIG_INVALID, "bad")})
    assert fetcher.calls.count(START) == 1 and codes(result) == [ErrorCode.CONFIG_INVALID]


def test_one_failing_page_does_not_stop_the_others():
    a, b = "https://www.example.com/a", "https://www.example.com/b"
    result, _, _ = run({ROBOTS: 404, START: f"follow:{a},{b}", a: 404, b: "ok"})
    assert len(result.snapshots) == 2 and codes(result) == [ErrorCode.HTTP_ERROR] and result.status == "partial"
    assert_valid_crawl_run(result)
    assert result.crawl_run["error_samples"][0]["url"] == a


# --- blocked: stop, never evade -----------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403, 429])
def test_block_stops_the_source_immediately_without_retry(status):
    a, b = "https://www.example.com/a", "https://www.example.com/b"
    result, fetcher, _ = run({ROBOTS: 404, START: f"follow:{a},{b}", a: status, b: "never"})
    assert fetcher.calls.count(a) == 1 and b not in fetcher.calls
    assert codes(result) == [ErrorCode.ACCESS_BLOCKED] and result.errors[0].http_status == status
    assert result.status == "partial"  # START succeeded before the block
    assert any(json.loads(line)["event"] == "blocked" for line in result.log_text.splitlines())
    assert_valid_crawl_run(result)


def test_block_on_first_page_is_failed():
    result, _, _ = run({ROBOTS: 404, START: 403})
    assert result.status == "failed"
    assert result.snapshots == [] and codes(result) == [ErrorCode.ACCESS_BLOCKED]


def test_no_workaround_headers_are_ever_added():
    result, fetcher, _ = run({ROBOTS: 404, START: 403})
    # the runner passes the request through unchanged: no cookies, tokens, referers or alternate agents
    assert all(k["user_agent"] == "ExhibitIQ-crawler" for k in fetcher.kwargs)


def test_robots_success_does_not_make_an_all_failed_run_partial():
    result, _, _ = run({ROBOTS: "User-agent: *\nDisallow:\n", START: 500})
    assert result.crawl_run["stats"]["requests_succeeded"] == 1 and result.status == "failed"


# --- adapter failures are contained -------------------------------------------------------


def test_parse_error_is_recorded_but_snapshot_is_kept():
    def parse(response, request, config):
        raise ParseError("table not found")

    result, _, _ = run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(parse))
    assert len(result.snapshots) == 1 and codes(result) == [ErrorCode.PARSE_ERROR]
    assert result.errors[0].message == "table not found" and result.status == "partial"


def test_adapter_bug_becomes_unexpected_not_a_crash():
    def parse(response, request, config):
        raise KeyError("boom")

    result, _, _ = run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(parse))
    assert codes(result) == [ErrorCode.UNEXPECTED] and "KeyError" in result.errors[0].message and len(result.snapshots) == 1


@pytest.mark.parametrize("returned", [None, {"records": []}, [1, 2]])
def test_adapter_returning_wrong_type_is_unexpected(returned):
    result, _, _ = run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(lambda *a: returned))
    assert codes(result) == [ErrorCode.UNEXPECTED] and "ParseResult" in result.errors[0].message


def test_non_mapping_record_is_unexpected_and_nothing_partial_is_kept():
    result, _, _ = run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(lambda *a: ParseResult(records=[{"ok": 1}, "bad"])))
    assert codes(result) == [ErrorCode.UNEXPECTED] and result.records == []


def test_adapter_warnings_are_logged_not_errors():
    result, _, _ = run({ROBOTS: 404, START: "x"}, adapter=scripted_adapter(lambda *a: ParseResult(warnings=["column missing"])))
    assert result.errors == [] and "column missing" in result.log_text and result.status == "succeeded"


def test_start_requests_failure_is_recorded():
    adapter = rows_adapter()
    adapter.start_requests = lambda config: (_ for _ in ()).throw(RuntimeError("bad start"))
    result, _, _ = run({}, adapter=adapter)
    assert codes(result) == [ErrorCode.UNEXPECTED] and result.status == "failed"
    assert_valid_crawl_run(result)


def test_adapter_start_requests_override_is_used():
    adapter = rows_adapter()
    adapter.start_requests = lambda config: [Request("https://www.example.com/custom")]
    _, fetcher, _ = run({ROBOTS: 404, "https://www.example.com/custom": "x"}, adapter=adapter)
    assert fetcher.calls == [ROBOTS, "https://www.example.com/custom"]


def test_records_from_failed_parse_are_not_added():
    def parse(response, request, config):
        if request.url == START:
            return ParseResult(records=[{"a": 1}], follow=[Request("https://www.example.com/bad")])
        raise ParseError("bad page")

    result, _, _ = run({ROBOTS: 404, START: "x", "https://www.example.com/bad": "y"}, adapter=scripted_adapter(parse))
    assert [r.data for r in result.records] == [{"a": 1}]


# --- status rules -------------------------------------------------------------------------


def test_all_requests_failing_is_failed_and_valid():
    result, _, _ = run({ROBOTS: 404, START: 500})
    assert result.status == "failed" and result.snapshots == []
    assert_valid_crawl_run(result)


def test_cancel_before_first_request():
    result, fetcher, _ = run({ROBOTS: 404, START: "x"}, cancel=lambda: True)
    assert result.status == "cancelled" and fetcher.calls == []
    assert_valid_crawl_run(result)


def test_cancel_midway_keeps_what_was_collected():
    a = "https://www.example.com/a"
    state = {"n": 0}

    def cancel():
        state["n"] += 1
        return state["n"] > 1

    result, _, _ = run({ROBOTS: 404, START: f"follow:{a}", a: "x"}, cancel=cancel)
    assert result.status == "cancelled" and len(result.snapshots) == 1


def test_error_samples_are_limited_to_the_contract():
    urls = [f"https://www.example.com/e{i}" for i in range(60)]
    script = {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: 404 for u in urls}}
    result, _, _ = run(script, options=RunOptions(max_requests=100))
    assert result.crawl_run["stats"]["error_count"] == 60 and len(result.crawl_run["error_samples"]) == 50
    assert_valid_crawl_run(result)


# --- run_all: one source never blocks the others (V2.3) -----------------------------------


def test_run_all_isolates_failures():
    registry = AdapterRegistry()
    registry.register(type(rows_adapter()), name="scripted")

    good = make_config(name="good")
    other_url = "https://www.other.org/list"
    blocked = make_config(name="blocked", start_urls=(other_url,), allowed_domains=("other.org",))
    missing = make_config(name="missing", adapter="nope")
    no_adapter = make_config(name="no-adapter", adapter=None)
    fetcher = FakeFetcher({ROBOTS: 404, START: "ok", "https://www.other.org/robots.txt": 404, other_url: 403})
    results = run_all([blocked, missing, no_adapter, good], adapters=registry, fetcher=fetcher, clock=FakeClock(), rand=fixed_rand)
    by_name = {r.source.name: r for r in results}
    assert [r.source.name for r in results] == ["blocked", "missing", "no-adapter", "good"]
    assert by_name["good"].status == "succeeded" and len(by_name["good"].snapshots) == 1
    assert by_name["blocked"].status == "failed" and codes(by_name["blocked"]) == [ErrorCode.ACCESS_BLOCKED]
    assert codes(by_name["missing"]) == [ErrorCode.CONFIG_INVALID] and by_name["missing"].status == "failed"
    assert codes(by_name["no-adapter"]) == [ErrorCode.CONFIG_INVALID]
    for r in results:
        assert_valid_crawl_run(r)


def test_run_all_survives_a_framework_crash():
    registry = AdapterRegistry()
    registry.register(type(rows_adapter()), name="scripted")

    class Exploding(FakeFetcher):
        def fetch(self, request, **kw):
            raise MemoryError("simulated crash")

    results = run_all([make_config()], adapters=registry, fetcher=Exploding({}), clock=FakeClock(), rand=fixed_rand)
    assert results[0].status == "failed" and codes(results[0]) == [ErrorCode.UNEXPECTED]
    assert_valid_crawl_run(results[0])


# --- generality (V2.3) --------------------------------------------------------------------


def test_same_runner_handles_two_differently_shaped_sources_without_code_change():
    csv_url = "https://data.other.net/export.csv"

    def parse_csv(response, request, config):
        lines = response.content.decode().splitlines()
        head, *rows = [line.split(",") for line in lines]
        return ParseResult(records=[dict(zip(head, row)) for row in rows])

    html = run({ROBOTS: 404, START: "<li>A</li>"})[0]
    config2 = make_config(name="csv", exhibition_id="another-fair", edition_id="another-fair-2026", start_urls=(csv_url,), allowed_domains=("other.net",), adapter="csv")
    fetcher = FakeFetcher({"https://data.other.net/robots.txt": 404, csv_url: "name,booth\nAcme,A1\nBeta,B2\n"})
    csv_result = run_source(config2, scripted_adapter(parse_csv, name="csv"), fetcher, clock=FakeClock(), rand=fixed_rand)
    assert [r.data for r in csv_result.records] == [{"name": "Acme", "booth": "A1"}, {"name": "Beta", "booth": "B2"}]
    assert html.status == csv_result.status == "succeeded"
    assert csv_result.crawl_run["exhibition_id"] == "another-fair"
