"""Tests for etl.registry and etl.build_records (D2-07). All names are synthetic."""
from __future__ import annotations

import json

import pytest

from etl.build_records import BuildError, RawListing, build_records
from etl.registry import CompanyRegistry, RegistryError
from etl.schema_registry import SchemaSet

SCHEMAS = SchemaSet()
S1, S2, S3 = "src_01JCS000000000000000000001", "src_01JCS000000000000000000002", "src_01JCS000000000000000000003"
STAMPS = {S1: "2026-11-03T06:00:00Z", S2: "2026-11-03T07:00:00Z", S3: "2026-11-04T08:00:00Z"}
ED = "example-expo-2026"
COUNTRIES = {"exampleland": "ZZ", "testonia": "TT"}


def counter_rand():
    state = {"n": 0}

    def rand(n: int) -> bytes:
        state["n"] += 1
        return state["n"].to_bytes(n, "big")

    return rand


def registry():
    return CompanyRegistry(rand=counter_rand(), now_ms=lambda: 1_700_000_000_000)


def row(name, source=S1, **fields):
    return RawListing({"exhibitor_name_as_listed": name, **fields}, source)


def build(rows, reg=None, edition=ED, **kw):
    return build_records(rows, edition_id=edition, retrieved_at=STAMPS, registry=reg or registry(), country_aliases=COUNTRIES, **kw)


# --- registry ----------------------------------------------------------------------------------


def test_ids_are_random_valid_and_not_derived_from_the_name():
    a, b = registry(), CompanyRegistry(rand=lambda n: b"\x07" * n, now_ms=lambda: 5)
    ida, idb = a.assign("acme", "acme"), b.assign("acme", "acme")
    assert ida != idb  # same key, different ID source: the key does not determine the ID
    assert SCHEMAS.errors("company", {"company_id": ida, "name": "x", "status": "active", "source_ids": [S1], "verification_status": "unverified"}) == []


def test_match_rules():
    reg = registry()
    assert reg.match("acme", None).kind == "new"
    first = reg.assign("acme", "acme", country="ZZ")
    assert reg.match("acme", "ZZ") == reg.match("acme", None) == reg.match("acme", "ZZ")
    assert reg.match("acme", "ZZ").company_id == first
    conflict = reg.match("acme", "TT")
    assert conflict.kind == "country_conflict" and conflict.others == (first,)
    unknown_country = reg.assign("other", "other")
    assert reg.match("other", "TT").company_id == unknown_country  # an unknown country does not contradict
    second = reg.assign("acme", "acme", country="ZZ")
    assert reg.match("acme", "ZZ").kind == "ambiguous" and set(reg.match("acme", "ZZ").others) == {first, second}


def test_remember_extends_and_never_replaces():
    reg = registry()
    cid = reg.assign("a", "a")
    reg.remember(cid, exact_key="a2", site="a.com", country="ZZ")
    reg.remember(cid, exact_key="a2", site="a.com", country="TT")
    entry = reg.companies[cid]
    assert entry.exact_keys == ["a", "a2"] and entry.sites == ["a.com"] and entry.country == "ZZ"


def test_participation_id_is_stable_per_edition_and_company():
    reg = registry()
    cid = reg.assign("a", "a")
    p1 = reg.participation_id(ED, cid)
    assert reg.participation_id(ED, cid) == p1 and reg.participation_id("example-expo-2027", cid) != p1
    with pytest.raises(RegistryError):
        reg.participation_id("Bad Edition", cid)
    with pytest.raises(RegistryError):
        reg.participation_id(ED, "co_01JCC000000000000000000009")


def test_save_load_round_trip_is_stable(tmp_path):
    reg = registry()
    cid = reg.assign("acme", "acme", country="ZZ")
    reg.remember(cid, site="acme.com")
    reg.participation_id(ED, cid)
    path = tmp_path / "reg" / "companies.json"
    reg.save(path)
    loaded = CompanyRegistry.load(path)
    assert loaded.dumps() == reg.dumps() and loaded.match("acme", "ZZ").company_id == cid
    assert not list(path.parent.glob("*.tmp"))
    assert CompanyRegistry.load(tmp_path / "missing.json").companies == {}


def test_failed_save_leaves_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / "r.json"
    reg = registry()
    reg.assign("a", "a")
    reg.save(path)
    before = path.read_text(encoding="utf-8")
    reg.assign("b", "b")
    import os

    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        reg.save(path)
    assert path.read_text(encoding="utf-8") == before and not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(version=2), lambda d: d.update(extra=1), lambda d: d.pop("participations"),
        lambda d: d["companies"].update({"co_bad": {"exact_keys": ["a"], "loose_key": "a"}}),
        lambda d: d["companies"][next(iter(d["companies"]))].update(exact_keys=[]),
        lambda d: d["companies"][next(iter(d["companies"]))].update(country="zz"),
        lambda d: d["companies"][next(iter(d["companies"]))].update(surprise=1),
        lambda d: d["participations"].update({"example-expo-2026|co_01JCC000000000000000000009": "pt_01JCP000000000000000000001"}),
        lambda d: d["participations"].update({next(iter(d["participations"])) + "x": "pt_bad"}),
        lambda d: d.update(participations={**d["participations"], f"example-expo-2027|{next(iter(d['companies']))}": next(iter(d["participations"].values()))}),
    ],
)
def test_corrupt_registries_are_rejected(mutate):
    reg = registry()
    cid = reg.assign("a", "a")
    reg.participation_id(ED, cid)
    data = json.loads(reg.dumps())
    mutate(data)
    with pytest.raises(RegistryError):
        CompanyRegistry.loads(json.dumps(data))


def test_not_json_is_rejected():
    with pytest.raises(RegistryError, match="not valid JSON"):
        CompanyRegistry.loads("{")


# --- build: basics -----------------------------------------------------------------------------


def test_one_row_builds_valid_company_and_participation():
    result = build([row("Synthetic Optics Ltd.", booth="A1", hall="2", country="Exampleland", website="WWW.Synthetic-Optics.example.com/", categories="Optics; Lasers", products="Lens | Mirror", description="  A synthetic company.  ", participation_type="Exhibitor")])
    (company,), (part,) = result.companies, result.participations
    assert SCHEMAS.errors("company", company) == [] and SCHEMAS.errors("participation", part) == []
    assert company["name"] == "Synthetic Optics Ltd." and company["status"] == "active" and company["verification_status"] == "unverified"
    assert company["country"] == "ZZ" and company["website"] == "https://www.synthetic-optics.example.com" and company["domains"] == ["www.synthetic-optics.example.com"]
    assert company["source_ids"] == [S1] and company["first_seen_at"] == STAMPS[S1] and "field_sources" not in company and company["description"] == "A synthetic company."
    assert part["company_id"] == company["company_id"] and part["edition_id"] == ED and part["listing_status"] == "listed"
    assert (part["booth"], part["hall"], part["country_as_listed"]) == ("A1", "2", "Exampleland")
    assert part["categories_as_listed"] == ["Optics", "Lasers"] and part["products_as_listed"] == ["Lens", "Mirror"] and part["participation_type"] == "exhibitor"
    assert (part["first_seen_at"], part["last_seen_at"]) == (STAMPS[S1], STAMPS[S1])
    assert result.report.summary() == {"rows_in": 1, "rows_rejected": 0, "warnings": 0, "merged_rows": 0, "candidates": 0, "conflicts": 0}


def test_nothing_is_invented_for_missing_fields():
    (company,), (part,) = (lambda r: (r.companies, r.participations))(build([row("Bare Name")]))
    assert set(company) == {"company_id", "name", "status", "source_ids", "verification_status", "first_seen_at"}
    assert set(part) == {"participation_id", "company_id", "edition_id", "exhibitor_name_as_listed", "participation_type", "listing_status", "first_seen_at", "last_seen_at", "source_ids", "verification_status"}
    assert part["participation_type"] == "unknown"


def test_empty_input_builds_nothing():
    result = build([])
    assert result.companies == [] and result.participations == [] and result.report.rows_in == 0


def test_unusable_rows_are_reported_not_silently_dropped():
    result = build([row("OK Name"), RawListing({"booth": "A1"}, S1), row("   "), row("---"), RawListing({"exhibitor_name_as_listed": None}, S2)])
    assert len(result.companies) == 1
    reasons = [r["reason"] for r in result.report.rows_rejected]
    assert [r["row"] for r in result.report.rows_rejected] == [1, 2, 3, 4] and "no exhibitor_name_as_listed" in reasons[0] and "no letters or digits" in reasons[2]


def test_bad_values_are_dropped_with_warnings_but_raw_text_is_kept():
    result = build([row("Acme", country="Atlantis", website="not a url", participation_type="VIP")])
    company, part = result.companies[0], result.participations[0]
    assert "country" not in company and part["country_as_listed"] == "Atlantis" and "website" not in company and "website_as_listed" not in part
    assert part["participation_type"] == "unknown"
    assert len(result.report.warnings) == 3 and any("Atlantis" in w for w in result.report.warnings)


def test_unknown_source_is_an_error():
    with pytest.raises(BuildError, match="no retrieved_at"):
        build_records([row("A", source="src_01JCS000000000000000000009")], edition_id=ED, retrieved_at=STAMPS, registry=registry())


def test_long_values_are_truncated_to_the_schema_limits():
    result = build([row("N" * 700, booth="B" * 700, description="D" * 5000)])
    assert len(result.companies[0]["name"]) == 500 and len(result.participations[0]["booth"]) == 500 and len(result.companies[0]["description"]) == 4000


# --- build: duplicates, matching, stability -------------------------------------------------------


def test_duplicate_rows_collapse_into_one_company_and_one_participation():
    rows = [row("Synthetic Optics Ltd.", S1, booth="A1", country="Exampleland", website="https://a.example.com"), row("SYNTHETIC OPTICS LTD", S2, booth="B2", hall="3", categories="Lasers")]
    result = build(rows)
    (company,), (part,) = result.companies, result.participations
    assert company["source_ids"] == [S1, S2] and company["aliases"] == [{"name": "SYNTHETIC OPTICS LTD", "source_ids": [S2]}]
    assert company["field_sources"] == {"website": [S1], "country": [S1]}  # only the first row had them
    assert part["booth"] == "A1" and part["hall"] == "3" and "booth also listed as: B2" in part["notes"] and "several spellings" in part["notes"]
    assert part["first_seen_at"] == STAMPS[S1] and part["last_seen_at"] == STAMPS[S2] and part["categories_as_listed"] == ["Lasers"]
    assert result.report.merged_rows == [{"company_id": company["company_id"], "rows": [0, 1], "listed_as": ["SYNTHETIC OPTICS LTD", "Synthetic Optics Ltd."], "reason": "identical exact name key"}]


def test_same_name_in_the_next_edition_keeps_the_company_id():
    reg = registry()
    first = build([row("Synthetic Optics Ltd.", country="Exampleland")], reg)
    second = build([row("synthetic optics ltd", S3)], reg, edition="example-expo-2027")
    assert second.companies[0]["company_id"] == first.companies[0]["company_id"]
    assert second.participations[0]["participation_id"] != first.participations[0]["participation_id"]
    again = build([row("Synthetic Optics Ltd.")], reg)
    assert again.participations[0]["participation_id"] == first.participations[0]["participation_id"]  # stable per edition


def test_ids_survive_a_registry_round_trip(tmp_path):
    reg = registry()
    first = build([row("Acme Demo")], reg)
    reg.save(tmp_path / "r.json")
    second = build([row("Acme Demo", S2)], CompanyRegistry.load(tmp_path / "r.json", rand=counter_rand()))
    assert second.companies[0]["company_id"] == first.companies[0]["company_id"]
    assert second.participations[0]["participation_id"] == first.participations[0]["participation_id"]


def test_different_countries_are_different_companies_and_reported():
    result = build([row("Acme Demo", country="Exampleland"), row("Acme Demo", S2, country="Testonia")])
    a, b = result.companies
    assert a["company_id"] != b["company_id"] and {a["country"], b["country"]} == {"ZZ", "TT"}
    assert result.report.conflicts[0]["kind"] == "country_conflict" and result.report.merged_rows == []
    assert result.report.candidates == [{"companies": sorted([a["company_id"], b["company_id"]]), "reason": "same listed name but the countries differ"}]


def test_similar_names_are_candidates_never_merged():
    result = build([row("Acme Ltd"), row("Acme Inc", S2), row("Totally Different", S3, website="https://www.acme-site.example.com"), row("Another", S3, website="https://acme-site.example.com/x")])
    assert len(result.companies) == 4 and result.report.merged_rows == []
    reasons = sorted(c["reason"] for c in result.report.candidates)
    assert reasons == ["same name apart from legal form", "same website"]


def test_candidates_include_companies_from_earlier_packages():
    reg = registry()
    old = build([row("Acme Ltd")], reg)
    new = build([row("Acme Inc", S3)], reg, edition="example-expo-2027")
    assert new.companies[0]["company_id"] != old.companies[0]["company_id"]
    assert new.report.candidates[0]["companies"] == sorted([old.companies[0]["company_id"], new.companies[0]["company_id"]])


def test_output_is_sorted_by_primary_key_even_when_ids_are_assigned_in_descending_order():
    state = {"n": 1000}

    def descending(n: int) -> bytes:
        state["n"] -= 1
        return state["n"].to_bytes(n, "big")

    reg = CompanyRegistry(rand=descending, now_ms=lambda: 1_700_000_000_000)
    result = build([row(n) for n in ["One Co", "Two Co", "Three Co"]], reg)
    ids = [c["company_id"] for c in result.companies]
    assert ids == sorted(ids) and [p["participation_id"] for p in result.participations] == sorted(p["participation_id"] for p in result.participations)
    assert [c["name"] for c in result.companies] == ["Three Co", "Two Co", "One Co"]  # assigned One, Two, Three; sorted by ID the order flips


def test_output_is_deterministic_and_sorted():
    rows = [row(n, S1 if i % 2 else S2) for i, n in enumerate(["Zeta Co", "Alpha Co", "Mid Co", "Beta Co"])]
    first, second = build(rows), build(rows)
    assert first.companies == second.companies and first.participations == second.participations
    ids = [c["company_id"] for c in first.companies]
    assert ids == sorted(ids) and [p["participation_id"] for p in first.participations] == sorted(p["participation_id"] for p in first.participations)


def test_row_order_does_not_change_which_company_a_name_belongs_to():
    # identity comes from the registry, not from the order rows arrive in
    reg = registry()
    first = build([row("A One"), row("B Two")], reg)
    second = build([row("B Two", S2), row("A One", S2)], reg, edition="example-expo-2027")
    by_name = lambda r: {c["name"]: c["company_id"] for c in r.companies}  # noqa: E731
    assert by_name(first) == by_name(second)


def test_invalid_builder_output_raises(monkeypatch):
    class Broken(SchemaSet):
        def errors(self, entity, instance):
            return ["simulated schema failure"]

    with pytest.raises(BuildError, match="simulated schema failure"):
        build([row("A")], schemas=Broken())


def test_every_participation_points_at_a_built_company():
    result = build([row("Acme Demo", country="Exampleland", website="https://acme.example.com"), row("Beta Test", S2)])
    ids = {c["company_id"] for c in result.companies}
    assert len(ids) == 2 and {p["company_id"] for p in result.participations} == ids  # referential integrity (R10) holds by construction
