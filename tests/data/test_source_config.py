"""Tests for crawler.source_config (D1-07). Synthetic values only."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from crawler.source_config import ConfigError, SourceConfig, load_source_config, parse_source_config


def valid() -> dict:
    return {
        "name": "example-crawler",
        "exhibition_id": "example-expo",
        "edition_id": "example-expo-2026",
        "source_type": "official_exhibitor_list",
        "start_urls": ["https://www.example.com/exhibitors"],
        "allowed_domains": ["example.com"],
    }


def test_valid_config_gets_conservative_defaults() -> None:
    cfg = parse_source_config(valid())
    assert isinstance(cfg, SourceConfig)
    assert cfg.start_urls == ("https://www.example.com/exhibitors",)
    assert (cfg.rate_limit_per_second, cfg.max_retries, cfg.timeout_seconds) == (1.0, 3, 30.0)
    assert cfg.user_agent == "ExhibitIQ-crawler"


def test_config_is_immutable() -> None:
    cfg = parse_source_config(valid())
    with pytest.raises(FrozenInstanceError):
        cfg.name = "other"  # type: ignore[misc]


def test_optional_values_are_applied() -> None:
    data = valid() | {"rate_limit_per_second": 0.5, "max_retries": 0, "timeout_seconds": 10, "user_agent": "X"}
    cfg = parse_source_config(data)
    assert (cfg.rate_limit_per_second, cfg.max_retries, cfg.timeout_seconds, cfg.user_agent) == (0.5, 0, 10.0, "X")


def test_subdomain_is_allowed_and_domains_are_lowercased() -> None:
    data = valid() | {"allowed_domains": ["Example.COM"], "start_urls": ["https://a.b.example.com/x"]}
    assert parse_source_config(data).allowed_domains == ("example.com",)


@pytest.mark.parametrize(
    "change, fragment",
    [
        ({"surprise": 1}, "unknown config keys"),
        ({"api_key": "x"}, "secrets must not be stored"),
        ({"Auth_Token": "x"}, "secrets must not be stored"),
        ({"start_urls": ["ftp://www.example.com/x"]}, "http(s)"),
        ({"start_urls": ["https://user:pw@www.example.com/x"]}, "credentials"),
        ({"start_urls": ["https://www.example.org/x"]}, "not in allowed_domains"),
        ({"start_urls": ["https://notexample.com/x"]}, "not in allowed_domains"),
        ({"start_urls": []}, "non-empty list"),
        ({"allowed_domains": ["https://example.com"]}, "bare domain"),
        ({"allowed_domains": ["localhost"]}, "bare domain"),
        ({"name": "  "}, "name must be a non-empty string"),
        ({"max_retries": True}, "max_retries"),
        ({"max_retries": 1.5}, "max_retries"),
        ({"max_retries": -1}, "max_retries"),
        ({"rate_limit_per_second": 0}, "rate_limit_per_second"),
        ({"timeout_seconds": "30"}, "timeout_seconds"),
    ],
)
def test_invalid_configs_are_rejected(change: dict, fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment.replace("(", r"\(").replace(")", r"\)")):
        parse_source_config(valid() | change)


@pytest.mark.parametrize("missing", sorted(valid()))
def test_each_required_key_is_required(missing: str) -> None:
    data = valid()
    del data[missing]
    with pytest.raises(ConfigError, match="missing required keys"):
        parse_source_config(data)


def test_load_from_toml_file(tmp_path: Path) -> None:
    path = tmp_path / "example.toml"
    path.write_text(
        'name = "example-crawler"\n'
        'exhibition_id = "example-expo"\n'
        'edition_id = "example-expo-2026"\n'
        'source_type = "official_exhibitor_list"\n'
        'start_urls = ["https://www.example.com/exhibitors"]\n'
        'allowed_domains = ["example.com"]\n'
        "max_retries = 2\n",
        encoding="utf-8",
    )
    cfg = load_source_config(path)
    assert cfg.name == "example-crawler" and cfg.max_retries == 2


def test_load_reports_file_path_for_bad_toml_and_bad_values(tmp_path: Path) -> None:
    broken = tmp_path / "broken.toml"
    broken.write_text("name = ", encoding="utf-8")
    with pytest.raises(ConfigError, match="broken.toml: invalid TOML"):
        load_source_config(broken)
    wrong = tmp_path / "wrong.toml"
    wrong.write_text('name = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="wrong.toml: missing required keys"):
        load_source_config(wrong)
