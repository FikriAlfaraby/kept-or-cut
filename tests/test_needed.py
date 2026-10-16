"""The needed facts, read from each raw output by the fixed rules, before any compressor ran."""

from pathlib import Path

import pytest

from kept_or_cut.cases import CASES
from kept_or_cut.needed import Fact, needed, survives

CORPUS = Path(__file__).resolve().parents[1] / "corpus"
# failing items and facts per case, as the rules read them
EXPECTED = {
    "pytest-two": (2, 6),
    "pytest-many": (44, 132),
    "pytest-collect": (1, 3),
    "pytest-import": (1, 3),
    "pytest-few": (6, 18),
    "pytest-renamed": (32, 96),
    "traceback-deep": (1, 2),
    "traceback-chained": (2, 4),
    "gotest-one": (5, 9),
    "gotest-panic": (2, 3),
    "vitest-one": (1, 3),
    "vitest-many": (7, 21),
    "tsc-one": (1, 2),
    "tsc-many": (39, 86),
    "eslint-few": (3, 6),
    "eslint-many": (12, 24),
}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_every_needed_fact_is_in_the_raw_output(case):
    raw = (CORPUS / case.id / "raw.txt").read_text(encoding="utf-8")
    facts = needed(case.kind, raw)
    assert (len({f.item for f in facts}), len(facts)) == EXPECTED[case.id]
    assert all(survives(f, raw) for f in facts)


def test_the_total():
    assert sum(n for _, n in EXPECTED.values()) == 418


def test_a_location_needs_its_line_number_written_as_one():
    fact = Fact("t", "location", "test_probe.py", 12)
    assert survives(fact, "tests/test_probe.py:12: AssertionError")
    assert survives(fact, 'File "/x/test_probe.py", line 12, in t')
    assert survives(fact, "test_probe.py (2 errors)\n  L12: assert")
    assert not survives(fact, "tests/test_probe.py F.F.. [ 12%]")
    assert not survives(fact, "tests/test_probe.py: AssertionError")


def test_a_message_must_keep_its_first_sixty_characters():
    fact = Fact("t", "message", "AssertionError: assert '013' == '012'")
    assert survives(fact, "E   AssertionError:   assert '013' == '012'")
    assert not survives(fact, "E   AssertionError: assert '01")
