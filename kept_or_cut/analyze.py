"""What survived: every needed fact, for every case and configuration, and what each output cost.

    uv run python -m kept_or_cut.analyze      # prints the summary as JSON

Every number in RESULTS.md comes from here, and tests/test_results.py holds the file to them.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import tiktoken

from .cases import CASES, EXPLORATORY
from .claude_code import VIEWS, views
from .needed import ANSI, needed, survives

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "corpus"
CONFIGS = ("rtk", "caveman-hook", "caveman-engine", "headroom-default", "headroom-aggressive")
# added after the results; reported apart from the pre-registered five. The two proxy runs are headroom as a coding
# agent meets it (scripts/headroom_proxy.py); the pre-registered headroom runs called compress() in a minimal install.
EXPLORATORY_CONFIGS = ("headroom-unprotected", "headroom-proxy", "headroom-proxy-token")
ENCODING = tiktoken.get_encoding("o200k_base")
# a run that failed must still read as failed
FAILED = re.compile(
    r"\b(fail(ed|ure|s)?|errors?|panic|traceback|exception)\b|\w+(Error|Exception)\b", re.IGNORECASE
)
# a pointer the agent could follow to get the dropped text back ("Retrieve more: hash=..." is headroom's proxy)
RECOVERY = re.compile(
    r"rtk recall [0-9a-f]+|caveman retrieve ccr_[0-9a-f]+|ccr[_:][\w/-]+|headroom_retrieve|retrieve\("
    r"|retrieve more: hash=[0-9a-f]+",
    re.IGNORECASE,
)


def tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def measure(facts: list, items: list[str], text: str, reference: str) -> dict:
    kept = [survives(f, text) for f in facts]
    lost = [f for f, k in zip(facts, kept, strict=True) if not k]
    whole = [i for i in items if all(k for f, k in zip(facts, kept, strict=True) if f.item == i)]
    by_field = {
        field: (
            sum(k for f, k in zip(facts, kept, strict=True) if f.field == field),
            sum(f.field == field for f in facts),
        )
        for field in ("name", "message", "location")
    }
    return {
        "unchanged": text == reference,
        "kept": sum(kept),
        "lost": [{"item": f.item, "field": f.field, "text": f.text, "line": f.line} for f in lost],
        "items_whole": len(whole),
        "first_item_whole": items[0] in whole,
        "by_field": by_field,
        "says_failed": bool(FAILED.search(ANSI.sub("", text))),
        "recovery_hint": bool(RECOVERY.search(text)),
        "tokens": tokens(text),
        "reference_tokens": tokens(reference),
        "chars": len(text),
    }


def case_result(case, runs: dict) -> dict:
    case_dir = CORPUS / case.id
    raw = (case_dir / "raw.txt").read_text(encoding="utf-8")
    facts = needed(case.kind, raw)
    items = list(dict.fromkeys(f.item for f in facts))
    out = {
        "kind": case.kind,
        "items": len(items),
        "facts": len(facts),
        "raw_tokens": tokens(raw),
        "raw_chars": len(raw),
        "configs": {},
    }
    for config in CONFIGS + EXPLORATORY_CONFIGS:
        text = (case_dir / f"{config}.txt").read_text(encoding="utf-8")
        out["configs"][config] = measure(facts, items, text, raw)
    # in Claude Code: each view is measured against what Claude Code shows for the command alone
    seen = views(case_dir, runs)
    for view in VIEWS:
        out["configs"][view] = measure(facts, items, seen[view], seen["cc-raw"])
    return out


def total(cases: dict, config: str) -> dict:
    rows = [c["configs"][config] for c in cases.values()]
    return {
        "facts_kept": sum(r["kept"] for r in rows),
        "facts": sum(c["facts"] for c in cases.values()),
        "cases_all_kept": sum(not r["lost"] for r in rows),
        "items_whole": sum(r["items_whole"] for r in rows),
        "items": sum(c["items"] for c in cases.values()),
        "cases_unchanged": sum(r["unchanged"] for r in rows),
        "tokens": sum(r["tokens"] for r in rows),
        "raw_tokens": sum(c["raw_tokens"] for c in cases.values()),
        "reference_tokens": sum(r["reference_tokens"] for r in rows),
        "lost_by_field": dict(Counter(lost["field"] for r in rows for lost in r["lost"])),
        "cases_losing_with_hint": sum(bool(r["lost"]) and r["recovery_hint"] for r in rows),
    }


def summary() -> dict:
    runs = json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))
    cases = {case.id: case_result(case, runs) for case in CASES}
    totals = {config: total(cases, config) for config in CONFIGS + EXPLORATORY_CONFIGS + VIEWS}
    exploratory = {case.id: case_result(case, runs) for case in EXPLORATORY}
    return {"cases": cases, "totals": totals, "exploratory_cases": exploratory}


if __name__ == "__main__":
    print(json.dumps(summary(), indent=1))
