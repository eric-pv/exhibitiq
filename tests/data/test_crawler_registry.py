"""Tests for crawler.adapters and crawler.sources (D2-01): the adapter registry and the source registry."""
from __future__ import annotations

from pathlib import Path

import pytest

from crawler.adapters import AdapterError, AdapterRegistry, ParseError, SourceAdapter, default_registry, resolve_adapter
from crawler.models import ParseResult, Request, Response
from crawler.source_config import ConfigError, SourceConfig
from crawler.sources import SourceRegistry


class Noop(SourceAdapter):
    name = "noop"

    def parse(self, response, request, config):
        return ParseResult()


def config(name: str = "example-source", exhibition: str = "example-expo", **kw) -> SourceConfig:
    base = dict(
        name=name, exhibition_id=exhibition, edition_id=f"{exhibition}-2026", source_type="official_exhibitor_list",
        start_urls=("https://www.example.com/a", "https://www.example.com/b"), allowed_domains=("example.com",),
    )
    base.update(kw)
    return SourceConfig(**base)


def toml(name: str, exhibition: str = "example-expo", extra: str = "") -> str:
    return (
        f'name = "{name}"\nexhibition_id = "{exhibition}"\nedition_id = "{exhibition}-2026"\n'
        'source_type = "official_exhibitor_list"\nstart_urls = ["https://www.example.com/x"]\n'
        f'allowed_domains = ["example.com"]\n{extra}'
    )


# --- adapter registry ----------------------------------------------------------------------


def test_register_as_a_plain_decorator_and_with_an_explicit_name() -> None:
    registry = AdapterRegistry()

    @registry.register
    class A(SourceAdapter):
        name = "alpha"

        def parse(self, response, request, config):
            return ParseResult()

    @registry.register(name="beta-two")
    class B(SourceAdapter):
        def parse(self, response, request, config):
            return ParseResult()

    assert registry.names() == ["alpha", "beta-two"] and "alpha" in registry and len(registry) == 2
    assert registry.get("alpha") is A and isinstance(registry.create("beta-two"), B)


def test_registries_are_independent_and_the_default_one_starts_empty_of_test_adapters() -> None:
    one, two = AdapterRegistry(), AdapterRegistry()
    one.register(Noop)
    assert one.names() == ["noop"] and two.names() == []
    assert "noop" not in default_registry


def test_duplicate_unknown_and_invalid_registrations_are_errors() -> None:
    registry = AdapterRegistry()
    registry.register(Noop)
    with pytest.raises(AdapterError, match="already registered"):
        registry.register(Noop)
    with pytest.raises(AdapterError, match="no adapter named 'missing'.*noop"):
        registry.get("missing")
    with pytest.raises(AdapterError, match="not a SourceAdapter"):
        registry.register(dict)  # type: ignore[arg-type]
    for bad in ("Has Space", "UPPER", "1x", "", "a" * 65):
        with pytest.raises(AdapterError, match="adapter name"):
            registry.register(name=bad)(type("X", (SourceAdapter,), {"parse": lambda s, r, q, c: ParseResult()}))


def test_adapter_error_is_a_config_error() -> None:
    assert issubclass(AdapterError, ConfigError)


def test_an_adapter_without_parse_cannot_be_instantiated() -> None:
    class Incomplete(SourceAdapter):
        name = "incomplete"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_default_start_requests_are_the_config_start_urls() -> None:
    requests = list(Noop().start_requests(config()))
    assert [r.url for r in requests] == ["https://www.example.com/a", "https://www.example.com/b"]
    assert all(isinstance(r, Request) for r in requests)


def test_resolve_adapter_validates_options_and_requires_a_name() -> None:
    class Strict(Noop):
        name = "strict"

        def validate_options(self, options):
            if "columns" not in options:
                raise ConfigError("columns is required")

    registry = AdapterRegistry()
    registry.register(Strict)
    assert isinstance(resolve_adapter(config(adapter="strict", options={"columns": {}}), registry), Strict)
    with pytest.raises(ConfigError, match="columns is required"):
        resolve_adapter(config(adapter="strict"), registry)
    with pytest.raises(ConfigError, match="does not name an adapter"):
        resolve_adapter(config(), registry)
    with pytest.raises(AdapterError, match="no adapter named"):
        resolve_adapter(config(adapter="nope"), registry)


def test_parse_error_and_models_are_importable_values() -> None:
    assert issubclass(ParseError, Exception)
    response = Response(url="u", final_url="u", status=200, headers={}, content=b"x")
    assert response.media_type is None


# --- source registry -----------------------------------------------------------------------


def test_source_registry_lookup_and_filtering() -> None:
    registry = SourceRegistry([config("b-source", "expo-b"), config("a-source", "expo-a"), config("c-source", "expo-a")])
    assert registry.names() == ["a-source", "b-source", "c-source"] and len(registry) == 3
    assert [c.name for c in registry] == ["a-source", "b-source", "c-source"]
    assert [c.name for c in registry.for_exhibition("expo-a")] == ["a-source", "c-source"]
    assert registry.for_exhibition("none") == []
    assert registry.get("b-source").exhibition_id == "expo-b" and "b-source" in registry
    with pytest.raises(ConfigError, match="no source named 'x'"):
        registry.get("x")


def test_duplicate_source_names_are_rejected() -> None:
    with pytest.raises(ConfigError, match="already registered"):
        SourceRegistry([config("same"), config("same", "other")])


def test_load_dir_finds_toml_files_recursively_in_a_deterministic_order(tmp_path: Path) -> None:
    (tmp_path / "expo-b").mkdir()
    (tmp_path / "expo-a" / "nested").mkdir(parents=True)
    (tmp_path / "expo-b" / "z.toml").write_text(toml("z-source", "expo-b"), encoding="utf-8")
    (tmp_path / "expo-a" / "nested" / "a.toml").write_text(toml("a-source", "expo-a"), encoding="utf-8")
    (tmp_path / "expo-a" / "readme.md").write_text("not a config", encoding="utf-8")
    registry = SourceRegistry.load_dir(tmp_path)
    assert registry.names() == ["a-source", "z-source"]
    assert registry.get("a-source").exhibition_id == "expo-a"


def test_load_dir_reports_every_problem_at_once(tmp_path: Path) -> None:
    (tmp_path / "ok.toml").write_text(toml("ok-source"), encoding="utf-8")
    (tmp_path / "bad1.toml").write_text(toml("bad-one", extra='surprise = 1\n'), encoding="utf-8")
    (tmp_path / "bad2.toml").write_text("name = ", encoding="utf-8")
    (tmp_path / "dup.toml").write_text(toml("ok-source", "other-expo"), encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        SourceRegistry.load_dir(tmp_path)
    message = str(info.value)
    assert message.startswith("3 invalid source config(s):")
    assert "bad1.toml" in message and "bad2.toml" in message and "dup.toml" in message and "already defined" in message


def test_load_dir_with_adapters_checks_the_adapter_and_its_options(tmp_path: Path) -> None:
    class NeedsColumns(Noop):
        name = "needs-columns"

        def validate_options(self, options):
            if "columns" not in options:
                raise ConfigError("columns is required")

    adapters = AdapterRegistry()
    adapters.register(NeedsColumns)
    (tmp_path / "good.toml").write_text(toml("good", extra='adapter = "needs-columns"\n[options]\ncolumns = ["name"]\n'), encoding="utf-8")
    assert SourceRegistry.load_dir(tmp_path, adapters=adapters).names() == ["good"]
    (tmp_path / "noopts.toml").write_text(toml("no-opts", extra='adapter = "needs-columns"\n'), encoding="utf-8")
    (tmp_path / "unknown.toml").write_text(toml("unknown", extra='adapter = "nope"\n'), encoding="utf-8")
    (tmp_path / "noadapter.toml").write_text(toml("no-adapter"), encoding="utf-8")
    with pytest.raises(ConfigError) as info:
        SourceRegistry.load_dir(tmp_path, adapters=adapters)
    message = str(info.value)
    assert message.startswith("3 invalid") and "columns is required" in message and "no adapter named" in message and "does not name an adapter" in message


def test_load_dir_rejects_a_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a directory"):
        SourceRegistry.load_dir(tmp_path / "absent")
    (tmp_path / "file.toml").write_text(toml("x"), encoding="utf-8")
    with pytest.raises(ConfigError, match="not a directory"):
        SourceRegistry.load_dir(tmp_path / "file.toml")
