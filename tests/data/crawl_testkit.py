"""Shared fakes for crawler tests (D2-01): a deterministic clock, a scripted fetcher and a local server.

Nothing here touches the real network. ``LocalSite`` serves from 127.0.0.1 on an ephemeral port and
is used only with ``UrllibFetcher(allow_private_networks=True, proxies={})``.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from crawler.errors import ErrorCode
from crawler.fetch import FetchError, classify_http_status
from crawler.models import ParseResult, Request, Response
from crawler.source_config import SourceConfig

T0 = datetime(2026, 11, 3, 6, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """Time that only moves when someone sleeps (or ``tick`` is called). Records every sleep."""

    def __init__(self, start: datetime = T0) -> None:
        self._start = start
        self._elapsed = 0.0
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self._start + timedelta(seconds=self._elapsed)

    def monotonic(self) -> float:
        return 1000.0 + self._elapsed

    def sleep(self, seconds: float) -> None:
        assert seconds >= 0
        self.sleeps.append(seconds)
        self._elapsed += seconds

    def tick(self, seconds: float) -> None:
        self._elapsed += seconds


def fixed_rand(n: int) -> bytes:
    """Deterministic 'random' bytes that still produce valid IDs (first character of the ULID is 0-7)."""
    fixed_rand.counter += 1
    return (fixed_rand.counter).to_bytes(n, "big")


fixed_rand.counter = 0  # type: ignore[attr-defined]


def make_config(**overrides: Any) -> SourceConfig:
    base: dict[str, Any] = dict(
        name="example-source", exhibition_id="example-expo", edition_id="example-expo-2026",
        source_type="official_exhibitor_list", start_urls=("https://www.example.com/list",),
        allowed_domains=("example.com",), rate_limit_per_second=2.0, max_retries=2, adapter="scripted",
    )
    base.update(overrides)
    return SourceConfig(**base)


class FakeFetcher:
    """Answers from a script: ``{url: Response | FetchError | [items consumed one per attempt]}``.

    A bare status int in the script means "that HTTP status with an empty body". Unknown URLs are 404.
    Every attempt is recorded in ``calls``.
    """

    def __init__(self, script: Mapping[str, Any]) -> None:
        self.script = {url: (list(v) if isinstance(v, list) else [v]) for url, v in script.items()}
        self.calls: list[str] = []
        self.kwargs: list[dict[str, Any]] = []

    def fetch(self, request: Request, *, timeout: float, user_agent: str, max_bytes: int, allowed_domains: Sequence[str]) -> Response:
        self.calls.append(request.url)
        self.kwargs.append(dict(timeout=timeout, user_agent=user_agent, max_bytes=max_bytes, allowed_domains=tuple(allowed_domains)))
        items = self.script.get(request.url)
        item: Any = 404 if not items else (items.pop(0) if len(items) > 1 else items[0])
        if isinstance(item, FetchError):
            raise item
        if isinstance(item, int):
            if 200 <= item <= 299:
                return Response(request.url, request.url, item, {}, b"", None)
            code, retryable = classify_http_status(item)
            raise FetchError(code, f"HTTP {item} for {request.url}", http_status=item, retryable=retryable)
        if isinstance(item, str):
            item = Response(request.url, request.url, 200, {}, item.encode(), "text/html")
        return item


def page(url: str, body: str | bytes = "<html></html>", *, final_url: str | None = None, status: int = 200) -> Response:
    data = body.encode() if isinstance(body, str) else body
    return Response(url, final_url or url, status, {}, data, "text/html")


def scripted_adapter(parse: Callable[[Response, Request, SourceConfig], ParseResult], *, name: str = "scripted", version: str = "1.2.3"):
    from crawler.adapters import SourceAdapter

    class _Adapter(SourceAdapter):
        def parse(self, response, request, config):  # type: ignore[no-untyped-def]
            return parse(response, request, config)

    _Adapter.name = name  # type: ignore[attr-defined]
    _Adapter.version = version  # type: ignore[attr-defined]
    return _Adapter()


class LocalSite:
    """A tiny HTTP server for fetcher tests. ``routes`` maps path -> (status, headers, body) or a callable."""

    def __init__(self, routes: Mapping[str, Any]) -> None:
        self.routes = dict(routes)
        self.requests: list[dict[str, Any]] = []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                site.requests.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}})
                route = site.routes.get(self.path.split("?")[0])
                if route is None:
                    route = (404, {}, b"not found")
                if callable(route):
                    route = route(self)
                status, headers, body = route
                if body is None:  # hang: the client must time out
                    time.sleep(2.0)
                    body = b""
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> "LocalSite":
        self.thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


__all__ = ["ErrorCode", "FakeClock", "FakeFetcher", "LocalSite", "T0", "fixed_rand", "make_config", "page", "scripted_adapter"]
