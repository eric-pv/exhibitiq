"""Preliminary rule-based screening that never deletes anything (D2-10).

Rules come from a TOML file (the exhibition-independent code; the keywords are configuration). Every
participation of a package gets a screening *label*; the package and its records are not touched, nothing is dropped,
and the output says plainly that it is rule-based, not an AI judgement or a verified fact.

    name = "example-screen"
    [[rules]]
    id = "optics"                        # unique, lower-case
    description = "mentions optics"      # optional
    field = "categories_as_listed"       # participation field, or company.<field> (e.g. company.description)
    op = "contains_any"                  # contains_any | equals_any | present | absent
    terms = ["optic", "laser"]           # case-insensitive; required for contains_any / equals_any
    outcome = "include"                  # include | exclude | review

Label per participation: ``excluded`` (an exclude rule matched, no include rule), ``include`` (an include rule matched,
no exclude), ``review`` (a review rule matched, or include and exclude both matched: a person decides),
``unscreened`` (no rule matched). Excluded participations stay in the data and in every export.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etl.package import read_package

OPS = ("contains_any", "equals_any", "present", "absent")
OUTCOMES = ("include", "exclude", "review")
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
_FIELD = re.compile(r"^(company\.)?[a-z][a-z0-9_]*$")
LABEL = "rule_based"


class ScreeningError(Exception):
    pass


@dataclass(frozen=True)
class Rule:
    id: str
    field: str
    op: str
    outcome: str
    terms: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class RuleSet:
    name: str
    rules: tuple[Rule, ...]

    def fingerprint(self) -> str:
        data = [{"id": r.id, "field": r.field, "op": r.op, "outcome": r.outcome, "terms": list(r.terms)} for r in self.rules]
        return "sha256:" + hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def parse_rules(data: Mapping[str, Any]) -> RuleSet:
    if not isinstance(data, Mapping) or set(data) - {"name", "rules"}:
        raise ScreeningError("rules file may only contain `name` and `[[rules]]`")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ScreeningError("`name` is required")
    raw = data.get("rules")
    if not isinstance(raw, list) or not raw:
        raise ScreeningError("at least one [[rules]] entry is required")
    rules, seen = [], set()
    for i, item in enumerate(raw):
        where = f"rules[{i}]"
        if not isinstance(item, Mapping) or set(item) - {"id", "description", "field", "op", "terms", "outcome"}:
            raise ScreeningError(f"{where}: unknown or missing keys")
        rid, field, op, outcome = item.get("id"), item.get("field"), item.get("op"), item.get("outcome")
        if not (isinstance(rid, str) and _ID.fullmatch(rid)) or rid in seen:
            raise ScreeningError(f"{where}: id must be unique and match {_ID.pattern}")
        seen.add(rid)
        if not (isinstance(field, str) and _FIELD.fullmatch(field)):
            raise ScreeningError(f"{where}: field must look like `booth` or `company.country`")
        if op not in OPS or outcome not in OUTCOMES:
            raise ScreeningError(f"{where}: op must be one of {OPS} and outcome one of {OUTCOMES}")
        terms = item.get("terms", [])
        if op in ("contains_any", "equals_any"):
            if not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t.strip() for t in terms):
                raise ScreeningError(f"{where}: {op} needs a non-empty list of terms")
        elif terms:
            raise ScreeningError(f"{where}: {op} takes no terms")
        description = item.get("description", "")
        if not isinstance(description, str):
            raise ScreeningError(f"{where}: description must be text")
        rules.append(Rule(rid, field, op, outcome, tuple(t.strip().casefold() for t in terms), description))
    return RuleSet(name.strip(), tuple(rules))


def load_rules(path: str | Path) -> RuleSet:
    try:
        return parse_rules(tomllib.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ScreeningError(f"cannot read rules {path}: {exc}") from None


def _texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [t for v in value for t in _texts(v)]
    text = str(value).strip().casefold()
    return [text] if text else []


def _matches(rule: Rule, participation: Mapping[str, Any], company: Mapping[str, Any]) -> bool:
    source = company if rule.field.startswith("company.") else participation
    texts = _texts(source.get(rule.field.removeprefix("company.")))
    if rule.op == "present":
        return bool(texts)
    if rule.op == "absent":
        return not texts
    if rule.op == "equals_any":
        return any(t in rule.terms for t in texts)
    return any(term in t for t in texts for term in rule.terms)


def screen_records(participations: Sequence[Mapping[str, Any]], companies: Sequence[Mapping[str, Any]], rules: RuleSet) -> dict[str, dict[str, Any]]:
    by_company = {c["company_id"]: c for c in companies}
    out: dict[str, dict[str, Any]] = {}
    for p in participations:
        company = by_company.get(p["company_id"], {})
        hits = [r for r in rules.rules if _matches(r, p, company)]
        outcomes = {r.outcome for r in hits}
        if not hits:
            label = "unscreened"
        elif "review" in outcomes or {"include", "exclude"} <= outcomes:
            label = "review"
        else:
            label = "include" if "include" in outcomes else "excluded"
        out[p["participation_id"]] = {"label": label, "matched_rules": [r.id for r in hits]}
    return out


def screen_package(package_dir: str | Path, rules: RuleSet) -> dict[str, Any]:
    package = read_package(package_dir)
    entries = screen_records(package.records["participations"], package.records["companies"], rules)
    counts = Counter(e["label"] for e in entries.values())
    return {
        "kind": LABEL, "note": "Rule-based preliminary screening; not an AI judgement and not a verified fact. Nothing was removed from the package.",
        "dataset_id": package.manifest["dataset_id"], "data_origin": package.manifest["data_origin"], "rules_name": rules.name, "rules_fingerprint": rules.fingerprint(),
        "rules": [{"id": r.id, "field": r.field, "op": r.op, "outcome": r.outcome, "terms": list(r.terms), "description": r.description} for r in rules.rules],
        "counts": {k: counts.get(k, 0) for k in ("include", "excluded", "review", "unscreened")}, "total": len(entries),
        "participations": dict(sorted(entries.items())),
    }


def save_screening(result: Mapping[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
        os.replace(temp, target)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
