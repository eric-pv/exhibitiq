"""Hashing for data packages (D1-04), per ``docs/specs/data-package-contract.md`` §6.

Every hash is written as ``sha256:`` followed by 64 lowercase hex characters.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping

PREFIX = "sha256:"
_HEX64 = re.compile(r"[0-9a-f]{64}")
EMPTY_SHA256 = PREFIX + hashlib.sha256(b"").hexdigest()


def sha256_of_bytes(data: bytes) -> str:
    return PREFIX + hashlib.sha256(data).hexdigest()


def _hex_of(digest: str) -> str:
    if not digest.startswith(PREFIX) or not _HEX64.fullmatch(digest[len(PREFIX):]):
        raise ValueError(f"not a sha256 digest in the form 'sha256:<64 lowercase hex>': {digest!r}")
    return digest[len(PREFIX):]


def content_hash(file_digests: Mapping[str, str]) -> str:
    """``content_hash``: sha256 of the list ``<hex>  <file name>\\n``, ordered by file name in
    byte order. Pass the digests of the 7 data files (never ``manifest.json``).

    Equivalent to: ``sha256sum <files> | LC_ALL=C sort -k2 | sha256sum``.
    """
    lines = [f"{_hex_of(file_digests[name])}  {name}\n" for name in sorted(file_digests, key=lambda n: n.encode("utf-8"))]
    return sha256_of_bytes("".join(lines).encode("utf-8"))
