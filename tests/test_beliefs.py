"""Part 2: the ground truth and scorer (checked before any model read a case), then what the models answered."""

import json
import re

from kept_or_cut.analyze import CORPUS
from kept_or_cut.analyze import summary as part1
from kept_or_cut.beliefs import parse
from kept_or_cut.beliefs_score import (
    BELIEFS,
    VIEWS,
    first_file,
    load,
    moved,
    score,
    summary,
    summary_count,
    truth,
    views,
)
from kept_or_cut.cases import CASES, EXPLORATORY
from kept_or_cut.predictions2 import verdicts

BY_ID = {c.id: c for c in CASES + EXPLORATORY}
RUNS = json.loads((CORPUS / "runs.json").read_text(encoding="utf-8"))


def test_each_runs_own_summary_count():
    counts = {c.id: truth(c)["count"] for c in CASES + EXPLORATORY}
    assert counts["pytest-many"] == 44 and counts["pytest-renamed"] == 32 and counts["pytest-few"] == 6
    assert counts["pytest-setup-errors"] == 18 and counts["pytest-collect"] == 1
    assert counts["vitest-many"] == 7 and counts["tsc-many"] == 43 and counts["eslint-many"] == 12
    assert counts["gotest-one"] is None and counts["traceback-deep"] is None
    assert summary_count("pytest", "== 14 failed, 241 passed, 1 warning, 18 errors in 17.64s ==") == 32


def test_the_planted_files():
    assert truth(BY_ID["pytest-two"])["planted"] == ["operators.py"]
    assert truth(BY_ID["eslint-many"])["planted"] == ["classify.ts", "guardrail.ts", "merge.ts", "writer.ts"]


def test_scoring_an_answer():
    t = {"exit_code": 1, "planted": ["tools.py"], "count": 6, "names": ["test_a", "test_b[x]"]}
    answer = {
        "run_failed": True,
        "failing_count": 6,
        "failing": [
            {"name": "tests/test_t.py::test_a", "file": "tests/test_t.py", "line": 4},
            {"name": "test_b", "file": None, "line": None},
        ],
        "first_look": {"file": "src/toko_wa/tools.py", "line": 10},
    }
    got = score(t, answer)
    assert got["failed"] and got["count"] and got["first"]
    assert got["names"] == 1  # "test_b" is not "test_b[x]"
    assert score(t, None) == {"parsed": False, "failed": False, "count": False, "names": 0, "first": False}


def test_parsing_a_reply():
    assert parse('Here it is:\n```json\n{"run_failed": false, "first_look": {"file": "a.py"}}\n```') == {
        "run_failed": False,
        "first_look": {"file": "a.py"},
    }
    assert parse("no json here") is None


def test_a_reply_cut_off_mid_answer_holds_no_answer():
    cut = '{"run_failed": true, "failing_count": 7, "failing": [{"name": "a", "file": "t.ts", "line": 14}, {"name": "b'
    assert parse(cut) is None
    braces = '{"run_failed": true, "failing": [{"name": "x {y}", "file": "a.py", "line": 1}]}'
    assert parse(braces)["failing"][0]["name"] == "x {y}"


# What the models answered (corpus/beliefs/, 510 answers), pinned to RESULTS-2.md.

MODELS = ("luna", "gemini")


def answers(model, case_id, view, field):
    return [(a or {}).get(field) for a in load(model, case_id, view)]


def test_every_stored_reply_holds_an_answer():
    paths = sorted(BELIEFS.glob("*/*/*.json"))
    assert len(paths) == 510
    records = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    assert all(parse(r["reply"]) is not None for r in records)
    asked_again = [r for r in records if r.get("earlier")]
    assert [(r["model"], r["case"], r["view"], r["trial"]) for r in asked_again] == [
        ("ag/gemini-3.8-flash", "vitest-many", "cc-raw", 1)
    ]
    assert (
        len(asked_again[0]["earlier"][0]["reply"]) == 1168
        and parse(asked_again[0]["earlier"][0]["reply"]) is None
    )


def test_the_totals():
    totals = summary()["totals"]
    got = {
        k: (t["said_failed"], t["count_right"], t["names_found"], t["first_right"]) for k, t in totals.items()
    }
    assert got == {
        "luna/full": (48, 12, 282, 11),
        "luna/cc-raw": (48, 9, 90, 9),
        "luna/cc-rtk": (48, 11, 108, 6),
        "luna/cc-caveman-engine": (48, 9, 187, 8),
        "luna/cc-headroom-proxy": (48, 10, 69, 8),
        "gemini/full": (48, 12, 282, 10),
        "gemini/cc-raw": (48, 11, 96, 9),
        "gemini/cc-rtk": (48, 11, 108, 8),
        "gemini/cc-caveman-engine": (48, 10, 190, 11),
        "gemini/cc-headroom-proxy": (48, 11, 69, 10),
    }
    assert {t["answers"] for t in totals.values()} == {48} and {t["parsed"] for t in totals.values()} == {48}
    assert {(t["counted_runs"], t["names"]) for t in totals.values()} == {(12, 288)}


def test_the_seven_verdicts():
    assert [v["verdict"] for v in verdicts()] == ["held", "wrong", "wrong", "held", "held", "wrong", "wrong"]


def test_rtk_on_the_run_with_18_errors_leaves_nothing_to_act_on():
    text = views(BY_ID["pytest-setup-errors"], RUNS)["cc-rtk"]
    assert "Pytest: 255 passed" in text and "error" not in text.lower()
    for model in MODELS:
        assert answers(model, "pytest-setup-errors", "cc-rtk", "run_failed") == [True, True, True]
        assert answers(model, "pytest-setup-errors", "cc-rtk", "failing_count") == [None, None, None]
        assert answers(model, "pytest-setup-errors", "cc-rtk", "failing") == [[], [], []]
        assert first_file(model, "pytest-setup-errors", "cc-rtk") == ""


def test_rtk_on_the_renamed_run_gives_a_short_count_and_the_wrong_file():
    assert "Pytest: 241 passed, 14 failed" in views(BY_ID["pytest-renamed"], RUNS)["cc-rtk"]
    for model in MODELS:
        assert answers(model, "pytest-renamed", "cc-rtk", "failing_count") == [14, 14, 14]
        assert first_file(model, "pytest-renamed", "cc-rtk") != "tools.py"
        for view in ("full", "cc-raw", "cc-caveman-engine", "cc-headroom-proxy"):
            assert first_file(model, "pytest-renamed", view) == "tools.py"


def test_when_the_cut_hides_the_total():
    progress = re.compile(r"^(?:\S+\.py )?([.FEsx]+)\s*\[\s*\d+%\]$", re.MULTILINE)
    many = views(BY_ID["pytest-many"], RUNS)["cc-raw"]
    assert not re.search(r"(?<!\d)(44|83)(?!\d)", many)
    assert sum(m.group(1).count("F") for m in progress.finditer(many)) == 44
    renamed = views(BY_ID["pytest-renamed"], RUNS)["cc-raw"]
    marks = "".join(m.group(1) for m in progress.finditer(renamed))
    assert (marks.count("F"), marks.count("E")) == (14, 18)
    assert answers("gemini", "pytest-many", "cc-raw", "failing_count") == [44, 44, 44]
    assert answers("gemini", "pytest-renamed", "cc-raw", "failing_count") == [32, 32, 32]
    assert answers("luna", "pytest-many", "cc-raw", "failing_count") == [None, 83, None]
    assert answers("luna", "pytest-renamed", "cc-raw", "failing_count") == [None, None, 33]
    for model in MODELS:
        assert answers(model, "tsc-many", "cc-raw", "failing_count") == [None, None, None]


def test_no_name_through_claude_code_alone_is_missing_from_its_text():
    rebuilt = []
    for case in CASES:
        names, texts = truth(case)["names"], views(case, RUNS)
        for model in MODELS:
            for view in VIEWS:
                for trial, failing in enumerate(answers(model, case.id, view, "failing")):
                    listed = [str(f.get("name") or "") for f in failing or [] if isinstance(f, dict)]
                    for name in names:
                        if any(name in got for got in listed) and name not in texts[view]:
                            rebuilt.append((case.id, model, view, trial, name))
    # Both from caveman's engine, which elided the test's header; "ot-04" and the function name stayed in the text.
    assert rebuilt == [
        ("pytest-renamed", "luna", "cc-caveman-engine", 2, "test_reference_actions_run_without_error[ot-04]"),
        (
            "pytest-renamed",
            "gemini",
            "cc-caveman-engine",
            1,
            "test_reference_actions_run_without_error[ot-04]",
        ),
    ]


def test_where_the_first_look_moved():
    got = moved()
    assert {k: len(v) for k, v in got.items()} == {
        "luna/cc-raw": 3,
        "luna/cc-rtk": 7,
        "luna/cc-caveman-engine": 4,
        "luna/cc-headroom-proxy": 4,
        "gemini/cc-raw": 2,
        "gemini/cc-rtk": 4,
        "gemini/cc-caveman-engine": 2,
        "gemini/cc-headroom-proxy": 1,
    }
    assert all("pytest-many" in runs for runs in got.values())
    for model in MODELS:
        assert first_file(model, "pytest-many", "full") != "test_mutants.py"
        assert all(first_file(model, "pytest-many", v) == "test_mutants.py" for v in VIEWS[1:])


def test_where_the_traceback_to_the_bug_goes():
    texts = views(BY_ID["pytest-renamed"], RUNS)
    named = {v: len(re.findall(r"(?<![\w/])(?:[\w./-]*/)?tools\.py", texts[v])) for v in VIEWS}
    assert (named["full"], named["cc-raw"], named["cc-rtk"]) == (18, 5, 0)
    caveman = texts["cc-caveman-engine"]
    assert "test_reference_actions_run_without_error[ot-04]" not in caveman
    assert "id='ot-04'" in caveman and "test_reference_actions_run_without_error" in caveman


def test_runs_where_no_view_leads_to_the_planted_file():
    results = summary()
    never = [
        c.id
        for c in CASES
        if not any(
            sum(s["first"] for s in results["cases"][c.id]["scores"][f"{m}/{v}"]) >= 2
            for m in MODELS
            for v in VIEWS
        )
    ]
    assert never == ["pytest-two", "pytest-many", "pytest-import", "gotest-panic", "vitest-one"]
    assert [first_file("luna", "pytest-many", "full")] == [""]
    assert first_file("gemini", "pytest-many", "full") == "test_trace.py"
    assert not any("test_trace" in line for line in views(BY_ID["pytest-many"], RUNS)["cc-rtk"].splitlines())


LABELS = {
    "full": "Full output, no cut",
    "cc-raw": "Claude Code alone",
    "cc-rtk": "rtk, then Claude Code",
    "cc-caveman-engine": "caveman's engine, then Claude Code",
    "cc-headroom-proxy": "Claude Code, then headroom's proxy",
}


def test_results_2_shows_these_numbers():
    page = (CORPUS.parent / "RESULTS-2.md").read_text(encoding="utf-8")
    totals, got = summary()["totals"], moved()

    def pct(found, of):
        return f"{round(100 * found / of)}%"

    for view, label in LABELS.items():
        luna, gemini = totals[f"luna/{view}"], totals[f"gemini/{view}"]
        row = (
            f"| {label} | {luna['count_right']} · {gemini['count_right']} "
            f"| {pct(luna['names_found'], 288)} · {pct(gemini['names_found'], 288)} "
            f"| {luna['first_right']} · {gemini['first_right']} |"
        )
        assert row in page, row
        if view != "full":
            assert f"| {label} | {len(got['luna/' + view])} | {len(got['gemini/' + view])} |" in page
    text = part1()
    named = [c.id for c in CASES if truth(c)["names"]]
    for view in VIEWS[1:]:
        left = sum(text["cases"][c]["configs"][view]["by_field"]["name"][0] for c in named)
        luna, gemini = totals[f"luna/{view}"]["names_found"], totals[f"gemini/{view}"]["names_found"]
        assert f"| {LABELS[view]} | {pct(left, 96)} | {pct(luna, 288)} | {pct(gemini, 288)} |" in page
    assert "## Predictions: 3 held, 4 wrong" in page


def test_the_readme_quotes_these_numbers():
    readme = " ".join((CORPUS.parent / "README.md").read_text(encoding="utf-8").split())
    totals = summary()["totals"]
    raw = [round(100 * totals[f"{m}/cc-raw"]["names_found"] / 288) for m in MODELS]
    caveman = [round(100 * totals[f"{m}/cc-caveman-engine"]["names_found"] / 288) for m in MODELS]
    assert f"{raw[0]}% and {raw[1]}% through Claude Code alone, where 35% of the names are left" in readme
    assert f"{caveman[0]}% and {caveman[1]}% through caveman's engine, where 68% are" in readme
    assert "all 480 answers on the 16 runs" in readme and "My predictions: 3 held, 4 wrong." in readme


def test_the_site_export_quotes_part_2():
    from kept_or_cut.export import beliefs

    block = beliefs(part1())
    assert block["totals"] == {
        k: {f: t[f] for f in block["totals"][k]} for k, t in summary()["totals"].items()
    }
    assert block["names"] == 96 and block["names_in_text"]["cc-raw"] == 34
    assert [p["verdict"] for p in block["predictions"]] == [v["verdict"] for v in verdicts()]
    assert {a["failing_count"] for a in block["answers"]["pytest-renamed"]["gemini/cc-rtk"]} == {14}
    assert [(a["model"], a["view"]) for a in block["absent_names"]] == [
        ("luna", "cc-caveman-engine"),
        ("gemini", "cc-caveman-engine"),
    ]
    quoted = block["replies"]["pytest-setup-errors/cc-rtk"]
    assert {" ".join(r.split()) for rs in quoted.values() for r in rs} == {
        '{"run_failed": true, "failing_count": null, "failing": [], "first_look": {"file": null, "line": null}}'
    }
