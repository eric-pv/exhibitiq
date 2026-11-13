"""Raw listings -> schema-valid ``company`` and ``participation`` records (D2-07).

Input rows are what the crawler / importers produced ("as listed", D2-01 / D2-04). The field names a
row may use are fixed here and are the only contract between acquisition and ETL:

    exhibitor_name_as_listed (required)  booth  hall  country  website  categories  products
    description  participation_type  (``_row`` and any other key are ignored)

Rules:

- **Nothing is invented.** A missing field stays missing. A value that cannot be normalized is dropped
  with a warning in the report, never replaced by a guess. The raw text stays in the ``*_as_listed``
  fields.
- **Identity is the registry's** (``etl.registry``): the same listed name keeps its ``company_id``
  across editions and packages; IDs are random, not derived from names (contract §2).
- **Conservative matching.** Rows are the same company only when their exact name keys are equal and
  their countries do not contradict. Similar names, shared websites or differing legal forms are
  reported as *candidates* for a human; nothing is merged on similarity.
- **Duplicates inside an edition collapse into one participation** (one per company per edition); the
  booth/hall/etc. the other rows disagree on are kept in ``notes`` rather than discarded or chosen silently.
- **Everything is traceable.** Each record carries the ``source_ids`` of the rows it comes from, and
  ``field_sources`` where a field comes from only some of them. All records are validated against the
  shared Schema before being returned; an invalid record is a bug and raises ``BuildError``.
- Deterministic: same rows + same registry state + same ID source = same output.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from etl.normalize import clean_text, name_keys, normalize_country, normalize_website, site_key, split_list
from etl.registry import CompanyRegistry
from etl.schema_registry import SchemaSet

PARTICIPATION_TYPES = ("exhibitor", "co_exhibitor", "sponsor", "unknown")
MAX_SHORT = 500
MAX_TEXT = 4000


class BuildError(Exception):
    """The builder produced something the Schema rejects (a bug), or the input as a whole is unusable."""


@dataclass(frozen=True)
class RawListing:
    """One row from one snapshot, with its provenance."""

    data: Mapping[str, Any]
    source_id: str


@dataclass
class BuildReport:
    rows_in: int = 0
    rows_rejected: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    merged_rows: list[dict[str, Any]] = field(default_factory=list)  # duplicates collapsed into one company
    candidates: list[dict[str, Any]] = field(default_factory=list)  # possible same company, NOT merged
    conflicts: list[dict[str, Any]] = field(default_factory=list)  # exact name equal but countries differ, or ambiguous

    def summary(self) -> dict[str, int]:
        return {
            "rows_in": self.rows_in, "rows_rejected": len(self.rows_rejected), "warnings": len(self.warnings),
            "merged_rows": len(self.merged_rows), "candidates": len(self.candidates), "conflicts": len(self.conflicts),
        }


@dataclass
class BuildResult:
    companies: list[dict[str, Any]]
    participations: list[dict[str, Any]]
    report: BuildReport


def _short(value: object) -> str | None:
    text = clean_text(value)
    return text[:MAX_SHORT].strip() or None


def _first(values: Sequence[Any]) -> Any:
    return next((v for v in values if v), None)


def build_records(
    listings: Sequence[RawListing],
    *,
    edition_id: str,
    retrieved_at: Mapping[str, str],
    registry: CompanyRegistry,
    country_aliases: Mapping[str, str] | None = None,
    schemas: SchemaSet | None = None,
) -> BuildResult:
    """Build records for one edition. ``retrieved_at`` maps every ``source_id`` used to its UTC timestamp.

    Mutates ``registry`` (new companies / participations); the caller saves it only after this returns.
    """
    schemas = schemas or SchemaSet()
    aliases = {k.casefold(): v for k, v in (country_aliases or {}).items()}
    report = BuildReport(rows_in=len(listings))
    unknown_sources = sorted({row.source_id for row in listings} - set(retrieved_at))
    if unknown_sources:
        raise BuildError(f"no retrieved_at for source(s): {', '.join(unknown_sources)}")

    # --- pass 1: clean each row and attach it to a company ------------------------------------------------
    groups: dict[str, list[dict[str, Any]]] = {}
    for index, listing in enumerate(listings):
        data = listing.data
        listed = _short(data.get("exhibitor_name_as_listed"))
        if listed is None:
            report.rows_rejected.append({"row": index, "reason": "no exhibitor_name_as_listed", "source_id": listing.source_id})
            continue
        try:
            keys = name_keys(listed)
        except ValueError:
            report.rows_rejected.append({"row": index, "reason": f"name {listed!r} has no letters or digits", "source_id": listing.source_id})
            continue
        country_text = _short(data.get("country"))
        country = normalize_country(country_text, aliases) if country_text else None
        if country_text and country is None:
            report.warnings.append(f"row {index}: country {country_text!r} is not in the country aliases; kept only as country_as_listed")
        website = normalize_website(data.get("website")) if clean_text(data.get("website")) else None
        if clean_text(data.get("website")) and website is None:
            report.warnings.append(f"row {index}: website {clean_text(data.get('website'))[:80]!r} is not a usable http(s) URL; dropped")
        ptype = clean_text(data.get("participation_type")).casefold()
        if ptype and ptype not in PARTICIPATION_TYPES:
            report.warnings.append(f"row {index}: participation_type {ptype!r} is not one of {', '.join(PARTICIPATION_TYPES)}; recorded as unknown")
        row = {
            "index": index, "source_id": listing.source_id, "listed": listed, "keys": keys, "country_text": country_text, "country": country,
            "website": website, "booth": _short(data.get("booth")), "hall": _short(data.get("hall")),
            "categories": split_list(data.get("categories")), "products": split_list(data.get("products")),
            "description": (clean_text(data.get("description"))[:MAX_TEXT].strip() or None),
            "type": ptype if ptype in PARTICIPATION_TYPES else "unknown",
        }
        match = registry.match(keys.exact, country)
        if match.kind == "matched":
            company_id = match.company_id
            assert company_id is not None
        else:
            if match.kind in ("country_conflict", "ambiguous"):
                report.conflicts.append({"row": index, "name": listed, "kind": match.kind, "existing": list(match.others), "country": country})
            company_id = registry.assign(keys.exact, keys.loose, country=country)
        registry.remember(company_id, exact_key=keys.exact, site=site_key(website.hostname) if website else None, country=country)
        groups.setdefault(company_id, []).append(row)

    # --- pass 2: one company + one participation per group ------------------------------------------------
    companies: list[dict[str, Any]] = []
    participations: list[dict[str, Any]] = []
    for company_id, rows in groups.items():
        if len(rows) > 1:
            report.merged_rows.append({"company_id": company_id, "rows": [r["index"] for r in rows], "listed_as": sorted({r["listed"] for r in rows}), "reason": "identical exact name key"})
        all_sources = list(dict.fromkeys(r["source_id"] for r in rows))
        stamps = sorted(retrieved_at[s] for s in all_sources)

        def sources_for(selector) -> list[str]:  # noqa: ANN001
            return list(dict.fromkeys(r["source_id"] for r in rows if selector(r)))

        name = rows[0]["listed"]
        company: dict[str, Any] = {"company_id": company_id, "name": name, "status": "active", "source_ids": all_sources, "verification_status": "unverified", "first_seen_at": stamps[0]}
        field_sources: dict[str, list[str]] = {}
        alias_sources: dict[str, list[str]] = {}
        for r in rows:
            if r["listed"] != name:
                alias_sources.setdefault(r["listed"], []).append(r["source_id"])
        if alias_sources:
            company["aliases"] = [{"name": n, "source_ids": list(dict.fromkeys(s))} for n, s in sorted(alias_sources.items())]
        website = _first([r["website"] for r in rows])
        if website:
            company["website"] = website.url
            company["domains"] = sorted({r["website"].hostname for r in rows if r["website"]})
            field_sources["website"] = sources_for(lambda r: r["website"] is not None and r["website"].url == website.url)
        country = _first([r["country"] for r in rows])
        if country:
            company["country"] = country
            field_sources["country"] = sources_for(lambda r: r["country"] == country)
        description = _first([r["description"] for r in rows])
        if description:
            company["description"] = description
            field_sources["description"] = sources_for(lambda r: r["description"] == description)
        field_sources = {k: v for k, v in field_sources.items() if v != all_sources}  # absent = "all of source_ids"
        if field_sources:
            company["field_sources"] = field_sources
        companies.append(company)

        participation: dict[str, Any] = {
            "participation_id": registry.participation_id(edition_id, company_id), "company_id": company_id, "edition_id": edition_id,
            "exhibitor_name_as_listed": rows[0]["listed"], "participation_type": _first([r["type"] for r in rows if r["type"] != "unknown"]) or "unknown",
            "listing_status": "listed", "first_seen_at": stamps[0], "last_seen_at": stamps[-1], "source_ids": all_sources, "verification_status": "unverified",
        }
        notes: list[str] = []
        for key, label in (("booth", "booth"), ("hall", "hall")):
            values = list(dict.fromkeys(r[key] for r in rows if r[key]))
            if values:
                participation[key] = values[0]
                if len(values) > 1:
                    notes.append(f"{label} also listed as: {', '.join(values[1:])}")
        country_text = _first([r["country_text"] for r in rows])
        if country_text:
            participation["country_as_listed"] = country_text
        if website:
            participation["website_as_listed"] = website.url
        for source_key, target in (("categories", "categories_as_listed"), ("products", "products_as_listed")):
            merged = list(dict.fromkeys(item for r in rows for item in r[source_key]))
            if merged:
                participation[target] = merged
        if len({r["listed"] for r in rows}) > 1:
            notes.append("listed under several spellings: " + "; ".join(sorted({r["listed"] for r in rows})))
        if notes:
            participation["notes"] = "; ".join(notes)[:MAX_TEXT]
        participations.append(participation)

    # --- candidates (never merged) ----------------------------------------------------------------------
    for company in companies:
        for other_id, reason in registry.candidates(company["company_id"]):
            pair = sorted([company["company_id"], other_id])
            entry = {"companies": pair, "reason": reason}
            if entry not in report.candidates:
                report.candidates.append(entry)
    report.candidates.sort(key=lambda e: (e["companies"], e["reason"]))

    # --- validate, then sort by primary key ---------------------------------------------------------------
    for entity, records in (("company", companies), ("participation", participations)):
        for record in records:
            problems = schemas.errors(entity, record)
            if problems:
                raise BuildError(f"built an invalid {entity} {record.get('company_id') or record.get('participation_id')}: {'; '.join(problems)}")
    companies.sort(key=lambda r: r["company_id"].encode())
    participations.sort(key=lambda r: r["participation_id"].encode())
    return BuildResult(companies, participations, report)
