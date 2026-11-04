"""Source adapters and their registry (D2-01).

An adapter is the **only** place where one kind of source differs from another: how its
pages are laid out, how to find the next page, how to read a row. Everything every source
shares (rate limiting, retries, domain scope, robots.txt, error handling, provenance, logging)
lives in the runner and must not be re-implemented in an adapter.

An adapter is selected by name from a source config (``adapter = "..."``). Adding a new
exhibition therefore means adding a config, and at most one adapter; it never means editing
the framework (V2.3). Adapters must not hard-code an exhibition's name, ID or URL.

    @registry.register
    class HtmlTable(SourceAdapter):
        name = "html-table"
        def parse(self, response, request, config): ...
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar

from crawler.models import ParseResult, Request, Response
from crawler.source_config import ConfigError, SourceConfig

_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ParseError(Exception):
    """An adapter could not read a response (unexpected layout, empty page, ...). The run continues."""


class AdapterError(ConfigError):
    """The adapter registry was used incorrectly (duplicate or unknown name, not an adapter)."""


class SourceAdapter(ABC):
    name: ClassVar[str]
    version: ClassVar[str] = "0.0.0"

    def validate_options(self, options: Mapping[str, Any]) -> None:
        """Reject bad ``[options]`` early (raise ``ConfigError``). The default accepts anything."""

    def start_requests(self, config: SourceConfig) -> Iterable[Request]:
        """The first requests of a run. The default is ``config.start_urls``."""
        return [Request(url) for url in config.start_urls]

    @abstractmethod
    def parse(self, response: Response, request: Request, config: SourceConfig) -> ParseResult:
        """Read one response. Raise ``ParseError`` for a page that cannot be read; do not perform I/O here."""


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, type[SourceAdapter]] = {}

    def register(self, adapter: type[SourceAdapter] | None = None, *, name: str | None = None) -> Any:
        """Register an adapter class; usable as ``@registry.register`` or ``@registry.register(name="x")``."""

        def apply(cls: type[SourceAdapter]) -> type[SourceAdapter]:
            if not (isinstance(cls, type) and issubclass(cls, SourceAdapter)):
                raise AdapterError(f"{cls!r} is not a SourceAdapter subclass")
            adapter_name = name or getattr(cls, "name", None)
            if not isinstance(adapter_name, str) or not _NAME.fullmatch(adapter_name):
                raise AdapterError(f"adapter name must match {_NAME.pattern}, got {adapter_name!r}")
            if adapter_name in self._adapters:
                raise AdapterError(f"an adapter named {adapter_name!r} is already registered")
            self._adapters[adapter_name] = cls
            return cls

        return apply(adapter) if adapter is not None else apply

    def get(self, name: str) -> type[SourceAdapter]:
        try:
            return self._adapters[name]
        except KeyError:
            raise AdapterError(f"no adapter named {name!r}; registered: {', '.join(self.names()) or '(none)'}") from None

    def create(self, name: str) -> SourceAdapter:
        return self.get(name)()

    def names(self) -> list[str]:
        return sorted(self._adapters)

    def __contains__(self, name: object) -> bool:
        return name in self._adapters

    def __len__(self) -> int:
        return len(self._adapters)


# The registry that built-in adapters (D2-02, D2-04) register into. Tests use their own instances.
default_registry = AdapterRegistry()


def resolve_adapter(config: SourceConfig, registry: AdapterRegistry) -> SourceAdapter:
    """The adapter a config asks for, with its options validated. Raises ``ConfigError`` (incl. ``AdapterError``)."""
    if config.adapter is None:
        raise ConfigError(f"source {config.name!r} does not name an adapter (add adapter = \"...\")")
    adapter = registry.create(config.adapter)
    adapter.validate_options(config.options)
    return adapter

