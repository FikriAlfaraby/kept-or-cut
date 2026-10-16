"""Scoring part 2: what each model believed after reading each view (PREDICTIONS-2.md).

uv run python -m kept_or_cut.beliefs_score      # prints the summary and the prediction verdicts as JSON
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .analyze import CORPUS
from .beliefs import parse
from .cases import CASES, EXPLORATORY
from .claude_code import views as cc_views
from .needed import needed

BELIEFS = CORPUS / "beliefs"
VIEWS = ("full", "cc-raw", "cc-rtk", "cc-caveman-engine", "cc-headroom-proxy")
TRIALS = 3
COUNTED = ("pytest", "vitest", "tsc", "eslint")


def base(path: str | None) -> str:
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1]


def summary_count(kind: str, raw: str) -> int | None:
    """What the run's own summary counts as failing, for the kinds that have one."""
    if kind == "pytest":
        lines = [ln for ln in raw.splitlines() if re.search(r"\d+ (failed|errors?)\b", ln) and " in " in ln]
        if not lines:
            return None
        last = lines[-1]
        failed = re.search(r"(\d+) failed", last)
        errors = re.search(r"(\d+) errors?\b", last)
        return (int(failed.group(1)) if failed else 0) + (int(errors.group(1)) if errors else 0)
    if kind == "vitest":
        m = re.search(r"Tests\s+(\d+) failed", raw)
        return int(m.group(1)) if m else None
    if kind == "tsc":
        return len(re.findall(r"error TS\d+", raw))
    if kind == "eslint":
        m = re.search(r"✖ (\d+) problems?", raw)
        return int(m.group(1)) if m else None
    return None


def truth(case) -> dict:
    raw = (CORPUS / case.id / "raw.txt").read_text(encoding="utf-8")
    facts = needed(case.kind, raw)
    return {
        "exit_code": json.loads((CORPUS / case.id / "raw.json").read_text(encoding="utf-8"))["exit_code"],
        "planted": sorted({base(e.path) for e in case.edits}),
        "count": summary_count(case.kind, raw) if case.kind in COUNTED else None,
        "names": [f.text for f in facts if f.field == "name"],
    }


def views(case, runs: dict) -> dict[str, str]:
    raw = (CORPUS / case.id / "raw.txt").read_text(encoding="utf-8")
    exit_code = truth(case)["exit_code"]
    seen = cc_views(CORPUS / case.id, runs)
    return {"full": f"Exit code {exit_code}\n{raw}".strip(), **{v: seen[v] for v in VIEWS[1:]}}


def answer_path(model: str, case_id: str, view: str, trial: int) -> Path:
    return BELIEFS / model / case_id / f"{view}-{trial}.json"


def score(t: dict, answer: dict | None) -> dict:
    if not isinstance(answer, dict):
        return {"parsed": False, "failed": False, "count": False, "names": 0, "first": False}
    listed = [str(item.get("name") or "") for item in answer.get("failing") or [] if isinstance(item, dict)]
    found = sum(any(name in got for got in listed) for name in t["names"])
    first = answer.get("first_look") if isinstance(answer.get("first_look"), dict) else {}
    return {
        "parsed": True,
        "failed": answer.get("run_failed") is True,
        "count": t["count"] is not None and answer.get("failing_count") == t["count"],
        "count_given": answer.get("failing_count"),
        "names": found,
        "first": base(first.get("file")) in t["planted"],
    }


def load(model: str, case_id: str, view: str) -> list[dict | None]:
    """Each trial's answer, parsed again from the reply as received, so a parser fix reaches every stored answer."""
    out = []
    for trial in range(TRIALS):
        path = answer_path(model, case_id, view, trial)
        out.append(parse(json.loads(path.read_text(encoding="utf-8"))["reply"]) if path.exists() else None)
    return out


def majority(flags: list[bool]) -> bool:
    return sum(flags) * 2 > len(flags)


def first_file(model: str, case_id: str, view: str) -> str | None:
    """The file a model would open first, by base name, when 2 of 3 trials agree ("" is no file); else None."""
    files = [base(((a or {}).get("first_look") or {}).get("file")) for a in load(model, case_id, view)]
    file, n = Counter(files).most_common(1)[0]
    return file if n * 2 > len(files) else None


def moved(models: tuple[str, ...] = ("luna", "gemini")) -> dict[str, list[str]]:
    """Exploratory, added after the results: the runs where a view changes the file the model would open first,
    compared with the full output. The pre-registered score (a planted file) is low for every view, because on
    several runs both models open the test file first even with the full output."""
    return {
        f"{model}/{view}": [
            c.id for c in CASES if first_file(model, c.id, view) != first_file(model, c.id, "full")
        ]
        for model in models
        for view in VIEWS[1:]
    }


def summary(models: tuple[str, ...] = ("luna", "gemini")) -> dict:
    out: dict = {"cases": {}, "totals": {}}
    for case in CASES + EXPLORATORY:
        t = truth(case)
        out["cases"][case.id] = {"truth": t, "scores": {}}
        for model in models:
            for view in VIEWS:
                scores = [score(t, a) for a in load(model, case.id, view)]
                out["cases"][case.id]["scores"][f"{model}/{view}"] = scores
    for model in models:
        for view in VIEWS:
            rows = [out["cases"][c.id]["scores"][f"{model}/{view}"] for c in CASES]
            truths = [out["cases"][c.id]["truth"] for c in CASES]
            out["totals"][f"{model}/{view}"] = {
                "answers": sum(len(r) for r in rows),
                "parsed": sum(s["parsed"] for r in rows for s in r),
                "said_failed": sum(s["failed"] for r in rows for s in r),
                "count_right": sum(
                    majority([s["count"] for s in r]) for r, t in zip(rows, truths) if t["count"]
                ),
                "counted_runs": sum(1 for t in truths if t["count"]),
                "names_found": sum(s["names"] for r in rows for s in r),
                "names": sum(len(t["names"]) for t in truths) * TRIALS,
                "first_right": sum(majority([s["first"] for s in r]) for r in rows),
            }
    return out


if __name__ == "__main__":
    print(json.dumps({"totals": summary()["totals"], "moved": moved()}, indent=1))
