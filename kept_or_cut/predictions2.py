"""The seven predictions in PREDICTIONS-2.md, scored in code.

uv run python -m kept_or_cut.predictions2
"""

from __future__ import annotations

from .analyze import summary as part1
from .beliefs_score import TRIALS, summary
from .cases import CASES

MODELS = ("luna", "gemini")


def verdicts(results: dict | None = None, text: dict | None = None) -> list[dict]:
    results = results or summary()
    text = text or part1()
    cases = results["cases"]
    out = []

    def add(claim: str, evidence: str, held: bool) -> None:
        out.append(
            {"n": len(out) + 1, "claim": claim, "verdict": "held" if held else "wrong", "evidence": evidence}
        )

    def scores(case: str, model: str, view: str) -> list[dict]:
        return cases[case]["scores"][f"{model}/{view}"]

    views = ("full", "cc-raw", "cc-rtk", "cc-caveman-engine", "cc-headroom-proxy")
    said = [s["failed"] for c in CASES for m in MODELS for v in views for s in scores(c.id, m, v)]
    add("Every view says failed", f"{sum(said)} of {len(said)} answers say the run failed", all(said))

    passed = {m: sum(not s["failed"] for s in scores("pytest-setup-errors", m, "cc-rtk")) for m in MODELS}
    add(
        "A pass read as a pass",
        "answers saying the run with 18 errors did not fail, through rtk: "
        + ", ".join(f"{m} {n} of {TRIALS}" for m, n in passed.items()),
        any(n >= 2 for n in passed.values()),
    )

    counts = {m: [s.get("count_given") for s in scores("pytest-many", m, "cc-rtk")] for m in MODELS}
    add(
        "A short count is believed",
        "counts given for the 44-failure run through rtk: "
        + "; ".join(f"{m} {c}" for m, c in counts.items()),
        all(sum(c == 41 for c in given) >= 2 for given in counts.values()),
    )

    named = [c.id for c in CASES if cases[c.id]["truth"]["names"]]
    left = sum(text["cases"][c]["configs"]["cc-raw"]["by_field"]["name"][0] for c in named)
    total = sum(len(cases[c]["truth"]["names"]) for c in named)
    shares = {
        m: sum(s["names"] for c in named for s in scores(c, m, "cc-raw")) / (total * TRIALS) for m in MODELS
    }
    add(
        "No names out of thin air",
        f"names left in the text {left}/{total} = {left / total:.3f}; listed: "
        + ", ".join(f"{m} {v:.3f}" for m, v in shares.items()),
        all(v <= left / total + 0.02 for v in shares.values()),
    )

    reworded = {m: [s["names"] for s in scores("vitest-many", m, "cc-headroom-proxy")] for m in MODELS}
    add(
        "Reworded names stay reworded",
        "exact names listed for the vitest run through headroom: "
        + "; ".join(f"{m} {r}" for m, r in reworded.items()),
        all(n == 0 for r in reworded.values() for n in r),
    )

    def first(model: str, view: str) -> int:
        return results["totals"][f"{model}/{view}"]["first_right"]

    full = {m: first(m, "full") for m in MODELS}
    raw = {m: first(m, "cc-raw") for m in MODELS}
    add(
        "The first file survives the cut",
        "first look on a planted file, full output and Claude Code alone: "
        + ", ".join(f"{m} {full[m]} and {raw[m]}" for m in MODELS),
        all(full[m] >= 9 and raw[m] >= full[m] - 1 for m in MODELS),
    )

    rtk = {m: first(m, "cc-rtk") for m in MODELS}
    add(
        "rtk keeps the first file",
        "first look through rtk and through Claude Code alone: "
        + ", ".join(f"{m} {rtk[m]} and {raw[m]}" for m in MODELS),
        all(abs(rtk[m] - raw[m]) <= 1 for m in MODELS),
    )
    return out


if __name__ == "__main__":
    for v in verdicts():
        print(f"{v['n']}. {v['verdict']:<5} {v['claim']}: {v['evidence']}")
