"""A3-08: reproducibility check for the ExhibitIQ Skill's deterministic tools.

Runs every deterministic command on the committed samples and prints one SHA-256 per output. Two independent
cloud workspaces (Eric's and Albert's) must print identical digests; `--check` compares with the committed
skills/exhibitiq/repro/expected-digest.json and exits 1 on any difference.

  python skills/exhibitiq/scripts/repro_check.py            # print digests
  python skills/exhibitiq/scripts/repro_check.py --check    # compare with the committed digests
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import exhibitiq_tools as tools  # noqa: E402
import profile_tools as pt  # noqa: E402

EXPECTED = ROOT / "skills" / "exhibitiq" / "repro" / "expected-digest.json"
EX = ROOT / "schemas" / "v1" / "examples"
G = ROOT / "data" / "samples" / "golden" / "v1"


def _h(obj) -> str:
    text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def digests() -> dict[str, str]:
    out = {}
    for name, pkg in (("example", EX / "package"), ("golden", G / "package")):
        out[f"validate-package:{name}"] = _h(tools.validate_package(pkg)["ok"])
        for prof in ("default-library", "bxr-opportunity"):
            out[f"classify:{name}:{prof}"] = _h(tools.classify(pkg, prof))
            out[f"relate:{name}:{prof}"] = _h(tools.relate(pkg, prof))
        out[f"score:{name}:opportunity@1"] = _h(tools.score(pkg))
    for prof in ("default-library", "bxr-opportunity"):
        out[f"config:{prof}"] = _h(pt.analysis_config(prof))
    out["compare:example+golden"] = _h(pt.compare([EX / "package", G / "package"]))
    out["report:example"] = _h(tools.render_report(EX / "analysis" / "analysis_result.with_config.example.json", EX / "package"))
    out["report:golden"] = _h(tools.render_report(G / "expected" / "analysis" / "analysis_result.json", G / "package"))
    return out


def main(argv: list[str]) -> int:
    d = digests()
    if "--check" not in argv:
        print(json.dumps({"python": platform.python_version(), "digests": d}, ensure_ascii=False, indent=2))
        return 0
    exp = json.loads(EXPECTED.read_text(encoding="utf-8"))["digests"]
    diff = sorted(k for k in set(d) | set(exp) if d.get(k) != exp.get(k))
    print(json.dumps({"ok": not diff, "different": diff}, ensure_ascii=False, indent=2))
    return 0 if not diff else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
