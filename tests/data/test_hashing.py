"""Tests for etl.hashing (D1-04). The expected values come from the contract's example package."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from etl.hashing import EMPTY_SHA256, content_hash, sha256_of_bytes

EXAMPLE = Path(__file__).resolve().parents[2] / "schemas" / "v1" / "examples" / "package"
# The empty-file digest is stated in the contract (§6).
CONTRACT_EMPTY = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def example_manifest() -> dict:
    return json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))


def test_empty_digest_matches_the_contract() -> None:
    assert sha256_of_bytes(b"") == CONTRACT_EMPTY == EMPTY_SHA256


def test_file_digests_match_the_example_package() -> None:
    for name, entry in example_manifest()["files"].items():
        assert sha256_of_bytes((EXAMPLE / name).read_bytes()) == entry["sha256"], name


def test_content_hash_reproduces_the_example_package() -> None:
    manifest = example_manifest()
    digests = {name: entry["sha256"] for name, entry in manifest["files"].items()}
    assert content_hash(digests) == manifest["content_hash"]


def test_content_hash_does_not_depend_on_mapping_order() -> None:
    digests = {name: entry["sha256"] for name, entry in example_manifest()["files"].items()}
    assert content_hash(dict(reversed(list(digests.items())))) == content_hash(digests)


def test_content_hash_changes_when_any_file_changes() -> None:
    digests = {name: entry["sha256"] for name, entry in example_manifest()["files"].items()}
    changed = dict(digests, **{"companies.jsonl": sha256_of_bytes(b"x")})
    assert content_hash(changed) != content_hash(digests)


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="sha256sum not available")
def test_content_hash_equals_the_contracts_reference_shell_command() -> None:
    names = "changes.jsonl companies.jsonl crawl_runs.jsonl edition.json exhibition.json participations.jsonl sources.jsonl"
    out = subprocess.run(
        f"sha256sum {names} | LC_ALL=C sort -k2 | sha256sum",
        shell=True,
        cwd=EXAMPLE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()[0]
    digests = {name: entry["sha256"] for name, entry in example_manifest()["files"].items()}
    assert content_hash(digests) == "sha256:" + out


@pytest.mark.parametrize("bad", ["", "abc", "sha256:" + "A" * 64, "sha256:" + "a" * 63, "md5:" + "a" * 64])
def test_malformed_digests_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        content_hash({"a.jsonl": bad})
