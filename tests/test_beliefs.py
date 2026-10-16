"""Part 2's ground truth and scorer, checked before any model read a case."""

from kept_or_cut.beliefs import parse
from kept_or_cut.beliefs_score import score, summary_count, truth
from kept_or_cut.cases import CASES, EXPLORATORY

BY_ID = {c.id: c for c in CASES + EXPLORATORY}


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
