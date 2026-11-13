"""File import as a first-class acquisition method (D2-04).

``FileImportAdapter`` ("file-import") reads CSV / HTML-table / Excel / PDF-text files with a mapping
given in the source config (``[options.mapping]``, see ``importers.py``). It plugs into the same runner
as web sources, so an imported file gets the same treatment: an immutable snapshot with sha256 and
timestamp, a ``crawl_run`` record, structured errors and the log.

Files that are already in the repository (or were attached to a PR) are served to the runner by
``LocalFileFetcher``: it maps the **origin URL** the file was obtained from to the local file. The
origin URL is what the ``source`` record cites (the Schema requires an ``http(s)`` URL for everything
but manual entry); the fetcher never touches the network. ``import_files`` is the one-call entry point.
"""
from __future__ import annotations

import mimetypes
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from crawler.adapters import AdapterRegistry, SourceAdapter, default_registry
from crawler.clock import Clock
from crawler.errors import ErrorCode
from crawler.fetch import FetchError
from crawler.importers import ImportMapping, mapping_from_dict, read_rows
from crawler.models import ParseResult, Request, Response
from crawler.runner import RunOptions, RunResult, run_source
from crawler.source_config import ConfigError, SourceConfig

ADAPTER_NAME = "file-import"
_MEDIA_TYPES = {".csv": "text/csv", ".html": "text/html", ".htm": "text/html", ".pdf": "application/pdf",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


class FileImportAdapter(SourceAdapter):
    name = ADAPTER_NAME
    version = "1.0.0"

    def validate_options(self, options: Mapping[str, Any]) -> None:
        unknown = sorted(set(options) - {"mapping"})
        if unknown:
            raise ConfigError(f"file-import: unknown option(s): {', '.join(unknown)}")
        if "mapping" not in options:
            raise ConfigError("file-import: [options.mapping] is required")
        mapping_from_dict(options["mapping"])

    def parse(self, response: Response, request: Request, config: SourceConfig) -> ParseResult:
        mapping = mapping_from_dict(config.options["mapping"])
        imported = read_rows(response.content, mapping)
        return ParseResult(records=imported.rows, warnings=imported.warnings)


def register_file_import(registry: AdapterRegistry | None = None) -> None:
    """Register the adapter (idempotent for the shared registry)."""
    target = registry or default_registry
    if ADAPTER_NAME not in target:
        target.register(FileImportAdapter)


register_file_import()


class LocalFileFetcher:
    """Serves local files under their origin URLs. Any other URL is a 404; no network access at all."""

    def __init__(self, files: Mapping[str, str | Path]) -> None:
        self._files = {url: Path(path) for url, path in files.items()}

    def fetch(self, request: Request, *, timeout: float, user_agent: str, max_bytes: int, allowed_domains: Sequence[str]) -> Response:
        path = self._files.get(request.url)
        if path is None:
            raise FetchError(ErrorCode.HTTP_ERROR, f"no local file registered for {request.url}", http_status=404, retryable=False)
        try:
            size = path.stat().st_size
            if size > max_bytes:
                raise FetchError(ErrorCode.HTTP_ERROR, f"{path.name} is larger than max_bytes ({max_bytes})", retryable=False)
            content = path.read_bytes()
        except OSError as exc:
            raise FetchError(ErrorCode.HTTP_ERROR, f"cannot read {path.name}: {exc.strerror or exc}", retryable=False) from exc
        media_type = _MEDIA_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
        return Response(request.url, request.url, 200, {}, content, media_type)


def import_files(
    config: SourceConfig,
    files: Mapping[str, str | Path],
    *,
    adapters: AdapterRegistry | None = None,
    clock: Clock | None = None,
    options: RunOptions | None = None,
    **kwargs: Any,
) -> RunResult:
    """Import local files described by ``config`` (adapter ``file-import``). ``files`` maps origin URL -> local path.

    Every file URL must be one of ``config.start_urls``; the run's trigger is ``import`` and robots.txt is not
    consulted (nothing is requested over the network).
    """
    from crawler.adapters import resolve_adapter

    registry = adapters or default_registry
    adapter = resolve_adapter(config, registry)
    stray = sorted(set(files) - set(config.start_urls))
    if stray:
        raise ConfigError(f"file URL(s) not in start_urls: {', '.join(stray)}")
    base = options or RunOptions()
    run_options = RunOptions(**{**base.__dict__, "respect_robots": False, "trigger": "import"})
    return run_source(config, adapter, LocalFileFetcher(files), clock=clock, options=run_options, **kwargs)


__all__ = ["ADAPTER_NAME", "FileImportAdapter", "LocalFileFetcher", "ImportMapping", "import_files", "register_file_import"]
