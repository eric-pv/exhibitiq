"""Run log for crawl runs (D1-07).

Two outputs, deliberately separate:

1. A JSONL event log (one canonical JSON object per line) for humans and
   GitHub Actions logs. Its format is defined here by data engineering; the
   shared contract only says the *detailed* log format is up to us.
2. A ``crawl_run`` record built from the counters, in the exact shape of the
   shared contract (``schemas/v1/crawl_run.schema.json``). Only finished runs
   are recorded, so ``finished_at`` and ``status`` are supplied by the caller.

This module does not generate IDs (``crawl_run_id`` is assigned when a run
starts, by the caller) and does no network I/O.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, TextIO

from crawler.errors import CrawlError

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
RESERVED_FIELDS = frozenset({"ts", "level", "event", "message"})
# crawl_run.error_samples allows at most 50 items; a contract test guards this.
MAX_ERROR_SAMPLES = 50


def format_utc(moment: datetime) -> str:
    """UTC RFC 3339 with a trailing Z, e.g. 2026-11-03T06:00:00Z."""
    if moment.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunLog:
    def __init__(self, stream: TextIO, *, clock: Callable[[], datetime] = _now) -> None:
        self._stream = stream
        self._clock = clock
        self._requests_attempted = 0
        self._requests_succeeded = 0
        self._records_extracted = 0
        self._error_count = 0
        self._error_samples: list[dict[str, str]] = []

    def event(self, level: str, name: str, message: str | None = None, **fields: Any) -> None:
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}, got {level!r}")
        clash = RESERVED_FIELDS & fields.keys()
        if clash:
            raise ValueError(f"reserved log fields cannot be used: {', '.join(sorted(clash))}")
        line: dict[str, Any] = {"ts": format_utc(self._clock()), "level": level, "event": name}
        if message is not None:
            line["message"] = message
        line.update(fields)
        self._stream.write(json.dumps(line, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        self._stream.flush()

    def log_request(self, url: str, *, succeeded: bool, http_status: int | None = None) -> None:
        self._requests_attempted += 1
        if succeeded:
            self._requests_succeeded += 1
        fields: dict[str, Any] = {"url": url, "succeeded": succeeded}
        if http_status is not None:
            fields["http_status"] = http_status
        self.event("INFO" if succeeded else "WARNING", "request", **fields)

    def log_records(self, count: int, **fields: Any) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("count must be a non-negative integer")
        self._records_extracted += count
        self.event("INFO", "records_extracted", count=count, **fields)

    def log_error(self, error: CrawlError) -> None:
        if error.occurred_at is None:
            error = replace(error, occurred_at=format_utc(self._clock()))
        self._error_count += 1
        if len(self._error_samples) < MAX_ERROR_SAMPLES:
            self._error_samples.append(error.to_error_sample())
        self.event("ERROR", "error", error.message, **error.to_log_fields())

    def stats(self) -> dict[str, int]:
        return {
            "requests_attempted": self._requests_attempted,
            "requests_succeeded": self._requests_succeeded,
            "records_extracted": self._records_extracted,
            "error_count": self._error_count,
        }

    def error_samples(self) -> list[dict[str, str]]:
        return list(self._error_samples)

    def build_crawl_run(
        self,
        *,
        crawl_run_id: str,
        exhibition_id: str,
        edition_id: str,
        crawler_name: str,
        crawler_version: str,
        trigger: str,
        started_at: datetime,
        finished_at: datetime,
        status: str,
        code_commit: str | None = None,
        github_run_url: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Build a ``crawl_run`` record. Optional fields are omitted when absent (never null).

        ``status`` is chosen by the caller; this module does not guess what
        counts as ``succeeded`` or ``partial``. Final validation against the
        shared Schema is done by the data-package validator.
        """
        record: dict[str, Any] = {
            "crawl_run_id": crawl_run_id,
            "exhibition_id": exhibition_id,
            "edition_id": edition_id,
            "crawler": {"name": crawler_name, "version": crawler_version},
            "trigger": trigger,
            "started_at": format_utc(started_at),
            "finished_at": format_utc(finished_at),
            "status": status,
            "stats": self.stats(),
        }
        if self._error_samples:
            record["error_samples"] = self.error_samples()
        for key, value in (("code_commit", code_commit), ("github_run_url", github_run_url), ("notes", notes)):
            if value is not None:
                record[key] = value
        return record
