"""Static safety checks for .github/workflows (D2-05, total specification §4).

These cannot prove a workflow runs; they guard the properties that must never regress: least privilege,
no writes to main, no untrusted input inside shell code, concurrency, timeouts, no secrets.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
CRAWL = ROOT / ".github" / "workflows" / "crawl.yml"
ALLOWED_ACTIONS = {"actions/checkout@v4", "actions/setup-python@v5"}


def load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # YAML 1.1 reads the key `on` as True
    return data


def run_blocks(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job["steps"]:
            if "run" in step:
                yield job_name, step["run"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
class TestEveryWorkflow:
    def test_default_permissions_are_empty(self, path):
        assert load(path)["permissions"] == {}

    def test_no_dangerous_triggers(self, path):
        triggers = set(load(path)["on"])
        assert not triggers & {"pull_request_target", "workflow_run", "issue_comment", "repository_dispatch"}

    def test_jobs_have_timeouts_and_pinned_runner(self, path):
        for name, job in load(path)["jobs"].items():
            assert isinstance(job.get("timeout-minutes"), int) and job["timeout-minutes"] <= 120, name
            assert re.fullmatch(r"ubuntu-\d\d\.\d\d", job["runs-on"]), name

    def test_only_known_actions(self, path):
        for job in load(path)["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert step["uses"] in ALLOWED_ACTIONS, step["uses"]

    def test_untrusted_expressions_never_appear_inside_shell_code(self, path):
        untrusted = re.compile(r"\$\{\{\s*(inputs\.|github\.event\.|github\.head_ref|matrix\.|steps\.[\w-]+\.outputs\.|needs\.)")
        for job_name, script in run_blocks(load(path)):
            assert not untrusted.search(script), f"{job_name}: expression interpolated into a run block"

    def test_no_secrets_and_no_push_to_main(self, path):
        text = path.read_text(encoding="utf-8")
        assert "secrets." not in text.replace("secrets.GITHUB_TOKEN", "")
        for _, script in run_blocks(load(path)):
            assert not re.search(r"git push[^\n]*\b(main|master)\b", script)
            assert "--force" not in script and "push -f" not in script


class TestCrawlWorkflow:
    wf = load(CRAWL)

    def test_triggers_and_inputs(self):
        assert set(self.wf["on"]) == {"workflow_dispatch", "schedule"}
        inputs = self.wf["on"]["workflow_dispatch"]["inputs"]
        assert set(inputs) == {"source", "max_requests", "resume_run"} and inputs["source"]["required"] is True
        assert self.wf["on"]["schedule"][0]["cron"]

    def test_only_the_crawl_job_can_write_and_only_contents_and_pull_requests(self):
        jobs = self.wf["jobs"]
        assert jobs["plan"]["permissions"] == {"contents": "read"}
        assert jobs["crawl"]["permissions"] == {"contents": "write", "pull-requests": "write"}

    def test_concurrency_per_source_without_cancelling_runs(self):
        concurrency = self.wf["jobs"]["crawl"]["concurrency"]
        assert "matrix.source" in concurrency["group"] and concurrency["cancel-in-progress"] is False

    def test_sources_run_one_at_a_time_and_failures_do_not_stop_the_others(self):
        strategy = self.wf["jobs"]["crawl"]["strategy"]
        assert strategy["max-parallel"] == 1 and strategy["fail-fast"] is False

    def test_runs_from_the_data_branch_and_opens_a_pr_to_it(self):
        assert self.wf["env"]["DATA_BRANCH"] == "dev/data-platform"
        text = CRAWL.read_text(encoding="utf-8")
        assert text.count("ref: ${{ env.DATA_BRANCH }}") == 2
        assert '--base "$DATA_BRANCH"' in text and "gh pr create" in text

    def test_pr_follows_the_merger_rules(self):
        text = CRAWL.read_text(encoding="utf-8")
        assert "【Albert 合併】" in text and "合併人：Albert。Eric 請勿合併。" in text and "--assignee acyihung-infinityandbeyond" in text

    def test_inputs_reach_the_shell_only_through_env(self):
        steps = {s.get("id"): s for s in self.wf["jobs"]["crawl"]["steps"]}
        env = steps["run"]["env"]
        assert {"SOURCE", "MAX_REQUESTS", "RESUME_RUN"} <= set(env)
        assert '"$SOURCE"' in steps["run"]["run"] and '"$RESUME_RUN"' in steps["run"]["run"]

    def test_plan_job_also_receives_inputs_through_env(self):
        plan = {s.get("id"): s for s in self.wf["jobs"]["plan"]["steps"]}["plan"]
        assert {"EVENT", "SOURCE"} <= set(plan["env"]) and 'os.environ["SOURCE"]' in plan["run"]

    def test_plan_skips_the_crawl_when_nothing_is_selected(self):
        assert "!= '[]'" in self.wf["jobs"]["crawl"]["if"]

    def test_only_the_cli_entry_point_is_used(self):
        scripts = "\n".join(s for _, s in run_blocks(self.wf))
        assert "python -m crawler.cli" in scripts and "curl" not in scripts and "wget" not in scripts
