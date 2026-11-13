"""Carrying a previous package forward and recording what changed (D2-08).

A data package describes one edition and is immutable (contract §3). When the same edition is acquired again, the new
package is built from the new acquisition, then ``carry_forward`` joins it with the previous package so that:

- **Nothing disappears.** A participation that was listed before and is not in the new listing stays,
  with ``listing_status: "removed"`` (contract: "紀錄保留，不刪除"). One that was removed and appears again is
  ``listed`` again. Companies are kept as long as a participation (or a ``merged_into``) refers to them.
- **Evidence accumulates.** The new package's ``sources.jsonl`` and ``crawl_runs.jsonl`` contain the previous
  ones too, so every reference in carried records still resolves (R10).
- **History is not rewritten.** ``first_seen_at`` stays the earliest value. Companies a person marked ``merged`` stay
  ``merged``; the build never silently un-merges them.

``diff_records`` then compares the previous and the final records and produces ``change`` records
(``added`` / ``removed`` / ``modified`` with ``field_changes``). It is a literal comparison: a field present before
and absent now is reported as ``after: null`` ("not in the latest listing"), not interpreted. ``source_ids``,
``field_sources`` and ``last_seen_at`` are bookkeeping, not content, and are not compared.
"""
from __future__ import annotations

import copy
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from etl.ids import make_id

BOOKKEEPING = frozenset({"source_ids", "field_sources", "last_seen_at"})
REMOVED_NOTE = "Not in the latest acquisition of this edition's exhibitor list; kept, marked removed."


@dataclass
class Carried:
    companies: list[dict[str, Any]]
    participations: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    crawl_runs: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


def _by(records: Sequence[Mapping[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {r[key]: copy.deepcopy(dict(r)) for r in records}


def carry_forward(
    previous: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    companies: Sequence[Mapping[str, Any]],
    participations: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    crawl_runs: Sequence[Mapping[str, Any]],
) -> Carried:
    """``previous`` maps ``companies`` / ``participations`` / ``sources`` / ``crawl_runs`` to the previous package's records."""
    warnings: list[str] = []
    new_companies, new_parts = _by(companies, "company_id"), _by(participations, "participation_id")
    old_companies, old_parts = _by(previous.get("companies", ()), "company_id"), _by(previous.get("participations", ()), "participation_id")

    out_parts = dict(new_parts)
    for pid, old in old_parts.items():
        if pid in new_parts:
            first = min(old.get("first_seen_at", new_parts[pid]["first_seen_at"]), new_parts[pid]["first_seen_at"])
            new_parts[pid]["first_seen_at"] = first
            out_parts[pid] = new_parts[pid]
        elif old["listing_status"] == "listed":
            removed = dict(old, listing_status="removed")
            removed["notes"] = (old.get("notes", "") + " | " + REMOVED_NOTE).strip(" |")[:4000]
            out_parts[pid] = removed
        else:
            out_parts[pid] = old  # already removed: unchanged

    out_companies = dict(new_companies)
    for cid, old in old_companies.items():
        if cid in new_companies:
            if old.get("status") == "merged":
                out_companies[cid] = old  # a person's decision stands; the new build must not undo it
                warnings.append(f"{cid} is merged (into {old.get('merged_into')}); the previous record was kept")
            else:
                new_companies[cid]["first_seen_at"] = min(old.get("first_seen_at", new_companies[cid]["first_seen_at"]), new_companies[cid]["first_seen_at"])
        else:
            out_companies[cid] = old

    # keep a company when this edition has a participation by it, or a kept company was merged into it (contract §3)
    keep = {p["company_id"] for p in out_parts.values()}
    frontier = set(keep)
    while frontier:
        targets = {out_companies[c]["merged_into"] for c in frontier if c in out_companies and out_companies[c].get("merged_into")} - keep
        keep |= targets
        frontier = targets
    for cid in sorted(set(out_companies) - keep):
        warnings.append(f"company {cid} has no participation in this edition and no kept company was merged into it; dropped from the package")
        del out_companies[cid]

    def union(old: Sequence[Mapping[str, Any]], new: Sequence[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
        merged = _by(old, key)
        merged.update(_by(new, key))  # same ID = same record; the new one wins (they must be identical)
        return [merged[k] for k in sorted(merged, key=lambda k: k.encode())]

    return Carried(
        companies=sorted(out_companies.values(), key=lambda r: r["company_id"].encode()),
        participations=sorted(out_parts.values(), key=lambda r: r["participation_id"].encode()),
        sources=union(previous.get("sources", ()), sources, "source_id"),
        crawl_runs=union(previous.get("crawl_runs", ()), crawl_runs, "crawl_run_id"),
        warnings=warnings,
    )


def _compare(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for key in sorted((set(before) | set(after)) - BOOKKEEPING):
        if before.get(key) != after.get(key):
            changes.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return changes


def diff_records(
    previous: Mapping[str, Sequence[Mapping[str, Any]]],
    current: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    dataset_id: str,
    previous_dataset_id: str,
    detected_at: str,
    rand: Callable[[int], bytes] = os.urandom,
    now_ms: int | None = None,
) -> list[dict[str, Any]]:
    """``change`` records between two sets of ``companies`` / ``participations`` (same keys as ``carry_forward``)."""
    out: list[dict[str, Any]] = []
    for entity_type, set_name, key in (("company", "companies", "company_id"), ("participation", "participations", "participation_id")):
        before, after = _by(previous.get(set_name, ()), key), _by(current.get(set_name, ()), key)
        for entity_id in sorted(set(before) | set(after), key=lambda k: k.encode()):
            old, new = before.get(entity_id), after.get(entity_id)
            record: dict[str, Any] | None = None
            if old is None:
                record = {"change_type": "added", "source_ids": new["source_ids"]}
            elif new is None:  # cannot happen after carry_forward (nothing is dropped); kept so the function is correct on its own
                record = {"change_type": "removed", "source_ids": old["source_ids"]}
            elif old.get("listing_status") == "listed" and new.get("listing_status") == "removed":
                record = {"change_type": "removed", "source_ids": old["source_ids"]}
            else:
                fields = _compare(old, new)
                if fields:
                    record = {"change_type": "modified", "field_changes": fields, "source_ids": new["source_ids"]}
            if record is not None:
                out.append({
                    "change_id": make_id("chg", now_ms=now_ms, rand=rand), "dataset_id": dataset_id, "previous_dataset_id": previous_dataset_id,
                    "entity_type": entity_type, "entity_id": entity_id, "detected_at": detected_at, **record,
                })
    out.sort(key=lambda c: c["change_id"].encode())
    return out
