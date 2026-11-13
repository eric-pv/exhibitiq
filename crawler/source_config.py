"""Source configuration for crawlers (D1-07).

A source config says *what to fetch and how politely*: which exhibition
source, which URLs, which domains are allowed, rate limit, retries, timeout.
Configs are TOML files (stdlib ``tomllib``, no extra dependency).

Boundaries:
- This is crawler-internal configuration, not part of the shared data
  contract. Values that the contract owns (``exhibition_id``, ``edition_id``,
  ``source_type``) are kept as plain strings here and are validated against
  ``schemas/v1/`` when records and packages are validated, not copied here.
- Secrets never belong in a config file (they would end up in Git); keys that
  look like secrets are rejected.
"""
from __future__ import annotations

import copy
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ConfigError(ValueError):
    """The source configuration is invalid."""


_REQUIRED = ("name", "exhibition_id", "edition_id", "source_type", "start_urls", "allowed_domains")
_OPTIONAL = ("rate_limit_per_second", "max_retries", "timeout_seconds", "user_agent", "adapter", "options")
_ALLOWED_KEYS = frozenset(_REQUIRED + _OPTIONAL)
_SECRET_KEY = re.compile(r"(token|secret|passwd|password|api[_-]?key|credential)", re.IGNORECASE)
_ADAPTER_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_DOMAIN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


@dataclass(frozen=True)
class SourceConfig:
    name: str
    exhibition_id: str
    edition_id: str
    source_type: str
    start_urls: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    rate_limit_per_second: float = 1.0
    max_retries: int = 3
    timeout_seconds: float = 30.0
    user_agent: str = "ExhibitIQ-crawler"
    adapter: str | None = None  # name in the adapter registry; the only place a source picks its behavior
    options: dict[str, Any] = field(default_factory=dict)  # adapter-specific settings (a TOML ``[options]`` table)


def _text(data: Mapping[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _number(data: Mapping[str, Any], key: str, default: float, *, minimum: float, inclusive: bool) -> float:
    if key not in data:
        return default
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be a number")
    ok = value >= minimum if inclusive else value > minimum
    if not ok:
        comparison = ">=" if inclusive else ">"
        raise ConfigError(f"{key} must be {comparison} {minimum}")
    return float(value)


def _non_negative_int(data: Mapping[str, Any], key: str, default: int) -> int:
    if key not in data:
        return default
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigError(f"{key} must be an integer >= 0")
    return value


def _string_list(data: Mapping[str, Any], key: str) -> list[str]:
    value = data[key]
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{key} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ConfigError(f"{key} must contain only non-empty strings")
    return [item.strip() for item in value]


def _host_allowed(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _secret_key_paths(value: Any, prefix: str = "") -> list[str]:
    """Dotted paths of every key (at any depth, including inside lists of tables) that looks like a secret."""
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, inner in value.items():
            path = f"{prefix}{key}"
            if _SECRET_KEY.search(str(key)):
                found.append(path)
            found.extend(_secret_key_paths(inner, path + "."))
    elif isinstance(value, list):
        for inner in value:
            found.extend(_secret_key_paths(inner, prefix))
    return found


def _adapter_and_options(data: Mapping[str, Any]) -> tuple[str | None, dict[str, Any]]:
    adapter = None
    if "adapter" in data:
        adapter = _text(data, "adapter")
        if not _ADAPTER_NAME.fullmatch(adapter):
            raise ConfigError(f"adapter must match {_ADAPTER_NAME.pattern}, got {adapter!r}")
    options = data.get("options", {})
    if not isinstance(options, Mapping) or not all(isinstance(k, str) for k in options):
        raise ConfigError("options must be a table with string keys")
    return adapter, copy.deepcopy(dict(options))  # a deep copy: nested tables must not be shared with the caller


def parse_source_config(data: Mapping[str, Any]) -> SourceConfig:
    """Validate a mapping (already parsed from TOML) and build a SourceConfig."""
    secret_keys = sorted(set(_secret_key_paths(data)))
    if secret_keys:
        raise ConfigError(f"secrets must not be stored in config files (keys: {', '.join(secret_keys)})")
    unknown = sorted(set(data) - _ALLOWED_KEYS)
    if unknown:
        raise ConfigError(f"unknown config keys: {', '.join(unknown)}")
    missing = [k for k in _REQUIRED if k not in data]
    if missing:
        raise ConfigError(f"missing required keys: {', '.join(missing)}")

    domains = tuple(d.lower() for d in _string_list(data, "allowed_domains"))
    for domain in domains:
        if not _DOMAIN.fullmatch(domain):
            raise ConfigError(f"allowed_domains entry must be a bare domain name, got {domain!r}")

    urls = tuple(_string_list(data, "start_urls"))
    for url in urls:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ConfigError(f"start_urls entry must be an http(s) URL, got {url!r}")
        if parts.username is not None or parts.password is not None:
            raise ConfigError("start_urls must not embed credentials")
        if not _host_allowed(parts.hostname.lower(), domains):
            raise ConfigError(f"start_urls host {parts.hostname!r} is not in allowed_domains")

    adapter, options = _adapter_and_options(data)
    return SourceConfig(
        name=_text(data, "name"),
        exhibition_id=_text(data, "exhibition_id"),
        edition_id=_text(data, "edition_id"),
        source_type=_text(data, "source_type"),
        start_urls=urls,
        allowed_domains=domains,
        rate_limit_per_second=_number(data, "rate_limit_per_second", 1.0, minimum=0, inclusive=False),
        max_retries=_non_negative_int(data, "max_retries", 3),
        timeout_seconds=_number(data, "timeout_seconds", 30.0, minimum=0, inclusive=False),
        user_agent=_text(data, "user_agent") if "user_agent" in data else "ExhibitIQ-crawler",
        adapter=adapter,
        options=options,
    )


def load_source_config(path: str | Path) -> SourceConfig:
    """Read a TOML file and return a validated SourceConfig."""
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: invalid TOML: {exc}") from exc
    try:
        return parse_source_config(data)
    except ConfigError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
