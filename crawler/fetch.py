"""Fetching one URL, safely (D2-01).

``Fetcher`` is the interface the runner uses; ``UrllibFetcher`` implements it with the standard
library only (no extra dependency). Safety rules it enforces, because configs will be written by
people and by workflows (D2-13) and must never become a way to reach things they should not:

- Only ``http``/``https``; the host must be inside ``allowed_domains``; **every redirect hop is
  checked again** (a redirect that leaves the allowed domains is refused).
- By default the host must resolve to **public** addresses only: loopback, private ranges,
  link-local (cloud metadata services live there) and other non-global addresses are refused.
  Residual risk: the name is resolved once to check and again to connect (DNS rebinding), and a
  configured HTTP proxy resolves names itself; neither is covered here.
- No credentials: ``Authorization``, ``Cookie`` and ``Proxy-Authorization`` headers are refused.
  Logging in is not an acquisition method (see the assessment process).
- Plain ``Accept-Encoding: identity`` (no compression, so no decompression bombs) and a hard cap on
  the body size.
- 401/403/429 are ``access_blocked``: the caller must stop and report, never retry or work around.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol
from urllib.parse import urlsplit

from crawler.errors import RETRYABLE_BY_DEFAULT, ErrorCode
from crawler.models import Request, Response

FORBIDDEN_REQUEST_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization"})


class FetchError(Exception):
    """A request failed. ``code`` is a crawler error code; ``retryable`` says whether retrying may help."""

    def __init__(self, code: ErrorCode, message: str, *, http_status: int | None = None, retryable: bool | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = RETRYABLE_BY_DEFAULT[code] if retryable is None else retryable


def classify_http_status(status: int) -> tuple[ErrorCode, bool]:
    """(error code, retryable) for an HTTP status that is not a success."""
    if status in (401, 403, 429):
        return ErrorCode.ACCESS_BLOCKED, False  # login required, forbidden, rate limited: stop, never evade
    if status == 408:
        return ErrorCode.TIMEOUT, True
    if 500 <= status <= 599:
        return ErrorCode.HTTP_ERROR, True
    return ErrorCode.HTTP_ERROR, False


def host_in_domains(host: str | None, domains: Sequence[str]) -> bool:
    if not host:
        return False
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in domains)


class Fetcher(Protocol):
    def fetch(self, request: Request, *, timeout: float, user_agent: str, max_bytes: int, allowed_domains: Sequence[str]) -> Response:
        """Return the response for a 2xx status; raise ``FetchError`` for everything else."""


class _ScopedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = 5

    def __init__(self, check: Callable[[str], None]) -> None:
        self._check = check

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        self._check(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibFetcher:
    def __init__(
        self,
        *,
        allow_private_networks: bool = False,
        proxies: Mapping[str, str] | None = None,
        resolver: Callable[..., Any] = socket.getaddrinfo,
    ) -> None:
        """``allow_private_networks`` is for tests that talk to a local server; never enable it in production.
        ``proxies=None`` uses the proxies from the environment; ``{}`` uses none."""
        self.allow_private_networks = allow_private_networks
        self._proxies = proxies
        self._resolver = resolver

    # ---------------------------------------------------------------- checks
    def _check_url(self, url: str, allowed_domains: Sequence[str]) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError(ErrorCode.CONFIG_INVALID, f"only http(s) URLs with a host can be fetched, got {url!r}")
        if parts.username is not None or parts.password is not None:
            raise FetchError(ErrorCode.CONFIG_INVALID, "URLs must not embed credentials")
        if not host_in_domains(parts.hostname, allowed_domains):
            raise FetchError(ErrorCode.CONFIG_INVALID, f"{parts.hostname} is not inside allowed_domains")
        self._check_public(parts.hostname, parts.port)

    def _check_public(self, host: str, port: int | None) -> None:
        if self.allow_private_networks:
            return
        try:
            infos = self._resolver(host, port or 0, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise FetchError(ErrorCode.NETWORK_ERROR, f"cannot resolve {host}: {exc}") from exc
        for info in infos:
            ip = ipaddress.ip_address(str(info[4][0]).split("%")[0])
            if not ip.is_global:
                raise FetchError(ErrorCode.CONFIG_INVALID, f"{host} resolves to a non-public address ({ip}); refusing to fetch")

    # ---------------------------------------------------------------- fetch
    def fetch(self, request: Request, *, timeout: float, user_agent: str, max_bytes: int, allowed_domains: Sequence[str]) -> Response:
        self._check_url(request.url, allowed_domains)
        headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.5", "Accept-Encoding": "identity"}
        for name, value in request.headers.items():
            if name.lower() in FORBIDDEN_REQUEST_HEADERS:
                raise FetchError(ErrorCode.CONFIG_INVALID, f"the {name} header is not allowed: acquisition never sends credentials")
            headers[name] = value

        handlers: list[Any] = [_ScopedRedirects(lambda new: self._check_url(new, allowed_domains))]
        if self._proxies is not None:
            handlers.insert(0, urllib.request.ProxyHandler(dict(self._proxies)))
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(urllib.request.Request(request.url, headers=headers, method="GET"), timeout=timeout) as raw:
                body = raw.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FetchError(ErrorCode.HTTP_ERROR, f"response is larger than max_bytes ({max_bytes})", http_status=raw.status, retryable=False)
                header_map = {k.lower(): v for k, v in raw.headers.items()}
                content_type = header_map.get("content-type")
                return Response(
                    url=request.url,
                    final_url=raw.geturl(),
                    status=raw.status,
                    headers=header_map,
                    content=body,
                    media_type=content_type.split(";")[0].strip().lower() if content_type else None,
                )
        except FetchError:
            raise
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code <= 399:  # urllib refused to follow it (loop, too many hops, non-http target)
                raise FetchError(ErrorCode.CONFIG_INVALID, f"redirect not followed (HTTP {exc.code}) for {request.url}", http_status=exc.code) from exc
            code, retryable = classify_http_status(exc.code)
            raise FetchError(code, f"HTTP {exc.code} for {request.url}", http_status=exc.code, retryable=retryable) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise FetchError(ErrorCode.TIMEOUT, f"timed out after {timeout}s: {request.url}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise FetchError(ErrorCode.TIMEOUT, f"timed out after {timeout}s: {request.url}") from exc
            raise FetchError(ErrorCode.NETWORK_ERROR, f"network error for {request.url}: {exc.reason}") from exc
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            raise FetchError(ErrorCode.NETWORK_ERROR, f"network error for {request.url}: {exc}") from exc
