"""Everything the fikrialfaraby.com/compress/ page shows, as one JSON document.

    uv run python -m kept_or_cut.export > compress.json

For every case: what it is, its needed facts, and, for each Claude Code view, the text the model reads and which
facts survive in it. The totals are analyze.py's, so the page and RESULTS.md quote the same numbers.
"""

from __future__ import annotations

import json
import subprocess
import sys

from .analyze import CORPUS, ROOT, summary, tokens
from .cases import CASES, EXPLORATORY
from .claude_code import VIEWS, views
from .needed import needed, survives
from .predictions import verdicts

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
    }
    json.dump(document, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
