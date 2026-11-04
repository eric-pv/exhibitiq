"""The source registry: every source config the system knows (D2-01).

Source configs are TOML files (``crawler.source_config``). The registry does not decide where they
live: ``load_dir`` takes a directory and finds every ``*.toml`` below it. Where exhibition data and
its configs are stored is decided elsewhere (the exhibition registry, D2-13); this module only needs
a path. Nothing here knows any exhibition.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from crawler.adapters import AdapterRegistry, resolve_adapter
from crawler.source_config import ConfigError, SourceConfig, load_source_config


class SourceRegistry:
    def __init__(self, configs: Iterable[SourceConfig] = ()) -> None:
        self._configs: dict[str, SourceConfig] = {}
        for config in configs:
            self.add(config)

    def add(self, config: SourceConfig) -> None:
        if config.name in self._configs:
            raise ConfigError(f"a source named {config.name!r} is already registered")
        self._configs[config.name] = config

    @classmethod
    def load_dir(cls, directory: str | Path, *, adapters: AdapterRegistry | None = None) -> "SourceRegistry":
        """Load every ``*.toml`` below ``directory`` (sorted, so the result is deterministic).

        All problems are collected and reported together. With ``adapters``, each config's adapter
        must exist and accept its options.
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise ConfigError(f"{directory} is not a directory")
        registry = cls()
        problems: list[str] = []
        owners: dict[str, Path] = {}
        for path in sorted(directory.rglob("*.toml")):
            try:
                config = load_source_config(path)
                if adapters is not None:
                    resolve_adapter(config, adapters)
                if config.name in owners:
                    raise ConfigError(f"{path}: source name {config.name!r} is already defined in {owners[config.name]}")
                registry.add(config)
                owners[config.name] = path
            except ConfigError as exc:
                text = str(exc)
                problems.append(text if str(path) in text else f"{path}: {text}")
        if problems:
            raise ConfigError(f"{len(problems)} invalid source config(s):\n" + "\n".join(f"- {p}" for p in problems))
        return registry

    def get(self, name: str) -> SourceConfig:
        try:
            return self._configs[name]
        except KeyError:
            raise ConfigError(f"no source named {name!r}; known: {', '.join(self.names()) or '(none)'}") from None

    def names(self) -> list[str]:
        return sorted(self._configs)

    def for_exhibition(self, exhibition_id: str) -> list[SourceConfig]:
        return [self._configs[n] for n in self.names() if self._configs[n].exhibition_id == exhibition_id]

    def __iter__(self) -> Iterator[SourceConfig]:
        return (self._configs[n] for n in self.names())

    def __len__(self) -> int:
        return len(self._configs)

    def __contains__(self, name: object) -> bool:
        return name in self._configs
