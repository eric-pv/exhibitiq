"""The shared crawl runner (D2-01).

``run_source`` runs one source config with one adapter and returns a ``RunResult``: raw snapshots
with provenance, raw extracted records, errors, an event log and a ``crawl_run`` record that is valid
against the shared Schema. Everything every source needs is here; nothing exhibition-specific is.

Rules the runner applies to every source:

- **Scope:** only URLs inside ``allowed_domains`` are fetched (checked before the request, again by the
  fetcher on every redirect hop, and on the final URL).
- **Politeness:** at most ``rate_limit_per_second`` requests per second (retries and robots.txt
  included), and at least the site's ``Crawl-delay`` (capped); robots.txt is honored by default.
- **Retries:** up to ``max_retries`` retries with exponential back-off, only for errors that may be
  transient (timeouts, network errors, 5xx).
- **Stop, never evade:** a 401/403/429 ends the run for that source immediately: no retry, no
  workaround. The failure is recorded and the caller continues with other sources (V2.3).
- **Evidence first:** every successful response is snapshotted (raw bytes, sha256, time, new
  ``source_id``) *before* it is parsed, so a parse failure never loses evidence.
- **Failures are data:** every failure becomes a structured ``CrawlError`` in the log and in the
  ``crawl_run`` record; one broken page does not stop the others.

Run status (``crawl_run.status``): ``cancelled`` if asked to stop; else ``failed`` if no page was
retrieved (robots.txt does not count); else ``partial`` if any error occurred or the run was cut short by ``max_requests``;
else ``succeeded``.

``crawl_run.stats.requests_*`` count every HTTP attempt, including robots.txt fetches and retries.
"""
from __future__ import annotations

import io
import os
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, TextIO
from urllib.parse import urldefrag, urlsplit

from crawler.adapters import AdapterRegistry, SourceAdapter, resolve_adapter
from crawler.clock import Clock, SystemClock
from crawler.errors import CrawlError, ErrorCode
from crawler.fetch import FetchError, Fetcher, classify_http_status, host_in_domains
from crawler.models import ExtractedRecord, ParseResult, Request, Response, Snapshot
from crawler.robots import RobotsRules, allow_all, disallow_all, rules_from_failure, rules_from_text
from crawler.runlog import RunLog, format_utc
from crawler.source_config import ConfigError, SourceConfig
from etl.hashing import sha256_of_bytes
from etl.ids import make_id


@dataclass(frozen=True)
class RunOptions:
    max_requests: int = 500  # page requests per source (retries and robots.txt not counted)
    max_bytes: int = 20 * 1024 * 1024
    respect_robots: bool = True
    max_crawl_delay_seconds: float = 30.0
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    trigger: str = "manual"  # crawl_run.trigger: manual, schedule, pull_request, import or other
    code_commit: str | None = None
    github_run_url: str | None = None
    resumes: str | None = None  # crawl_run_id of the earlier run this run continues (written to notes)


class SnapshotSink(Protocol):
    def save(self, snapshot: Snapshot) -> None:
        """Persist a snapshot (D2-06). Called once per successful response, before parsing."""


@dataclass
class RunResult:
    source: SourceConfig
    crawl_run: dict[str, Any]
    status: str
    snapshots: list[Snapshot] = field(default_factory=list)
    records: list[ExtractedRecord] = field(default_factory=list)
    errors: list[CrawlError] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # URLs not fetched, with the reason
    pending: list[str] = field(default_factory=list)  # in-scope URLs found but never fetched (max_requests, cancel, block): a resume can fetch them
    log_text: str = ""


def _normalize(url: str) -> str:
    url, _ = urldefrag(url)
    parts = urlsplit(url)
    return parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()).geturl()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _milliseconds(moment) -> int:  # type: ignore[no-untyped-def]
    return int(moment.timestamp() * 1000)


class _Crawl:
    def __init__(
        self,
        config: SourceConfig,
        adapter: SourceAdapter,
        fetcher: Fetcher,
        clock: Clock,
        options: RunOptions,
        log_stream: TextIO | None,
        sink: SnapshotSink | None,
        cancel: Callable[[], bool] | None,
        rand: Callable[[int], bytes],
        start_requests: Iterable[Request] | None = None,
    ) -> None:
        self.initial = start_requests
        self.config, self.adapter, self.fetcher, self.clock, self.options = config, adapter, fetcher, clock, options
        self.sink, self.cancel, self.rand = sink, cancel, rand
        self._own_stream = io.StringIO() if log_stream is None else None
        self.stream: TextIO = self._own_stream if self._own_stream is not None else log_stream  # type: ignore[assignment]
        self.log = RunLog(self.stream, clock=clock.now)
        self.result = RunResult(source=config, crawl_run={}, status="failed")
        self.robots: dict[str, RobotsRules] = {}
        self.last_attempt: float | None = None
        self.min_interval = 1.0 / config.rate_limit_per_second
        self.blocked = False
        self.pages_succeeded = 0

    # ------------------------------------------------------------------ bookkeeping
    def error(self, code: ErrorCode, message: str, url: str | None = None, *, http_status: int | None = None, retryable: bool | None = None) -> None:
        error = CrawlError(code, message, url=url, http_status=http_status, retryable=retryable)
        self.result.errors.append(error)
        self.log.log_error(error)

    def skip(self, url: str, reason: str) -> None:
        self.result.skipped.append(f"{url}: {reason}")
        self.log.event("WARNING", "skipped", reason, url=url)

    def in_scope(self, url: str) -> bool:
        parts = urlsplit(url)
        return parts.scheme in ("http", "https") and host_in_domains(parts.hostname, self.config.allowed_domains)

    # ------------------------------------------------------------------ requests
    def _wait_turn(self, interval: float) -> None:
        if self.last_attempt is not None:
            wait = self.last_attempt + interval - self.clock.monotonic()
            if wait > 0:
                self.clock.sleep(wait)
        self.last_attempt = self.clock.monotonic()

    def _interval_for(self, url: str) -> float:
        rules = self.robots.get(_origin(url))
        delay = rules.crawl_delay if rules is not None and rules.crawl_delay else 0.0
        return max(self.min_interval, delay)

    @staticmethod
    def _status_error(response: Response) -> FetchError | None:
        if 200 <= response.status <= 299:
            return None
        code, retryable = classify_http_status(response.status)
        return FetchError(code, f"HTTP {response.status} for {response.url}", http_status=response.status, retryable=retryable)

    def request_with_retries(self, request: Request) -> tuple[Response | None, FetchError | None]:
        """One logical request: rate-limited, retried when worthwhile. Does not record the final error."""
        attempts = self.config.max_retries + 1
        failure: FetchError | None = None
        for attempt in range(1, attempts + 1):
            self._wait_turn(self._interval_for(request.url))
            try:
                response = self.fetcher.fetch(
                    request,
                    timeout=self.config.timeout_seconds,
                    user_agent=self.config.user_agent,
                    max_bytes=self.options.max_bytes,
                    allowed_domains=self.config.allowed_domains,
                )
                failure = self._status_error(response)
                if failure is None and not host_in_domains(urlsplit(response.final_url).hostname, self.config.allowed_domains):
                    failure = FetchError(ErrorCode.CONFIG_INVALID, f"the final URL {response.final_url} is outside allowed_domains")
            except FetchError as exc:
                failure = exc
            if failure is None:
                self.log.log_request(request.url, succeeded=True, http_status=response.status)
                return response, None
            self.log.log_request(request.url, succeeded=False, http_status=failure.http_status)
            if not failure.retryable or attempt == attempts:
                return None, failure
            delay = min(self.options.backoff_max_seconds, self.options.backoff_base_seconds * 2 ** (attempt - 1))
            self.log.event("WARNING", "retry", failure.message, url=request.url, attempt=attempt, delay_seconds=delay, code=str(failure.code))
            self.clock.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    # ------------------------------------------------------------------ robots.txt
    def robots_for(self, url: str) -> RobotsRules:
        origin = _origin(url)
        if origin not in self.robots:
            robots_url = f"{origin}/robots.txt"
            response, failure = self.request_with_retries(Request(robots_url))
            if response is not None:
                text = response.content.decode("utf-8", errors="replace")
                rules = rules_from_text(text, self.config.user_agent, max_crawl_delay=self.options.max_crawl_delay_seconds)
            else:
                assert failure is not None
                rules = rules_from_failure(failure)
            self.robots[origin] = rules
            self.log.event("INFO", "robots", rules.reason, origin=origin, mode=rules.mode, crawl_delay=rules.crawl_delay)
        return self.robots[origin]

    # ------------------------------------------------------------------ one page
    def make_snapshot(self, response: Response) -> Snapshot:
        now = self.clock.now()
        snapshot = Snapshot(
            source_id=make_id("src", now_ms=_milliseconds(now), rand=self.rand),
            crawl_run_id=self.run_id,
            url=response.url,
            final_url=response.final_url,
            retrieved_at=format_utc(now),
            http_status=response.status,
            media_type=response.media_type,
            content_sha256=sha256_of_bytes(response.content),
            size=len(response.content),
            content=response.content,
        )
        self.result.snapshots.append(snapshot)
        self.pages_succeeded += 1
        if self.sink is not None:
            self.sink.save(snapshot)
        return snapshot

    def parse(self, request: Request, response: Response, snapshot: Snapshot, queue: deque[Request]) -> None:
        try:
            parsed = self.adapter.parse(response, request, self.config)
            if not isinstance(parsed, ParseResult):
                raise TypeError(f"parse() must return a ParseResult, got {type(parsed).__name__}")
            rows = [row for row in parsed.records]
            if not all(isinstance(row, Mapping) for row in rows):
                raise TypeError("every parsed record must be a mapping")
        except Exception as exc:  # an adapter bug or a page it cannot read must not stop the run
            from crawler.adapters import ParseError

            if isinstance(exc, ParseError):
                self.error(ErrorCode.PARSE_ERROR, str(exc) or "page could not be parsed", request.url)
            else:
                self.error(ErrorCode.UNEXPECTED, f"adapter {self.adapter.name!r} raised {type(exc).__name__}: {exc}", request.url)
            return
        for row in rows:
            self.result.records.append(ExtractedRecord(data=dict(row), url=request.url, source_id=snapshot.source_id, snapshot_sha256=snapshot.content_sha256))
        self.log.log_records(len(rows), url=request.url, source_id=snapshot.source_id)
        for warning in parsed.warnings:
            self.log.event("WARNING", "adapter_warning", warning, url=request.url)
        queue.extend(parsed.follow)

    # ------------------------------------------------------------------ the run
    def run(self) -> RunResult:
        started = self.clock.now()
        self.run_id = make_id("run", now_ms=_milliseconds(started), rand=self.rand)
        self.log.event("INFO", "run_started", source=self.config.name, adapter=self.adapter.name, crawl_run_id=self.run_id, exhibition_id=self.config.exhibition_id)

        queue: deque[Request] = deque()
        seen: set[str] = set()
        cancelled = False
        truncated = 0
        pages = 0
        try:
            queue.extend(self.initial if self.initial is not None else self.adapter.start_requests(self.config))
        except Exception as exc:
            self.error(ErrorCode.UNEXPECTED, f"adapter {self.adapter.name!r} start_requests raised {type(exc).__name__}: {exc}")

        while queue and not self.blocked:
            if self.cancel is not None and self.cancel():
                cancelled = True
                self.log.event("WARNING", "cancelled", "stop requested")
                break
            request = queue.popleft()
            url = _normalize(request.url)
            if url in seen:
                continue
            seen.add(url)
            if not self.in_scope(url):
                self.skip(url, "outside allowed_domains")
                continue
            if pages >= self.options.max_requests:
                waiting = [_normalize(r.url) for r in queue]
                self.result.pending.append(url)
                truncated += 1 + sum(1 for u in waiting if u not in seen and u not in self.result.pending)
                self.log.event("WARNING", "max_requests", f"stopped at max_requests={self.options.max_requests}", unfetched=truncated)
                break
            if self.options.respect_robots:
                rules = self.robots_for(url)
                if not rules.allows(url, self.config.user_agent):
                    self.skip(url, f"disallowed by robots.txt ({rules.reason})")
                    self.error(ErrorCode.ACCESS_BLOCKED, f"not fetched: disallowed by robots.txt ({rules.reason})", url)
                    continue
            pages += 1
            response, failure = self.request_with_retries(Request(url, request.headers, request.meta))
            if response is None:
                assert failure is not None
                self.error(failure.code, failure.message, url, http_status=failure.http_status, retryable=failure.retryable)
                if failure.code is ErrorCode.ACCESS_BLOCKED:
                    self.blocked = True
                    self.log.event("ERROR", "blocked", "access blocked: stopping this source, not working around it", url=url)
                continue
            snapshot = self.make_snapshot(response)
            self.parse(Request(url, request.headers, request.meta), response, snapshot, queue)

        for waiting_request in queue:  # whatever is still queued (max_requests, cancel, block) can be fetched by a resume
            waiting_url = _normalize(waiting_request.url)
            if waiting_url not in seen and waiting_url not in self.result.pending and self.in_scope(waiting_url):
                self.result.pending.append(waiting_url)
        finished = self.clock.now()
        stats = self.log.stats()
        if cancelled:
            status = "cancelled"
        elif self.pages_succeeded == 0:  # robots.txt requests do not count as data
            status = "failed"
        elif stats["error_count"] > 0 or truncated:
            status = "partial"
        else:
            status = "succeeded"
        note_parts = []
        if self.options.resumes:
            note_parts.append(f"resumes {self.options.resumes}: fetches only the URLs that run could not fetch")
        if truncated:
            note_parts.append(f"stopped at max_requests={self.options.max_requests}; {truncated} URL(s) were not fetched, so the data is incomplete")
        notes = "; ".join(note_parts) or None
        self.log.event("INFO", "run_finished", status=status, **stats)
        self.result.status = status
        self.result.crawl_run = self.log.build_crawl_run(
            crawl_run_id=self.run_id,
            exhibition_id=self.config.exhibition_id,
            edition_id=self.config.edition_id,
            crawler_name=self.adapter.name,
            crawler_version=self.adapter.version,
            trigger=self.options.trigger,
            started_at=started,
            finished_at=finished,
            status=status,
            code_commit=self.options.code_commit,
            github_run_url=self.options.github_run_url,
            notes=notes,
        )
        if self._own_stream is not None:
            self.result.log_text = self._own_stream.getvalue()
        return self.result


def run_source(
    config: SourceConfig,
    adapter: SourceAdapter,
    fetcher: Fetcher,
    *,
    clock: Clock | None = None,
    options: RunOptions | None = None,
    log_stream: TextIO | None = None,
    sink: SnapshotSink | None = None,
    cancel: Callable[[], bool] | None = None,
    rand: Callable[[int], bytes] = os.urandom,
    start_requests: Iterable[Request] | None = None,
) -> RunResult:
    """Run one source. Never raises for crawl problems; they are in the result.

    ``start_requests`` replaces the adapter's first requests (used to resume: only the URLs that are still missing).
    """
    return _Crawl(config, adapter, fetcher, clock or SystemClock(), options or RunOptions(), log_stream, sink, cancel, rand, start_requests).run()


def _failed_result(config: SourceConfig, error: CrawlError, clock: Clock, options: RunOptions, rand: Callable[[int], bytes]) -> RunResult:
    """A run that could not start (bad config, missing adapter) or crashed: recorded, not raised."""
    stream = io.StringIO()
    log = RunLog(stream, clock=clock.now)
    now = clock.now()
    log.log_error(error)
    crawl_run = log.build_crawl_run(
        crawl_run_id=make_id("run", now_ms=_milliseconds(now), rand=rand),
        exhibition_id=config.exhibition_id,
        edition_id=config.edition_id,
        crawler_name=config.adapter or "unresolved",
        crawler_version="0.0.0",
        trigger=options.trigger,
        started_at=now,
        finished_at=clock.now(),
        status="failed",
        code_commit=options.code_commit,
        github_run_url=options.github_run_url,
    )
    return RunResult(source=config, crawl_run=crawl_run, status="failed", errors=[error], log_text=stream.getvalue())


def run_all(
    configs: Iterable[SourceConfig],
    *,
    adapters: AdapterRegistry,
    fetcher: Fetcher,
    clock: Clock | None = None,
    options: RunOptions | None = None,
    sink: SnapshotSink | None = None,
    cancel: Callable[[], bool] | None = None,
    rand: Callable[[int], bytes] = os.urandom,
) -> list[RunResult]:
    """Run several sources independently. A source that fails, is blocked or crashes never stops the others (V2.3)."""
    clock = clock or SystemClock()
    options = options or RunOptions()
    results: list[RunResult] = []
    for config in configs:
        try:
            adapter = resolve_adapter(config, adapters)
        except ConfigError as exc:
            results.append(_failed_result(config, CrawlError(ErrorCode.CONFIG_INVALID, str(exc)), clock, options, rand))
            continue
        try:
            results.append(run_source(config, adapter, fetcher, clock=clock, options=options, sink=sink, cancel=cancel, rand=rand))
        except Exception as exc:  # a bug in the framework itself: record it, keep going
            results.append(_failed_result(config, CrawlError(ErrorCode.UNEXPECTED, f"{type(exc).__name__}: {exc}"), clock, options, rand))
    return results
