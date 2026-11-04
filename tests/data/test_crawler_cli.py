"""Tests for crawler.cli, crawler.resume and the pending-URL bookkeeping (D2-05)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from crawler.adapters import AdapterRegistry
from crawler.cli import main, scheduled_sources, source_path
from crawler.errors import ErrorCode
from crawler.fetch import FetchError
from crawler.resume import ResumeError, plan_resume
from crawler.runner import RunOptions, run_source
from crawler.store import RunStore, verify_run
from tests.data.crawl_testkit import FakeClock, FakeFetcher, fixed_rand, make_config, scripted_adapter
from tests.data.test_crawler_runner import ROBOTS, START, rows_adapter

BASE = "https://www.example.com/"
CONFIG = (
    'name = "demo-source"\nexhibition_id = "example-expo"\nedition_id = "example-expo-2026"\n'
    'source_type = "official_exhibitor_list"\nstart_urls = ["https://www.example.com/list"]\n'
    'allowed_domains = ["example.com"]\nrate_limit_per_second = 1000\nmax_retries = 0\nadapter = "demo"\n'
)


def adapters() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(type(rows_adapter(name="demo")), name="demo")
    return registry


@pytest.fixture
def env(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "demo-source.toml").write_text(CONFIG, encoding="utf-8")
    return sources, tmp_path / "raw"


def cli(env, *extra, script=None, fetcher=None):
    sources, raw = env
    out, err = io.StringIO(), io.StringIO()
    code = main(["run", "--source", "demo-source", "--sources-dir", str(sources), "--out", str(raw), *extra], fetcher=fetcher or FakeFetcher(script or {}), adapters=adapters(), out=out, err=err)
    values = dict(line.split("=", 1) for line in out.getvalue().splitlines() if "=" in line)
    return code, values, err.getvalue()


# --- run ----------------------------------------------------------------------------------


def test_run_stores_evidence_and_prints_outputs(env):
    code, out, err = cli(env, script={ROBOTS: 404, START: "<p>x</p>"})
    assert code == 0 and err == ""
    assert out["status"] == "succeeded" and out["snapshots"] == "1" and out["errors"] == "0" and out["pending"] == "0"
    run_dir = Path(out["run_dir"])
    assert run_dir.name == out["crawl_run_id"] and verify_run(run_dir) == []
    assert json.loads((run_dir / "crawl_run.json").read_text(encoding="utf-8"))["trigger"] == "manual"


def test_failed_source_is_recorded_with_exit_code_zero(env):
    code, out, _ = cli(env, script={ROBOTS: 404, START: 403})
    assert code == 0 and out["status"] == "failed" and out["errors"] == "1"
    assert verify_run(Path(out["run_dir"])) == []


def test_trigger_option(env):
    _, out, _ = cli(env, "--trigger", "schedule", script={ROBOTS: 404, START: "x"})
    assert json.loads((Path(out["run_dir"]) / "crawl_run.json").read_text(encoding="utf-8"))["trigger"] == "schedule"


def test_github_environment_is_recorded(env, monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    _, out, _ = cli(env, script={ROBOTS: 404, START: "x"})
    record = json.loads((Path(out["run_dir"]) / "crawl_run.json").read_text(encoding="utf-8"))
    assert record["code_commit"] == "a" * 40 and record["github_run_url"] == "https://github.com/owner/repo/actions/runs/12345"


@pytest.mark.parametrize(
    "sha,server,repo,run_id,has_commit,has_url",
    [
        ("not-a-sha", "https://github.com", "owner/repo", "1", False, True),
        ("a" * 40, "http://evil", "owner/repo", "1", True, False),
        ("a" * 40, "https://github.com", "owner/re po", "1", True, False),
        ("a" * 40, "https://github.com", "owner/repo", "12x", True, False),
    ],
)
def test_github_environment_values_are_checked_one_by_one(env, monkeypatch, sha, server, repo, run_id, has_commit, has_url):
    for key, value in (("GITHUB_SHA", sha), ("GITHUB_SERVER_URL", server), ("GITHUB_REPOSITORY", repo), ("GITHUB_RUN_ID", run_id)):
        monkeypatch.setenv(key, value)
    _, out, _ = cli(env, script={ROBOTS: 404, START: "x"})
    record = json.loads((Path(out["run_dir"]) / "crawl_run.json").read_text(encoding="utf-8"))
    assert ("code_commit" in record) is has_commit and ("github_run_url" in record) is has_url


def test_max_requests_limits_and_leaves_pending(env):
    urls = [f"{BASE}p{i}" for i in range(4)]
    script = {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: "x" for u in urls}}
    _, out, _ = cli(env, "--max-requests", "2", script=script)
    assert out["status"] == "partial" and out["snapshots"] == "2" and out["pending"] == "3"
    assert sorted(json.loads((Path(out["run_dir"]) / "pending.json").read_text(encoding="utf-8"))) == sorted(urls[1:])


@pytest.mark.parametrize("value", ["0", "-3", "5001", "x"])
def test_bad_max_requests(env, value):
    code, out, err = cli(env, "--max-requests", value, script={START: "x"})
    assert code == 2 and out == {} and not (env[1]).exists()


# --- untrusted input --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["../demo-source", "demo/source", "Demo", "demo source", "-x", "", "demo-source.toml", "demo_source", "a" * 70, "$(id)", "demo;ls"])
def test_hostile_source_names_are_refused(env, name):
    sources, raw = env
    out, err = io.StringIO(), io.StringIO()
    code = main(["run", "--source", name, "--sources-dir", str(sources), "--out", str(raw)], fetcher=FakeFetcher({}), adapters=adapters(), out=out, err=err)
    assert code == 2 and out.getvalue() == "" and not raw.exists()


@pytest.mark.parametrize("name", ["Demo", "demo_source", "demo.source"])
def test_names_outside_the_pattern_are_refused_even_if_such_a_file_exists(env, name):
    sources, raw = env
    (sources / f"{name}.toml").write_text(CONFIG.replace("demo-source", name), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = main(["run", "--source", name, "--sources-dir", str(sources), "--out", str(raw)], fetcher=FakeFetcher({}), adapters=adapters(), out=out, err=err)
    assert code == 2 and "lowercase letters" in err.getvalue() and not raw.exists()


def test_a_run_that_fails_verification_is_not_reported_as_success(env, monkeypatch):
    import crawler.cli as module

    monkeypatch.setattr(module, "verify_run", lambda run_dir: ["simulated damage"])
    code, out, err = cli(env, script={ROBOTS: 404, START: "x"})
    assert code == 2 and "failed verification" in err and out == {}


def test_config_name_must_match_file_name(env):
    sources, _ = env
    (sources / "other-name.toml").write_text(CONFIG, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = main(["run", "--source", "other-name", "--sources-dir", str(sources), "--out", str(env[1])], fetcher=FakeFetcher({}), adapters=adapters(), out=out, err=err)
    assert code == 2 and "must equal its file name" in err.getvalue()


def test_symlink_out_of_the_sources_directory_is_refused(env, tmp_path):
    sources, _ = env
    outside = tmp_path / "outside.toml"
    outside.write_text(CONFIG.replace("demo-source", "evil"), encoding="utf-8")
    (sources / "evil.toml").symlink_to(outside)
    with pytest.raises(Exception, match="inside the sources directory"):
        source_path("evil", sources)


def test_unknown_adapter_and_bad_config_exit_two(env):
    sources, raw = env
    (sources / "demo-source.toml").write_text(CONFIG.replace('adapter = "demo"', 'adapter = "missing"'), encoding="utf-8")
    code, _, err = cli(env, script={})
    assert code == 2 and "no adapter named" in err
    (sources / "demo-source.toml").write_text("not = [toml", encoding="utf-8")
    assert cli(env, script={})[0] == 2
    assert not raw.exists()


def test_argument_errors_exit_two():
    assert main([], err=io.StringIO()) == 2
    assert main(["run"], err=io.StringIO()) == 2


# --- scheduled ----------------------------------------------------------------------------------


def run_scheduled(path):
    out, err = io.StringIO(), io.StringIO()
    code = main(["scheduled", "--schedule", str(path)], out=out, err=err)
    return code, out.getvalue().strip(), err.getvalue()


def test_scheduled_lists_sources_or_nothing(tmp_path):
    assert run_scheduled(tmp_path / "missing.toml") == (0, "[]", "")
    path = tmp_path / "s.toml"
    path.write_text('sources = ["a-one", "b-two"]\n', encoding="utf-8")
    assert run_scheduled(path) == (0, '["a-one", "b-two"]', "")


@pytest.mark.parametrize("text", ['sources = "a"', 'sources = ["A"]', 'sources = ["a", "a"]', 'sources = [1]', 'other = 1', 'sources = ["../x"]', "bad = ["])
def test_scheduled_rejects_bad_files(tmp_path, text):
    path = tmp_path / "s.toml"
    path.write_text(text, encoding="utf-8")
    code, out, err = run_scheduled(path)
    assert code == 2 and out == "" and "error" in err


def test_the_shipped_schedule_is_empty_and_valid():
    root = Path(__file__).resolve().parents[2]
    assert scheduled_sources(root / "crawler" / "schedule.toml") == []


# --- resume --------------------------------------------------------------------------------------


def first_run(env, script, *flags):
    _, out, _ = cli(env, *flags, script=script)
    return out


def test_resume_fetches_only_what_is_missing_and_links_the_runs(env):
    urls = [f"{BASE}p{i}" for i in range(4)]
    first = first_run(env, {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: "x" for u in urls}}, "--max-requests", "2")
    fetcher = FakeFetcher({ROBOTS: 404, **{u: "x" for u in urls}})
    code, out, err = cli(env, "--resume", first["crawl_run_id"], fetcher=fetcher)
    assert code == 0, err
    assert START not in fetcher.calls and urls[0] not in fetcher.calls  # already retrieved by the first run
    assert sorted(c for c in fetcher.calls if c != ROBOTS) == sorted(urls[1:])
    assert out["status"] == "succeeded" and out["crawl_run_id"] != first["crawl_run_id"]
    record = json.loads((Path(out["run_dir"]) / "crawl_run.json").read_text(encoding="utf-8"))
    assert record["notes"].startswith(f"resumes {first['crawl_run_id']}")
    assert verify_run(Path(first["run_dir"])) == []  # the earlier run is untouched
    assert (Path(first["run_dir"]) / "pending.json").read_text(encoding="utf-8").count("http") == 3


def test_resume_retries_temporary_errors_only(env):
    a, b, c, d = (f"{BASE}{x}" for x in "abcd")
    script = {ROBOTS: 404, START: f"follow:{a},{b},{c},{d}", a: 503, b: 404, c: FetchError(ErrorCode.TIMEOUT, "slow"), d: FetchError(ErrorCode.NETWORK_ERROR, "down")}
    first = first_run(env, script)
    fetcher = FakeFetcher({ROBOTS: 404, a: "ok", b: "should not be fetched", c: "ok", d: "ok"})
    code, out, _ = cli(env, "--resume", first["run_dir"], fetcher=fetcher)
    assert code == 0 and sorted(c for c in fetcher.calls if c != ROBOTS) == sorted([a, c, d])
    assert b not in fetcher.calls


def test_resume_refused_after_a_block(env):
    a = f"{BASE}a"
    first = first_run(env, {ROBOTS: 404, START: f"follow:{a}", a: 429})
    code, out, err = cli(env, "--resume", first["crawl_run_id"], fetcher=FakeFetcher({}))
    assert code == 2 and "blocked by the site" in err and out == {}


def test_robots_disallow_is_not_a_block_but_is_not_retried(env):
    a, b = f"{BASE}private/x", f"{BASE}b"
    script = {ROBOTS: "User-agent: *\nDisallow: /private/\n", START: f"follow:{a},{b}", a: "no", b: 503}
    first = first_run(env, script)
    fetcher = FakeFetcher({ROBOTS: "User-agent: *\nDisallow: /private/\n", a: "no", b: "ok"})
    code, _, _ = cli(env, "--resume", first["crawl_run_id"], fetcher=fetcher)
    assert code == 0 and [c for c in fetcher.calls if c != ROBOTS] == [b]


def test_resume_with_nothing_to_do(env):
    first = first_run(env, {ROBOTS: 404, START: "x"})
    code, _, err = cli(env, "--resume", first["crawl_run_id"], fetcher=FakeFetcher({}))
    assert code == 2 and "nothing to resume" in err


@pytest.mark.parametrize("value", ["run_01JCR000000000000000000009", "../../etc", "nope", "/etc"])
def test_resume_with_unknown_or_hostile_value(env, value):
    first_run(env, {ROBOTS: 404, START: 500})
    code, _, err = cli(env, "--resume", value, fetcher=FakeFetcher({}))
    assert code == 2 and "error:" in err


def test_resume_directory_outside_out_is_refused(env, tmp_path):
    first = first_run(env, {ROBOTS: 404, START: 500})
    elsewhere = tmp_path / "elsewhere" / "a" / "b" / Path(first["run_dir"]).name
    elsewhere.parent.mkdir(parents=True)
    import shutil

    shutil.copytree(first["run_dir"], elsewhere)
    code, _, err = cli(env, "--resume", str(elsewhere), fetcher=FakeFetcher({}))
    assert code == 2 and "under --out" in err


def test_plan_resume_never_retries_errors_a_fetch_cannot_fix(env):
    a, b, c, d, e = (f"{BASE}{x}" for x in "abcde")
    first = first_run(env, {ROBOTS: 404, START: f"follow:{a}"})
    run_dir = Path(first["run_dir"])
    (run_dir / "errors.json").write_text(json.dumps([
        {"code": "parse_error", "url": a, "message": "m"}, {"code": "access_blocked", "url": b, "message": "robots"},
        {"code": "config_invalid", "url": c, "message": "m"}, {"code": "unexpected", "url": d, "message": "m"},
        {"code": "http_error", "url": e, "message": "too big", "http_status": 200}, {"code": "timeout", "url": START, "message": "m"},
    ]), encoding="utf-8")
    (run_dir / "pending.json").write_text("[]", encoding="utf-8")
    plan = plan_resume(run_dir, make_config())
    assert plan.urls == (START,) and plan.reasons == {START: "timeout"}


def test_plan_resume_rejects_other_editions(env):
    first = first_run(env, {ROBOTS: 404, START: 500})
    other = make_config(edition_id="example-expo-2027")
    with pytest.raises(ResumeError, match="belongs to"):
        plan_resume(first["run_dir"], other)


def test_plan_resume_rejects_tampered_run_files(env):
    first = first_run(env, {ROBOTS: 404, START: 500})
    run_dir = Path(first["run_dir"])
    config = make_config()
    (run_dir / "errors.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ResumeError, match="malformed"):
        plan_resume(run_dir, config)
    (run_dir / "errors.json").write_text("not json", encoding="utf-8")
    with pytest.raises(ResumeError, match="cannot read"):
        plan_resume(run_dir, config)
    (run_dir / "crawl_run.json").unlink()
    with pytest.raises(ResumeError, match="not a finished run"):
        plan_resume(run_dir, config)


# --- runner: pending bookkeeping ---------------------------------------------------------------------


def test_runner_reports_pending_urls_for_max_requests_and_cancel():
    urls = [f"{BASE}p{i}" for i in range(4)]
    script = {ROBOTS: 404, START: "follow:" + ",".join(urls), **{u: "x" for u in urls}}
    result = run_source(make_config(), rows_adapter(), FakeFetcher(script), clock=FakeClock(), rand=fixed_rand, options=RunOptions(max_requests=2))
    assert sorted(result.pending) == sorted(urls[1:]) and "3 URL(s)" in result.crawl_run["notes"]
    calls = {"n": 0}

    def cancel():
        calls["n"] += 1
        return calls["n"] > 1

    cancelled = run_source(make_config(), rows_adapter(), FakeFetcher(script), clock=FakeClock(), rand=fixed_rand, cancel=cancel)
    assert cancelled.status == "cancelled" and sorted(cancelled.pending) == sorted(urls)


def test_pending_excludes_out_of_scope_and_seen_urls():
    script = {ROBOTS: 404, START: f"follow:{BASE}ok,https://other.org/x,{START},{BASE}ok2"}
    result = run_source(make_config(), rows_adapter(), FakeFetcher({**script, f"{BASE}ok": "x"}), clock=FakeClock(), rand=fixed_rand, options=RunOptions(max_requests=1))
    assert sorted(result.pending) == [f"{BASE}ok", f"{BASE}ok2"]  # the other-origin URL and the already fetched start URL are not pending


def test_start_requests_override_and_resumes_note():
    fetcher = FakeFetcher({ROBOTS: 404, f"{BASE}only": "x"})
    from crawler.models import Request

    result = run_source(make_config(), rows_adapter(), fetcher, clock=FakeClock(), rand=fixed_rand, options=RunOptions(resumes="run_01JCR000000000000000000001"), start_requests=[Request(f"{BASE}only")])
    assert fetcher.calls == [ROBOTS, f"{BASE}only"] and result.crawl_run["notes"].startswith("resumes run_01JCR000000000000000000001")
    assert result.status == "succeeded"


def test_store_writes_pending_json(tmp_path):
    config = make_config()
    store = RunStore(tmp_path, config)
    urls = [f"{BASE}p{i}" for i in range(3)]
    result = run_source(config, rows_adapter(), FakeFetcher({ROBOTS: 404, START: "follow:" + ",".join(urls)}), clock=FakeClock(), rand=fixed_rand, sink=store, options=RunOptions(max_requests=1))
    directory = store.finalize(result)
    assert json.loads((directory / "pending.json").read_text(encoding="utf-8")) == sorted(urls)
