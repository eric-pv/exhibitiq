"""Quality gate between an acquisition and a new data package (D4-07).

A source can fail without an HTTP error: a page that still answers 200 but whose exhibitor list is now empty, a CSV
that only has its header, a table whose name column became blank. The crawler then reports ``succeeded`` (or
``partial``) with few or no records, and nothing downstream would stop a near-empty package from becoming the
edition's latest. ``check_acquisition`` looks at what is about to be packaged and says whether it should be:

| Code | Level | When |
|---|---|---|
| ``Q1`` | block | a crawl run of the acquisition is ``failed`` or ``cancelled`` |
| ``Q2`` | block | no participation is ``listed`` (the source returned nothing usable) |
| ``Q3`` | block | the ``listed`` count fell by more than ``max_drop_ratio`` compared with the previous package |
| ``Q4`` | warn  | a crawl run is ``partial`` (errors, or cut short) |
| ``Q5`` | warn  | the crawl runs extracted more rows than became listed participations (rows were skipped or merged) |

``block`` means: do not publish automatically; a person looks at the evidence first. Nothing is deleted or changed, and
the gate never decides that a drop is real or not — it only refuses to let one through unseen. A person who has
checked the source can pass ``accept={"Q3"}`` (for example) and the finding is kept, downgraded to ``warn`` and marked
``accepted``. The previous package is never modified either way.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_DROP_RATIO = 0.5
CODES = ("Q1", "Q2", "Q3", "Q4", "Q5")


@dataclass(frozen=True)
class QualityFinding:
    code: str
    level: str  # "block" | "warn"
    message: str
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "level": self.level, "message": self.message, "accepted": self.accepted}


def _listed(participations: Iterable[Mapping[str, Any]]) -> int:
    return sum(1 for p in participations if p.get("listing_status") == "listed")


def check_acquisition(
    crawl_runs: Sequence[Mapping[str, Any]],
    participations: Sequence[Mapping[str, Any]],
    *,
    previous_participations: Sequence[Mapping[str, Any]] | None = None,
    max_drop_ratio: float = DEFAULT_MAX_DROP_RATIO,
    accept: Iterable[str] = (),
) -> list[QualityFinding]:
    """Findings for the records about to be packaged.

    ``crawl_runs`` are the runs of **this** acquisition (not the ones carried from the previous package);
    ``participations`` are the final records (after ``carry_forward`` when there is a previous package; carried
    ``removed`` records are not counted as listed); ``previous_participations`` are the previous package's.
    """
    if not 0 <= max_drop_ratio < 1:
        raise ValueError("max_drop_ratio must be at least 0 and below 1")
    accepted = set(accept)
    unknown = sorted(accepted - set(CODES))
    if unknown:
        raise ValueError(f"unknown quality codes: {', '.join(unknown)}")
    if not crawl_runs:
        raise ValueError("an acquisition has at least one crawl run")
    found: list[QualityFinding] = []

    def add(code: str, level: str, message: str) -> None:
        if level == "block" and code in accepted:
            found.append(QualityFinding(code, "warn", message + " (accepted by a person)", accepted=True))
        else:
            found.append(QualityFinding(code, level, message))

    for run in sorted(crawl_runs, key=lambda r: r["crawl_run_id"]):
        status = run.get("status")
        if status in ("failed", "cancelled"):
            samples = run.get("error_samples") or []
            detail = f": {samples[0]['message']}" if samples else ""
            add("Q1", "block", f"crawl run {run['crawl_run_id']} is {status}{detail}")
        elif status == "partial":
            add("Q4", "warn", f"crawl run {run['crawl_run_id']} is partial ({run.get('stats', {}).get('error_count', 0)} error(s)){': ' + run['notes'] if run.get('notes') else ''}")

    listed = _listed(participations)
    if listed == 0:
        add("Q2", "block", "no participation is listed: the source returned no usable exhibitor rows")
    if previous_participations is not None:
        before = _listed(previous_participations)
        if listed < before * (1 - max_drop_ratio):
            add("Q3", "block", f"listed participations fell from {before} to {listed} (more than {max_drop_ratio:.0%}); check the source before publishing")
    extracted = sum(int(r.get("stats", {}).get("records_extracted", 0)) for r in crawl_runs)
    if extracted > listed:
        add("Q5", "warn", f"{extracted} row(s) were extracted but {listed} participation(s) are listed (rows merged as the same company, or skipped)")
    return found


def blocked(findings: Iterable[QualityFinding]) -> bool:
    """True if any finding still blocks automatic publication."""
    return any(f.level == "block" for f in findings)
