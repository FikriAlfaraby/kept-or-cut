"""Run every configuration on every case and keep what the agent would read.

    uv run python scripts/compress.py              # every tool
    uv run python scripts/compress.py headroom     # one tool (rtk, caveman or headroom); the others stay as recorded

rtk runs live, in the same planted state as the raw capture, through the command its hook rewrites to. The other
configurations read the captured raw output. Everything is written to corpus/<case>/<configuration>.txt.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.cases import CASES, EXPLORATORY
from kept_or_cut.plant import planted, public, run
from kept_or_cut.tools import caveman_engine, caveman_hook_wraps, headroom, rtk_rewrite

sys.path.insert(0, str(ROOT / "scripts"))
from capture_raw import clean, tidy, untracked

TOOLS = ("rtk", "caveman", "headroom")
wanted = set(sys.argv[1:]) or set(TOOLS)
if wanted - set(TOOLS):
    raise SystemExit(f"unknown tool: {', '.join(sorted(wanted - set(TOOLS)))}")
runs = ROOT / "corpus" / "runs.json"
log = json.loads(runs.read_text(encoding="utf-8")) if wanted != set(TOOLS) else {}
home = Path(tempfile.mkdtemp(prefix="caveman-home-"))
try:
    for case in CASES + EXPLORATORY:
        out = ROOT / "corpus" / case.id
        raw = (out / "raw.txt").read_text(encoding="utf-8")
        entry = log.get(case.id, {})

        if "rtk" in wanted:
            rewritten = rtk_rewrite(case.raw)
            if rewritten:
                before = untracked(case.repo)
                with planted(case.repo, case.edits):
                    r = run(rewritten, case.repo)
                tidy(case.repo, before)
                if not clean(case.repo):
                    raise SystemExit(f"{case.repo} is not clean after rtk on {case.id}")
                text = public(r.output)
                entry["rtk"] = {"command": list(rewritten), "exit_code": r.exit_code}
            else:
                text = raw
                entry["rtk"] = {"command": None, "note": "rtk rewrite leaves this command alone"}
            (out / "rtk.txt").write_text(text, encoding="utf-8")

        if "caveman" in wanted:
            engine, stats = caveman_engine(raw, home)
            (out / "caveman-engine.txt").write_text(engine, encoding="utf-8")
            entry["caveman-engine"] = stats
            wraps = caveman_hook_wraps(case.raw)
            (out / "caveman-hook.txt").write_text(engine if wraps else raw, encoding="utf-8")
            entry["caveman-hook"] = {"wraps": wraps}

        if "headroom" in wanted:
            for name, aggressive, unprotected in (
                ("headroom-default", False, False),
                ("headroom-aggressive", True, False),
                ("headroom-unprotected", True, True),
            ):
                text, stats = headroom(raw, case.raw, aggressive, unprotected)
                (out / f"{name}.txt").write_text(text, encoding="utf-8")
                entry[name] = stats
        log[case.id] = entry
        print(case.id, "done")
finally:
    shutil.rmtree(home, ignore_errors=True)
runs.write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
