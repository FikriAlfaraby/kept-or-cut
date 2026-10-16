"""RESULTS.md and README.md, recomputed from the corpus: a change to the corpus or the rules that moves a number fails
here."""

import json
from pathlib import Path

import pytest

from kept_or_cut.analyze import CORPUS, summary
from kept_or_cut.cases import CASES
from kept_or_cut.claude_code import cut, read_back, views
from kept_or_cut.needed import needed
from kept_or_cut.predictions import verdicts

ROOT = Path(__file__).resolve().parents[1]
RESULTS = (ROOT / "RESULTS.md").read_text(encoding="utf-8")
FLAT = " ".join(RESULTS.split())
README = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
RUNS = json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))
# configuration: facts kept, failing items fully visible, outputs with every fact, tokens, its row in RESULTS.md
FULL_OUTPUT = {
    "rtk": (282, 85, 10, 11118, "rtk 1.0.1, through its hook"),
    "caveman-hook": (418, 159, 16, 60387, "caveman 4.0.1, through its hook"),
    "caveman-engine": (404, 145, 13, 35464, "caveman's engine on every output"),
    "headroom-proxy": (407, 152, 15, 55592, "headroom 0.41.0's proxy, given the full output (added later)"),
    "headroom-default": (418, 159, 16, 60387, "headroom `compress()`, as pre-registered"),
    "headroom-aggressive": (418, 159, 16, 60387, None),
}
IN_CLAUDE_CODE = {
    "cc-raw": (294, 83, 12, 18956, "Claude Code alone"),
    "cc-rtk": (270, 75, 9, 10030, "rtk, then Claude Code"),
    "cc-caveman-hook": (294, 83, 12, 19026, "caveman's hook, then Claude Code"),
    "cc-caveman-engine": (347, 102, 10, 19917, "caveman's engine, then Claude Code"),
    "cc-headroom-proxy": (257, 69, 11, 15884, "Claude Code, then headroom's proxy"),
}
# failing items fully visible in the five runs Claude Code cuts
LONG_RUNS = {
    "pytest-many": ("pytest, 44 failures", 7, 10, 33, 7),
    "pytest-few": ("pytest, 6 failures", 3, 6, 4, 2),
    "pytest-renamed": ("pytest, 32 failures and errors", 6, 10, 11, 0),
    "vitest-many": ("vitest, 7 failures", 7, 5, 3, 0),
    "tsc-many": ("tsc, 43 errors", 29, 29, 29, 29),
}


@pytest.fixture(scope="module")
def results():
    return summary()


def text(case: str, config: str) -> str:
    return (CORPUS / case / f"{config}.txt").read_text(encoding="utf-8")


def lost(results, case: str, config: str) -> list[tuple[str, str, int | None]]:
    return [(x["field"], x["text"], x["line"]) for x in results["cases"][case]["configs"][config]["lost"]]


def row(name: str, facts: int, items: int, outputs: int, tokens: int, reference: int | None) -> str:
    cells = f"| {name} | {facts} | {items} | {outputs} | {tokens:,}"
    if reference is None:
        return cells + " |"
    change = round(100 * (tokens / reference - 1))
    return cells + (f" (−{-change}%) |" if change < 0 else f" (+{change}%) |" if change > 0 else " (0%) |")


def test_the_corpus(results):
    total = results["totals"]["rtk"]
    assert (len(results["cases"]), total["facts"], total["items"], total["raw_tokens"]) == (
        16,
        418,
        159,
        60387,
    )
    assert "16 planted bugs; 159 failing items; 418 needed facts" in FLAT
    assert "| The raw output | 418 | 159 | 16 | 60,387 |" in RESULTS


def test_the_418_facts_hold_237_different_ones():
    distinct = 0
    for case in CASES:
        facts = needed(case.kind, text(case.id, "raw"))
        distinct += len({(f.field, f.text, f.line) for f in facts})
        if case.id == "pytest-many":
            assert len({f.text for f in facts if f.field == "message"}) == 6
            assert len({(f.text, f.line) for f in facts if f.field == "location"}) == 2
    assert distinct == 237 and "The 418 facts hold only 237 different ones" in FLAT


@pytest.mark.parametrize("config", FULL_OUTPUT)
def test_each_tool_on_the_full_output(results, config):
    facts, items, outputs, tokens, name = FULL_OUTPUT[config]
    t = results["totals"][config]
    assert (t["facts_kept"], t["items_whole"], t["cases_all_kept"], t["tokens"]) == (
        facts,
        items,
        outputs,
        tokens,
    )
    if name:
        assert row(name, facts, items, outputs, tokens, t["raw_tokens"]) in RESULTS


@pytest.mark.parametrize("view", IN_CLAUDE_CODE)
def test_each_tool_in_claude_code(results, view):
    facts, items, outputs, tokens, name = IN_CLAUDE_CODE[view]
    t = results["totals"][view]
    assert (t["facts_kept"], t["items_whole"], t["cases_all_kept"], t["tokens"]) == (
        facts,
        items,
        outputs,
        tokens,
    )
    assert (
        row(name, facts, items, outputs, tokens, None if view == "cc-raw" else t["reference_tokens"])
        in RESULTS
    )


def test_the_five_long_runs(results):
    shown = ("cc-raw", "cc-rtk", "cc-caveman-engine", "cc-headroom-proxy")
    cut_cases = [c.id for c in CASES if "characters truncated] ..." in views(CORPUS / c.id, RUNS)["cc-raw"]]
    assert cut_cases == list(LONG_RUNS)
    for case, (label, *visible) in LONG_RUNS.items():
        assert [results["cases"][case]["configs"][v]["items_whole"] for v in shown] == visible
        assert f"| {label} | {' | '.join(str(n) for n in visible)} |" in RESULTS


def test_claude_codes_cut():
    # the shape of the one cut in my own transcripts: 29,877 characters became 10,040, the marker at 5,002
    shown = cut("x" * 29877)
    assert len(shown) == 10040 and shown.index("... [19877 characters truncated] ...") == 5002
    assert cut("x" * 11024) == "x" * 11024 and len(cut("x" * 11025)) < 11025


def test_claude_code_reads_back_30000_bytes_first():
    assert read_back("x" * 30000) == "x" * 30000 and read_back("x" * 30001) == "x" * 30000
    # bytes, not characters: a two-byte character split at the limit becomes one replacement character
    assert read_back("x" * 29999 + "é" * 3) == "x" * 29999 + "\ufffd"
    # the two longest runs lose their end, summary line included
    for case, summary_line in (("pytest-many", "44 failed"), ("pytest-renamed", "14 failed")):
        assert summary_line in text(case, "raw") and summary_line not in views(CORPUS / case, RUNS)["cc-raw"]


def test_rtk_calls_a_run_with_18_errors_a_pass(results):
    case = results["exploratory_cases"]["pytest-setup-errors"]
    assert "255 passed, 1 warning, 18 errors" in text("pytest-setup-errors", "raw")
    assert text("pytest-setup-errors", "rtk").startswith("Pytest: 255 passed in 18.56s\n")
    assert not case["configs"]["rtk"]["says_failed"]
    assert (case["configs"]["rtk"]["kept"], case["facts"]) == (0, 54)


def test_rtk_drops_errors_from_its_count():
    assert "14 failed, 241 passed, 1 warning, 18 errors" in text("pytest-renamed", "raw")
    assert text("pytest-renamed", "rtk").startswith("Pytest: 241 passed, 14 failed in")
    assert "… +4 more failures" in text("pytest-renamed", "rtk")


def test_rtk_counts_31_more_when_34_remain(results):
    raw = text("pytest-many", "raw")
    rtk = text("pytest-many", "rtk")
    assert rtk.count("[FAIL]") == 10 and "… +31 more failures" in rtk
    assert results["cases"]["pytest-many"]["items"] == 44
    # pytest draws three of the 44 rules with two underscores; rtk splits on three
    assert sum(line.startswith("___") for line in raw.splitlines()) == 41
    assert results["cases"]["pytest-many"]["configs"]["rtk"]["by_field"]["message"] == (42, 44)


def test_rtk_turns_lint_into_counts(results):
    for case in ("eslint-few", "eslint-many"):
        assert results["cases"][case]["configs"]["rtk"]["kept"] == 0
        assert "Top rules:" in text(case, "rtk")


def test_rtk_cuts_the_panic_before_my_code(results):
    assert lost(results, "gotest-panic", "rtk") == [("location", "shipping.go", 12)]


def test_rtk_points_back_whenever_it_drops_something(results):
    losing = [c for c, r in results["cases"].items() if r["configs"]["rtk"]["lost"]]
    assert len(losing) == 6
    assert all(results["cases"][c]["configs"]["rtk"]["recovery_hint"] for c in losing)


def test_rtk_leaves_collection_errors_and_tracebacks_whole(results):
    for case in ("pytest-collect", "pytest-import", "traceback-deep", "traceback-chained"):
        assert not results["cases"][case]["configs"]["rtk"]["lost"]


def test_cavemans_hook_wraps_only_the_go_runs():
    assert sorted(c for c, r in RUNS.items() if r.get("caveman-hook", {}).get("wraps")) == [
        "gotest-one",
        "gotest-panic",
    ]


def test_cavemans_engine_loses_lint_files_vitest_pointers_and_one_frame(results):
    losing = {c: lost(results, c, "caveman-engine") for c in results["cases"]}
    losing = {c: v for c, v in losing.items() if v}
    assert {c: len(v) for c, v in losing.items()} == {"eslint-many": 9, "pytest-renamed": 1, "vitest-many": 4}
    assert {field for v in losing.values() for field, _, _ in v} == {"location"}
    assert "… 2 lines elided (caveman) …" in text("eslint-many", "caveman-engine")


def test_cavemans_engine_offers_the_original_back(results):
    for case, r in results["cases"].items():
        engine = r["configs"]["caveman-engine"]
        assert ("recover: caveman retrieve ccr_" in text(case, "caveman-engine")) == (
            not engine["unchanged"]
        ), case


def test_headroom_proxy_leaves_small_failures_alone(results):
    for case, r in results["cases"].items():
        unchanged = r["configs"]["headroom-proxy"]["unchanged"]
        assert unchanged == (r["raw_chars"] <= 8000), case
    assert sum(r["configs"]["headroom-proxy"]["unchanged"] for r in results["cases"].values()) == 11


def test_headroom_proxy_rewords_the_vitest_names(results):
    losing = [c for c, r in results["cases"].items() if r["configs"]["headroom-proxy"]["lost"]]
    assert losing == ["vitest-many"]
    fields = results["cases"]["vitest-many"]["configs"]["headroom-proxy"]["by_field"]
    assert fields == {"name": (0, 7), "message": (3, 7), "location": (7, 7)}
    reworded = text("vitest-many", "headroom-proxy")
    assert "parses '800jt' 800 million" in reworded and "parses '800jt' as 800 million" not in reworded


def test_headroom_behind_claude_code_rewrites_assertions(results):
    assert "assert 134570 == (((2 * 59000) + 15000) + 570)" in text("pytest-few", "raw")
    shown = text("pytest-few", "cc-headroom-proxy")
    assert "assert 134570 == (((2 * 59000) 15000) + 570)" in shown
    assert "AssertionError: 199000 198000" in shown and "assert 199000 == 198000" not in shown
    assert results["cases"]["vitest-many"]["configs"]["cc-headroom-proxy"]["by_field"]["name"] == (0, 7)
    for case in LONG_RUNS:
        forwarded = results["cases"][case]["configs"]["cc-raw"]["chars"]
        assert 8000 < forwarded < 11024 and "Retrieve more: hash=" in text(case, "cc-headroom-proxy"), case


def test_headroom_proxy_offers_the_original_back(results):
    for case, r in results["cases"].items():
        if not r["configs"]["headroom-proxy"]["unchanged"]:
            assert "Retrieve more: hash=" in text(case, "headroom-proxy"), case
        for name in ("headroom-proxy", "cc-headroom-proxy"):
            assert RUNS[case][name]["tools_added"] == ["headroom_retrieve"]
            assert RUNS[case][name]["is_error_kept"] and RUNS[case][name]["exit_code_line_kept"]


def test_headroom_proxy_ran_with_its_model_loaded():
    for name in ("headroom-proxy", "headroom-proxy-token", "cc-headroom-proxy", "cc-headroom-proxy-token"):
        assert RUNS["_proxy"][name]["kompress"]["kompress"]["status"] == "loaded"


def test_headroom_compress_as_registered_changed_nothing(results):
    for config in ("headroom-default", "headroom-aggressive"):
        assert all(r["configs"][config]["unchanged"] for r in results["cases"].values())


def test_headroom_proxy_repeats():
    full = json.loads((CORPUS / "headroom-proxy-repeats.json").read_text(encoding="utf-8"))
    assert full["runs"] == 6
    token, cache = full["summary"]["headroom-proxy-token"], full["summary"]["headroom-proxy"]
    assert all(r["different_outputs"] == 1 for r in token.values())
    varied = {c: r for c, r in cache.items() if r["different_outputs"] > 1}
    assert varied == {"pytest-renamed": {"different_outputs": 2, "kept": [96, 96], "tokens": [19341, 19353]}}
    assert all(r["kept"][0] == r["kept"][1] for mode in (token, cache) for r in mode.values())
    behind = json.loads((CORPUS / "cc-headroom-proxy-repeats.json").read_text(encoding="utf-8"))
    assert behind["runs"] == 3
    assert all(r["different_outputs"] == 1 for mode in behind["summary"].values() for r in mode.values())
    assert "two versions of the 32-failure pytest output (19,341 and 19,353 tokens)" in FLAT
    assert "Behind Claude Code, three runs gave the same output every time, in both modes" in FLAT


EXPECTED_VERDICTS = ["wrong", "held", "held", "half", "held", "held", "held", "wrong", "held", "half"]


def test_the_predictions_as_scored():
    scored = verdicts()
    assert [v["verdict"] for v in scored] == EXPECTED_VERDICTS
    assert "6 held, 2 wrong, 2 half" in RESULTS
    for v in scored:
        assert f"| {v['n']} | {v['claim']} | {v['verdict']} |" in RESULTS


def test_the_readme_repeats_the_same_numbers():
    for line in (
        "| Claude Code alone | 83 | 18,956 |",
        "| rtk, then Claude Code | 75 | 10,030 (−47%) |",
        "| caveman's engine, then Claude Code | 102 | 19,917 (+5%) |",
        "| Claude Code, then headroom's proxy | 69 | 15,884 (−16%) |",
        "6 held, 2 wrong, 2 half",
        "Pytest: 255 passed in 18.56s",
    ):
        assert line in README


def test_the_site_export_quotes_the_same_numbers(results):
    from kept_or_cut.export import SHOWN, case_entry

    for case in CASES:
        entry = case_entry(case, RUNS, False)
        for view in SHOWN:
            assert sum(entry["views"][view]["kept"]) == results["cases"][case.id]["configs"][view]["kept"], (
                case.id
            )
