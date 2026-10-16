"""The ten predictions in PREDICTIONS.md, each scored in code against the pre-registered configurations.

    uv run python -m kept_or_cut.predictions

A prediction with two parts is "half" when exactly one part held.
"""

from __future__ import annotations

import json

from .analyze import CORPUS, summary

COLLECT = ("pytest-collect", "pytest-import")
PAST_TEN = ("pytest-many", "pytest-renamed")
LINT = ("eslint-few", "eslint-many")
FEW = ("pytest-two", "pytest-few")
TRACEBACKS = ("traceback-deep", "traceback-chained")
GO = ("gotest-one", "gotest-panic")
LARGE = ("pytest-many", "pytest-renamed", "vitest-many", "tsc-many")  # as named in the prediction
SMALL_CHARS = 8000


def _verdict(*parts: bool) -> str:
    return "held" if all(parts) else "wrong" if not any(parts) else "half"


def verdicts(results: dict | None = None, runs: dict | None = None) -> list[dict]:
    results = results or summary()
    runs = runs or json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))
    cases = results["cases"]

    def cfg(case: str, config: str) -> dict:
        return cases[case]["configs"][config]

    def lost(case: str, config: str, field: str) -> int:
        return sum(item["field"] == field for item in cfg(case, config)["lost"])

    out = []

    def add(claim: str, evidence: str, *parts: bool) -> None:
        out.append({"n": len(out) + 1, "claim": claim, "verdict": _verdict(*parts), "evidence": evidence})

    hidden = [k for k in COLLECT if not cfg(k, "rtk")["says_failed"]]
    message_lost = [k for k in COLLECT if lost(k, "rtk", "message")]
    add(
        "rtk hides collection errors",
        f"rtk's output says the run failed in {len(COLLECT) - len(hidden)} of 2 collection errors; "
        f"the error message is lost in {len(message_lost)} of 2",
        len(hidden) == len(COLLECT) and len(message_lost) == len(COLLECT),
    )
    names = {k: lost(k, "rtk", "name") for k in PAST_TEN}
    add(
        "rtk drops failing tests past ten",
        f"failing-test names lost: {names['pytest-many']} of 44 and {names['pytest-renamed']} of 32",
        all(names.values()),
    )
    lines = {k: cfg(k, "rtk")["by_field"]["location"] for k in LINT}
    add(
        "rtk drops every lint line number",
        "lint locations kept: " + ", ".join(f"{kept} of {total}" for kept, total in lines.values()),
        all(kept == 0 for kept, _ in lines.values()),
    )
    few_names = {k: lost(k, "rtk", "name") for k in FEW}
    few_places = {k: lost(k, "rtk", "location") for k in FEW}
    add(
        "rtk keeps the names but loses places",
        f"names lost: {few_names['pytest-two']} and {few_names['pytest-few']}; "
        f"locations lost: {few_places['pytest-two']} and {few_places['pytest-few']}",
        all(n == 0 for n in few_names.values()),
        all(few_places.values()),
    )
    add(
        "rtk leaves tracebacks alone",
        "unchanged: " + ", ".join(k for k in TRACEBACKS if cfg(k, "rtk")["unchanged"]),
        all(cfg(k, "rtk")["unchanged"] for k in TRACEBACKS),
    )
    wrapped = sorted(k for k in cases if runs[k]["caveman-hook"]["wraps"])
    add("caveman's hook wraps only Go", "wraps: " + ", ".join(wrapped), set(wrapped) == set(GO))
    whole = sum(not cfg(k, "caveman-engine")["lost"] for k in cases)
    add("caveman's engine keeps nearly everything", f"{whole} of 16 cases keep every fact", whole >= 12)
    go_messages = cfg("gotest-one", "caveman-engine")["by_field"]["message"]
    add(
        "caveman merges numbers",
        f"messages kept in the four-row Go run: {go_messages[0]} of {go_messages[1]}",
        go_messages[0] < go_messages[1],
    )
    same = sum(cfg(k, "headroom-default")["unchanged"] for k in cases)
    add("headroom's default changes nothing", f"{same} of 16 outputs unchanged", same == len(cases))
    small = [k for k in cases if cases[k]["raw_chars"] < SMALL_CHARS]
    small_whole = sum(not cfg(k, "headroom-aggressive")["lost"] for k in small)
    large_losing = [k for k in LARGE if cfg(k, "headroom-aggressive")["lost"]]
    add(
        "headroom aggressive is safe on small outputs, not on large ones",
        f"{small_whole} of {len(small)} small outputs keep every fact; "
        f"{len(large_losing)} of the 4 large ones lose any",
        small_whole == len(small),
        bool(large_losing),
    )
    return out


if __name__ == "__main__":
    for v in verdicts():
        print(f"{v['n']:>2}. {v['verdict']:<5} {v['claim']}: {v['evidence']}")
