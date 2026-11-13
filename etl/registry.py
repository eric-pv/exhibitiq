"""The company and participation ID registry (D2-07).

Contract §2: a ``company_id`` is assigned once, never changes, is never reused and is never derived
from a name or domain. The registry is where that promise is kept across data packages: it remembers
which listed names belong to which ``company_id`` (and which ``participation_id`` an edition's
participation has), so the next package for the same or another exhibition reuses the same IDs.

It lives in one JSON file, ``data/registry/companies.json`` by convention (canonical, sorted, small
diffs, versioned by Git). Only the ETL writes it; entries are only ever added or extended.

Matching is deliberately conservative. A listed name links to an existing company only when
its **exact key** is identical and the known countries do not contradict each other. Anything less
certain creates a *new* company and the pair is reported as a candidate for a human to merge
(``status: merged`` in the data, decided by a person, per the contract).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from etl.ids import make_id

REGISTRY_VERSION = 1
_CO = re.compile(r"^co_[0-7][0-9A-HJKMNP-TV-Z]{25}$")
_PT = re.compile(r"^pt_[0-7][0-9A-HJKMNP-TV-Z]{25}$")
_EDITION = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*-[0-9]{4}(?:-[a-z0-9]+)?$")


class RegistryError(Exception):
    pass


@dataclass
class Entry:
    exact_keys: list[str]
    loose_key: str
    sites: list[str] = field(default_factory=list)  # site keys (hostname without www.) seen for this company
    country: str | None = None


@dataclass(frozen=True)
class Match:
    kind: str  # "matched" | "new" | "ambiguous" | "country_conflict"
    company_id: str | None = None
    others: tuple[str, ...] = ()  # the companies that stopped an automatic match


class CompanyRegistry:
    def __init__(self, *, rand: Callable[[int], bytes] = os.urandom, now_ms: Callable[[], int | None] = lambda: None) -> None:
        self.companies: dict[str, Entry] = {}
        self.participations: dict[str, str] = {}  # "<edition_id>|<company_id>" -> participation_id
        self._rand, self._now_ms = rand, now_ms

    # ------------------------------------------------------------------ matching
    def match(self, exact_key: str, country: str | None) -> Match:
        same_key = sorted(cid for cid, e in self.companies.items() if exact_key in e.exact_keys)
        if not same_key:
            return Match("new")
        compatible = [c for c in same_key if not (country and self.companies[c].country and self.companies[c].country != country)]
        if len(compatible) == 1:
            return Match("matched", compatible[0])
        if not compatible:
            return Match("country_conflict", None, tuple(same_key))
        return Match("ambiguous", None, tuple(compatible))

    def assign(self, exact_key: str, loose_key: str, *, country: str | None = None) -> str:
        """A new company. The ID is random (ULID), never a function of ``exact_key``."""
        for _ in range(5):
            company_id = make_id("co", now_ms=self._now_ms(), rand=self._rand)
            if company_id not in self.companies:
                self.companies[company_id] = Entry([exact_key], loose_key, [], country)
                return company_id
        raise RegistryError("could not generate an unused company_id")  # pragma: no cover

    def remember(self, company_id: str, *, exact_key: str | None = None, site: str | None = None, country: str | None = None) -> None:
        """Extend what is known about a company (never replaces: an existing country is kept)."""
        entry = self.companies[company_id]
        if exact_key and exact_key not in entry.exact_keys:
            entry.exact_keys.append(exact_key)
            entry.exact_keys.sort()
        if site and site not in entry.sites:
            entry.sites.append(site)
            entry.sites.sort()
        if country and entry.country is None:
            entry.country = country

    def participation_id(self, edition_id: str, company_id: str) -> str:
        """Stable per (edition, company): the same pair always gets the same ID (contract §2)."""
        if not _EDITION.fullmatch(edition_id) or company_id not in self.companies:
            raise RegistryError(f"unknown company or bad edition_id: {company_id!r}, {edition_id!r}")
        key = f"{edition_id}|{company_id}"
        if key not in self.participations:
            self.participations[key] = make_id("pt", now_ms=self._now_ms(), rand=self._rand)
        return self.participations[key]

    def candidates(self, company_id: str) -> list[tuple[str, str]]:
        """Other companies that *might* be the same one: (company_id, reasons). For humans; nothing is merged."""
        mine = self.companies[company_id]
        found: list[tuple[str, str]] = []
        for other_id, entry in sorted(self.companies.items()):
            if other_id == company_id:
                continue
            reasons = []
            if set(entry.exact_keys) & set(mine.exact_keys):
                reasons.append("same listed name but the countries differ")
            elif entry.loose_key == mine.loose_key:
                reasons.append("same name apart from legal form")
            if set(entry.sites) & set(mine.sites):
                reasons.append("same website")
            if reasons:
                found.append((other_id, " and ".join(reasons)))
        return found

    # ------------------------------------------------------------------ persistence
    def to_dict(self) -> dict[str, Any]:
        return {
            "version": REGISTRY_VERSION,
            "companies": {
                cid: {k: v for k, v in {"exact_keys": sorted(e.exact_keys), "loose_key": e.loose_key, "sites": sorted(e.sites), "country": e.country}.items() if v not in (None, [])}
                for cid, e in sorted(self.companies.items())
            },
            "participations": dict(sorted(self.participations.items())),
        }

    def dumps(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=1) + "\n"

    def save(self, path: str | Path) -> None:
        """Atomic write (temp file + rename) so a crash never leaves a half-written registry."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self.dumps())
            os.replace(temp, target)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise

    @classmethod
    def loads(cls, text: str, **kwargs: Any) -> "CompanyRegistry":
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise RegistryError(f"registry is not valid JSON: {exc}") from None
        if not isinstance(data, dict) or data.get("version") != REGISTRY_VERSION or set(data) != {"version", "companies", "participations"}:
            raise RegistryError(f"unsupported registry (expected version {REGISTRY_VERSION} with companies and participations)")
        registry = cls(**kwargs)
        if not isinstance(data["companies"], dict) or not isinstance(data["participations"], dict):
            raise RegistryError("companies and participations must be objects")
        for cid, raw in data["companies"].items():
            if not _CO.fullmatch(cid) or not isinstance(raw, dict) or set(raw) - {"exact_keys", "loose_key", "sites", "country"}:
                raise RegistryError(f"bad company entry {cid!r}")
            keys, loose, sites, country = raw.get("exact_keys"), raw.get("loose_key"), raw.get("sites", []), raw.get("country")
            if not (isinstance(keys, list) and keys and all(isinstance(k, str) and k for k in keys) and isinstance(loose, str) and loose and isinstance(sites, list) and all(isinstance(s, str) for s in sites)):
                raise RegistryError(f"bad company entry {cid!r}")
            if country is not None and not (isinstance(country, str) and re.fullmatch(r"[A-Z]{2}", country)):
                raise RegistryError(f"bad country for {cid!r}")
            registry.companies[cid] = Entry(list(keys), loose, list(sites), country)
        for key, pid in data["participations"].items():
            edition, _, cid = str(key).partition("|")
            if not (_EDITION.fullmatch(edition) and cid in registry.companies and isinstance(pid, str) and _PT.fullmatch(pid)):
                raise RegistryError(f"bad participation entry {key!r}")
            registry.participations[key] = pid
        if len(set(registry.participations.values())) != len(registry.participations):
            raise RegistryError("a participation_id is used twice")
        return registry

    @classmethod
    def load(cls, path: str | Path, **kwargs: Any) -> "CompanyRegistry":
        """Load a registry file; a missing file is an empty registry (first run)."""
        target = Path(path)
        if not target.exists():
            return cls(**kwargs)
        return cls.loads(target.read_text(encoding="utf-8"), **kwargs)
