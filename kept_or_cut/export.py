"""Everything the fikrialfaraby.com/compress/ page shows, as one JSON document.

    uv run python -m kept_or_cut.export > compress.json

For every case: what it is, its needed facts, and, for each Claude Code view, the text the model reads and which
facts survive in it. The totals are analyze.py's, so the page and RESULTS.md quote the same numbers. Part 2's block
("beliefs") is beliefs_score.py's, so the page and RESULTS-2.md do too.
"""

from __future__ import annotations

import json
import subprocess
import sys

from .analyze import CORPUS, ROOT, summary, tokens
from .beliefs_score import TRIALS, answer_path, first_file, load, moved, truth
from .beliefs_score import VIEWS as READ_VIEWS
from .beliefs_score import summary as beliefs_summary
from .beliefs_score import views as read_views
from .cases import CASES, EXPLORATORY
from .claude_code import VIEWS, views
from .needed import needed, survives
from .predictions import verdicts
from .predictions2 import MODELS
from .predictions2 import verdicts as verdicts2

SHOWN = ("cc-raw", "cc-rtk", "cc-caveman-engine", "cc-headroom-proxy")


def case_entry(case, runs: dict, exploratory: bool) -> dict:
    case_dir = CORPUS / case.id
    raw = (case_dir / "raw.txt").read_text(encoding="utf-8")
    facts = needed(case.kind, raw)
    seen = views(case_dir, runs)
    return {
        "id": case.id,
        "kind": case.kind,
        "what": case.what,
        "command": " ".join(case.raw),
        "exploratory": exploratory,
        "raw_chars": len(raw),
        "raw_tokens": tokens(raw),
        "facts": [{"item": f.item, "field": f.field, "text": f.text, "line": f.line} for f in facts],
        "views": {
            view: {
                "text": seen[view],
                "tokens": tokens(seen[view]),
                "kept": [survives(f, seen[view]) for f in facts],
            }
            for view in SHOWN
        },
    }


def beliefs(text: dict) -> dict:
    """Part 2: what the two models answered after reading each view, and the answers the page quotes."""
    results = beliefs_summary()
    named = [c.id for c in CASES if results["cases"][c.id]["truth"]["names"]]
    keys = ("answers", "said_failed", "count_right", "counted_runs", "names_found", "names", "first_right")

    def brief(answer: dict) -> dict:
        return {
            "run_failed": answer["run_failed"],
            "failing_count": answer.get("failing_count"),
            "listed": len(answer.get("failing") or []),
            "first_look": answer.get("first_look"),
        }

    runs = json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))
    absent = []  # a failing test the model named that is not in the text it read
    for case in CASES:
        names, texts = truth(case)["names"], read_views(case, runs)
        for m in MODELS:
            for v in READ_VIEWS:
                for trial, answer in enumerate(load(m, case.id, v)):
                    listed = [
                        str(f.get("name") or "") for f in answer.get("failing") or [] if isinstance(f, dict)
                    ]
                    absent += [
                        {"case": case.id, "model": m, "view": v, "trial": trial, "name": name}
                        for name in names
                        if any(name in got for got in listed) and name not in texts[v]
                    ]

    def replies(case_id: str, view: str) -> dict:
        return {
            m: [
                json.loads(answer_path(m, case_id, view, t).read_text(encoding="utf-8"))["reply"]
                for t in range(TRIALS)
            ]
            for m in MODELS
        }

    return {
        "models": {"luna": "GPT-6 Luna", "gemini": "Gemini 3.8 Flash"},
        "trials": TRIALS,
        "views": list(READ_VIEWS),
        "totals": {k: {f: t[f] for f in keys} for k, t in results["totals"].items()},
        "names": sum(len(results["cases"][c]["truth"]["names"]) for c in named),
        "names_in_text": {
            v: sum(text["cases"][c]["configs"][v]["by_field"]["name"][0] for c in named)
            for v in READ_VIEWS[1:]
        },
        "counts": {c.id: results["cases"][c.id]["truth"]["count"] for c in CASES + EXPLORATORY},
        "moved": moved(),
        "first_files": {
            c.id: {f"{m}/{v}": first_file(m, c.id, v) for m in MODELS for v in READ_VIEWS}
            for c in CASES + EXPLORATORY
        },
        "answers": {
            c.id: {f"{m}/{v}": [brief(a) for a in load(m, c.id, v)] for m in MODELS for v in READ_VIEWS}
            for c in CASES + EXPLORATORY
        },
        "absent_names": absent,
        "replies": {"pytest-setup-errors/cc-rtk": replies("pytest-setup-errors", "cc-rtk")},
        "predictions": verdicts2(None, text),
    }


def main() -> None:
    runs = json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))
    results = summary()
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    keys = (
        "facts_kept",
        "facts",
        "items_whole",
        "items",
        "cases_all_kept",
        "tokens",
        "reference_tokens",
        "raw_tokens",
    )
    document = {
        "commit": commit,
        "cases": [case_entry(c, runs, False) for c in CASES]
        + [case_entry(c, runs, True) for c in EXPLORATORY],
        "totals": {config: {k: t[k] for k in keys} for config, t in results["totals"].items()},
        "views": list(VIEWS),
        "caveman_hook_wraps": [c.id for c in CASES if runs[c.id]["caveman-hook"]["wraps"]],
        "predictions": verdicts(results, runs),
        "beliefs": beliefs(results),
    }
    json.dump(document, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
