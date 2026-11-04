"""Deterministic text cleaning and normalization (D2-07).

Everything here is a pure function with no exhibition-specific knowledge. Two principles:

1. **Cleaning is not interpretation.** ``clean_text`` only removes what is never meaningful (control and
   zero-width characters, repeated whitespace, Unicode compatibility forms). It does not fix spelling,
   translate, or change case.
2. **Name keys are for matching, never identity.** A company's identity is its ``company_id`` (contract
   §2: never derived from a name). ``exact_key`` is strict enough to link the *same listed name* across
   editions; ``loose_key`` additionally ignores legal-form words and is used **only to suggest
   candidates for a human**, never to merge.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

_SPACE = re.compile(r"\s+")
_HOSTNAME = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_LIST_SPLIT = re.compile(r"[;|\n、；]+")
MAX_TEXT = 500  # common.schema.json short_text

# Generic legal-form words (any country). Used only by ``loose_key``. Not exhibition-specific.
LEGAL_FORMS = frozenset(
    {
        "ltd", "limited", "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "llp", "lp", "plc", "gmbh", "ag", "kg",
        "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "ab", "oy", "as", "aps", "pte", "pty", "sdn", "bhd", "oyj", "kk", "jsc", "ooo", "zao",
        "有限公司", "股份有限公司", "有限責任公司", "株式会社", "株式會社", "有限会社", "합자회사", "주식회사",
    }
)


def clean_text(value: object) -> str:
    """NFKC, drop control/format characters (incl. zero-width), collapse whitespace, strip. Never raises on str."""
    if not isinstance(value, str):
        value = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", value)
    text = "".join(" " if ch in "\t\r\n  " else ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf") or ch in "\t\r\n")
    return _SPACE.sub(" ", text).strip()


@dataclass(frozen=True)
class NameKeys:
    exact: str
    loose: str


def _tokens(name: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", name).casefold()
    return [t for t in re.split(r"[^\w]+|_", folded) if t]


def name_keys(name: str) -> NameKeys:
    """Matching keys for a company name. Raises ``ValueError`` if the name has no letters or digits."""
    cleaned = clean_text(name)
    exact_tokens = _tokens(cleaned)
    if not exact_tokens:
        raise ValueError("name has no letters or digits")
    exact = "".join(exact_tokens)
    loose_tokens = list(exact_tokens)
    while len(loose_tokens) > 1 and loose_tokens[-1] in LEGAL_FORMS:
        loose_tokens.pop()
    # a CJK legal form written before or after the name, with or without a space: 株式会社Example, 測試股份有限公司
    joined = "".join(loose_tokens)
    for form in sorted((f for f in LEGAL_FORMS if any(ord(c) > 0x2E80 for c in f)), key=len, reverse=True):
        if joined != form and (joined.endswith(form) or joined.startswith(form)):
            joined = joined[: -len(form)] if joined.endswith(form) else joined[len(form):]
            break
    return NameKeys(exact=exact, loose=joined or exact)


@dataclass(frozen=True)
class Website:
    url: str  # normalized http(s) URL
    hostname: str  # lower-case, ASCII (punycode), without a trailing dot


def normalize_website(raw: object) -> Website | None:
    """A normalized public http(s) URL, or ``None`` if ``raw`` is not one. Never guesses beyond adding ``https://``."""
    text = clean_text(raw)
    if not text or " " in text:
        return None
    if "://" not in text:
        text = "https://" + text.lstrip("/")
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").rstrip(".").lower()
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or parts.username is not None or parts.password is not None or not host:
        return None
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    if not _HOSTNAME.fullmatch(host) or len(host) > 253:
        return None
    scheme = parts.scheme.lower()
    netloc = host if port in (None, 80 if scheme == "http" else 443) else f"{host}:{port}"
    path = parts.path if parts.path not in ("", "/") else ""
    url = urlunsplit((scheme, netloc, path, parts.query, ""))
    return Website(url=url, hostname=host) if len(url) <= 2048 else None


def site_key(hostname: str) -> str:
    """Hostname without a leading ``www.``: for spotting two entries that share a website. Candidates only."""
    return hostname[4:] if hostname.startswith("www.") else hostname


def split_list(value: object) -> list[str]:
    """``"a; b | c"`` -> ``["a", "b", "c"]``: cleaned, empty items dropped, duplicates removed, order kept."""
    if isinstance(value, (list, tuple)):
        items: Iterable[object] = value
    else:
        items = _LIST_SPLIT.split(clean_text_keep_newlines(value))
    seen: dict[str, None] = {}
    for item in items:
        text = clean_text(item)[:MAX_TEXT]
        if text:
            seen.setdefault(text, None)
    return list(seen)


def clean_text_keep_newlines(value: object) -> str:
    """Like ``clean_text`` but keeps newlines (they separate list items)."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cf") or ch in "\t\r\n")


def normalize_country(raw: object, aliases: Mapping[str, str]) -> str | None:
    """ISO 3166-1 alpha-2 code for ``raw`` using the caller's alias table, else ``None``. No built-in guesses.

    ``aliases`` maps a lower-case, cleaned spelling to a code. Country spellings are part of a source's
    mapping configuration (they differ between sources), not of this module.
    """
    code = aliases.get(clean_text(raw).casefold())
    return code if isinstance(code, str) and re.fullmatch(r"[A-Z]{2}", code) else None
