"""Resuming an earlier run (D2-05): fetch only what that run could not.

A resume is a **new run** (new ``crawl_run_id``, new snapshots, its own ``crawl_run`` record whose notes
say which run it continues). It never re-fetches pages the earlier run already retrieved, and it never
rewrites the earlier run's directory (evidence is immutable). The data of an exhibition is the union of
its runs; combining them is the data package's job (D2-11).

URLs a resume fetches:

- everything in the earlier run's ``pending.json`` (found but not fetched: ``max_requests``, cancel), and
- URLs whose error may have been temporary: ``network_error``, ``timeout`` and ``http_error`` with a 5xx
  status or none.

Never resumed: ``access_blocked`` (a URL robots.txt forbids is skipped again; a source that answered 401/403/429 is not
asked again automatically), ``config_invalid``, ``parse_error`` (fetching again cannot fix a parser) and
``unexpected``. A previous run that was blocked cannot be resumed at all.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from crawler.source_config import SourceConfig

_RUN_DIR = re.compile(r"^run_[0-7][0-9A-HJKMNP-TV-Z]{25}$")
_RETRY_CODES = {"network_error", "timeout"}


class ResumeError(Exception):
    """The earlier run cannot be resumed (not found, other source, blocked, nothing left to do)."""


@dataclass(frozen=True)
class ResumePlan:
    crawl_run_id: str
    urls: tuple[str, ...]
    reasons: dict[str, str] = field(default_factory=dict)  # url -> "pending" or the error code


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResumeError(f"cannot read {path.name}: {exc}") from None


def plan_resume(run_dir: str | Path, config: SourceConfig) -> ResumePlan:
    directory = Path(run_dir)
    if not _RUN_DIR.fullmatch(directory.name):
        raise ResumeError(f"{directory.name!r} is not a run directory name")
    if not directory.is_dir() or not (directory / "crawl_run.json").is_file():
        raise ResumeError(f"{directory} is not a finished run (crawl_run.json missing)")
    record = _load(directory / "crawl_run.json")
    if not isinstance(record, dict) or record.get("crawl_run_id") != directory.name:
        raise ResumeError("crawl_run.json does not match the directory name")
    if (record.get("exhibition_id"), record.get("edition_id")) != (config.exhibition_id, config.edition_id):
        raise ResumeError(f"that run belongs to {record.get('edition_id')!r}, not to {config.edition_id!r}")
    errors = _load(directory / "errors.json")
    pending = _load(directory / "pending.json") if (directory / "pending.json").is_file() else []
    if not isinstance(errors, list) or not isinstance(pending, list):
        raise ResumeError("errors.json / pending.json are malformed")
    if any(isinstance(e, dict) and e.get("code") == "access_blocked" and e.get("http_status") is not None for e in errors):
        raise ResumeError("the earlier run was blocked by the site (HTTP 401/403/429); the source is not asked again automatically. Review the source assessment first")
    reasons: dict[str, str] = {}
    for url in pending:
        if isinstance(url, str):
            reasons[url] = "pending"
    for error in errors:
        if not isinstance(error, dict) or not isinstance(error.get("url"), str):
            continue
        code, status = error.get("code"), error.get("http_status")
        if code in _RETRY_CODES or (code == "http_error" and (status is None or (isinstance(status, int) and status >= 500))):
            reasons.setdefault(error["url"], str(code))
    if not reasons:
        raise ResumeError("nothing to resume: the earlier run has no pending or temporarily failed URLs")
    return ResumePlan(crawl_run_id=directory.name, urls=tuple(sorted(reasons)), reasons=reasons)
