"""Tests for etl.normalize (D2-07): cleaning, name keys, websites, lists, countries."""
from __future__ import annotations

import pytest

from etl.normalize import clean_text, name_keys, normalize_country, normalize_website, site_key, split_list


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Acme   Demo \n Ltd ", "Acme Demo Ltd"),
        ("Acme​Demo", "AcmeDemo"),  # zero-width space removed
        ("a\x00b\x07c", "abc"),  # control characters removed
        ("Ａｃｍｅ　Demo", "Acme Demo"),  # full-width forms, ideographic space (NFKC)
        ("a b", "a b"),
        ("tab\tsep", "tab sep"),
        ("", ""), (None, ""), (12, "12"),
        ("Müller", "Müller"),  # case and accents are not touched
        ("ＡＢＣ", "ABC"),
    ],
)
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


def test_clean_text_does_not_change_case_or_translate():
    assert clean_text("SYNTHETIC optics 測試") == "SYNTHETIC optics 測試"


@pytest.mark.parametrize(
    "a,b",
    [
        ("Synthetic Optics Ltd.", "SYNTHETIC OPTICS LTD"),
        ("Synthetic-Optics Ltd", "synthetic optics ltd"),
        ("Ｓynthetic Optics Ltd", "Synthetic Optics Ltd"),
        ("S.A. Demo", "SA Demo"),
    ],
)
def test_exact_key_ignores_case_punctuation_spacing_and_width(a, b):
    assert name_keys(a).exact == name_keys(b).exact


@pytest.mark.parametrize("a,b", [("Acme Ltd", "Acme Inc"), ("Acme", "Acme Ltd"), ("Acme Labs", "Acme"), ("Müller", "Muller"), ("Acme 2", "Acme")])
def test_exact_key_keeps_legal_forms_and_real_differences(a, b):
    assert name_keys(a).exact != name_keys(b).exact


@pytest.mark.parametrize(
    "a,b",
    [("Acme Ltd", "Acme Inc"), ("Acme Co., Ltd.", "Acme"), ("Acme GmbH", "ACME"), ("測試股份有限公司", "測試"), ("株式会社 Example", "Example"), ("Example 株式会社", "Example")],
)
def test_loose_key_ignores_legal_forms(a, b):
    assert name_keys(a).loose == name_keys(b).loose


def test_loose_key_never_empties_a_name():
    assert name_keys("Ltd").loose == "ltd" and name_keys("有限公司").loose == "有限公司" and name_keys("Co Ltd").loose == "co"


def test_loose_key_only_strips_trailing_western_forms():
    assert name_keys("Limited Edition Optics").loose == "limitededitionoptics"


@pytest.mark.parametrize("name", ["", "   ", "---", "...!!", "​"])
def test_name_without_letters_or_digits_is_rejected(name):
    with pytest.raises(ValueError):
        name_keys(name)


def test_digits_count_as_name():
    assert name_keys("3M").exact == "3m"


@pytest.mark.parametrize(
    "raw,url,host",
    [
        ("https://www.Example.COM/", "https://www.example.com", "www.example.com"),
        ("www.example.com", "https://www.example.com", "www.example.com"),
        ("http://example.com:80/a/b?x=1#frag", "http://example.com/a/b?x=1", "example.com"),
        ("https://example.com:443", "https://example.com", "example.com"),
        ("https://example.com:8443/x", "https://example.com:8443/x", "example.com"),
        ("//example.com/p", "https://example.com/p", "example.com"),
        ("https://example.com./x", "https://example.com/x", "example.com"),
        ("münchen.de", "https://xn--mnchen-3ya.de", "xn--mnchen-3ya.de"),
        ("  https://Example.com/A  ", "https://example.com/A", "example.com"),
    ],
)
def test_normalize_website(raw, url, host):
    site = normalize_website(raw)
    assert (site.url, site.hostname) == (url, host)


@pytest.mark.parametrize(
    "raw",
    ["", None, "not a url", "mailto:a@b.com", "javascript:alert(1)", "ftp://example.com", "file:///etc/passwd", "https://user:pw@example.com", "http://127.0.0.1/x", "http://[::1]/", "https://localhost", "https://example", "http://", "https://exa mple.com", "https://-bad.com", "https://example.com:99999", "https://" + "a" * 64 + ".com", "https://example.com/" + "x" * 2100],
)
def test_unusable_websites_are_none(raw):
    assert normalize_website(raw) is None


def test_site_key():
    assert site_key("www.example.com") == "example.com" and site_key("shop.example.com") == "shop.example.com"


def test_split_list():
    assert split_list("a; b |a\nc、d；e") == ["a", "b", "c", "d", "e"]
    assert split_list(["x", " x ", "", "y"]) == ["x", "y"]
    assert split_list(None) == [] and split_list("  ;; ") == []
    assert split_list("a" * 600) == ["a" * 500]


def test_normalize_country_uses_only_the_given_aliases():
    aliases = {"exampleland": "ZZ", "bad": "zz", "worse": "ZZZ"}
    assert normalize_country("  ExampleLand ", aliases) == "ZZ"
    assert normalize_country("Testonia", aliases) is None
    assert normalize_country("ZZ", aliases) is None  # no built-in guessing, not even for codes
    assert normalize_country("bad", aliases) is None and normalize_country("worse", aliases) is None
    assert normalize_country(None, aliases) is None
