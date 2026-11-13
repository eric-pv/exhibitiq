"""robots.txt handling (D2-01), following RFC 9309 with one extra caution.

How a ``robots.txt`` fetch result is interpreted:

| result                                   | meaning                                                         |
|------------------------------------------|-----------------------------------------------------------------|
| 2xx                                      | parse it; its rules (and ``Crawl-delay``) apply                 |
| 404, 410 and other 4xx                   | no robots.txt: everything is allowed                            |
| **401, 403, 429**                        | access denied: treat as *disallow all* (more cautious than RFC) |
| 5xx, network error, timeout              | unreachable: treat as *disallow all* (RFC 9309 §2.3.1.4)        |

This module only interprets bytes and errors; fetching (with rate limiting, retries and accounting)
is done by the runner. A site's terms of use are judged in the source assessment (D1-11); robots.txt
is one input to it, and the framework honors it by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.robotparser import RobotFileParser

from crawler.fetch import FetchError


@dataclass(frozen=True)
class RobotsRules:
    reason: str
    mode: str  # "allow_all", "disallow_all" or "rules"
    crawl_delay: float | None = None
    _parser: RobotFileParser | None = None

    def allows(self, url: str, user_agent: str) -> bool:
        if self.mode == "allow_all":
            return True
        if self.mode == "disallow_all":
            return False
        assert self._parser is not None
        return self._parser.can_fetch(user_agent, url)


def allow_all(reason: str) -> RobotsRules:
    return RobotsRules(reason=reason, mode="allow_all")


def disallow_all(reason: str) -> RobotsRules:
    return RobotsRules(reason=reason, mode="disallow_all")


def rules_from_text(text: str, user_agent: str, *, max_crawl_delay: float) -> RobotsRules:
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    delay = parser.crawl_delay(user_agent)
    capped = None if delay is None else min(float(delay), max_crawl_delay)
    return RobotsRules(reason="robots.txt rules", mode="rules", crawl_delay=capped, _parser=parser)


def rules_from_failure(error: FetchError) -> RobotsRules:
    status = error.http_status
    if status in (401, 403, 429):
        return disallow_all(f"robots.txt access denied (HTTP {status})")
    if status is not None and 400 <= status < 500:
        return allow_all(f"no robots.txt (HTTP {status})")
    return disallow_all(f"robots.txt unavailable: {error.message}")
