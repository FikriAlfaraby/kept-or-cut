# kept-or-cut

**Does the error line a coding agent needs survive token compression?**

Token-compression tools shrink what a coding agent reads from the shell. rtk (83k GitHub stars) "reduces LLM
token consumption by 60-90% on common dev commands". headroom (75k) promises "20% fewer tokens for coding agents"
and "same answers". caveman (113k) reports 18 of 18 answers right. Those are averages. An agent fixing a failing
run needs a few exact lines: the failing test's name, the error message, the file and line.

I planted 16 bugs in four of my repositories and two small fixtures, ran each failing command, and checked by
fixed rules which of those lines each tool keeps. The predictions were tagged before any tool ran on the cases
([PREDICTIONS.md](PREDICTIONS.md), tag `v0.1-prereg`).

## Results

In Claude Code, the agent never reads the middle of a long failing run. Claude Code itself keeps the first and
last 5,000 characters of a failed command's output, and each tool sits before or after that cut. 159 failing
items:

| What the model reads | Items fully visible | Tokens |
|---|---:|---:|
| Claude Code alone | 101 | 18,720 |
| rtk, then Claude Code | 75 | 10,030 (−46%) |
| caveman's hook, then Claude Code | 101 | 18,790 (0%) |
| caveman's engine, then Claude Code | 104 | 19,853 (+6%) |
| Claude Code, then headroom's proxy | 88 | 15,754 (−16%) |

- **rtk's summary can read as a pass.** In a case I added after the results, a pytest run with 18 errors and no
  failures came back as "Pytest: 255 passed in 18.56s", with only the exit code saying otherwise; rtk's summary has
  no place for errors (already reported upstream, a fix is open). Lint came back as counts with no line numbers,
  and with 44 failures it said "+31 more" when 34 remained. On the other hand, its short summary of a 6-failure
  run fits under Claude Code's cut, so all six tests stay visible where Claude Code alone shows three.
- **caveman's hook looks only at the first word.** `pytest` and `npm` are on its list, `uv` and `npx` are not, so
  `uv run pytest` and `npx vitest run` pass through; with my commands it wrapped 2 of 16. Its engine kept 404 of
  418 facts on the full output.
- **headroom compresses exactly what Claude Code already cut.** It keeps a failed result verbatim up to 8,000
  characters, and every cut output arrives just over that. Its model then dropped words and operators: "assert
  134570 == (((2 * 59000) + 15000) + 570)" became "assert 134570 == (((2 * 59000) 15000) + 570)". Each compressed
  block carries a hash to retrieve what headroom received, which Claude Code had already cut.

Each tool on the full output, the comparison I pre-registered, is in [RESULTS.md](RESULTS.md), with links to the
lines of each tool's source that explain what it did. My predictions: 6 held, 2 wrong, 2 half. I ran headroom
wrong at first and missed Claude Code's own cut until a review; RESULTS.md says what changed after the results.

## How it works

- `kept_or_cut/cases.py`: the 16 cases (repository, planted edit, command), plus one added after the results.
- `kept_or_cut/needed.py`: what an agent needs from each kind of output, read from the raw text by fixed rules.
- `kept_or_cut/claude_code.py`: what Claude Code 2.1.294 shows the model for a failed command.
- `scripts/capture_raw.py` plants each bug, runs the command and restores the repository; `scripts/compress.py`
  and `scripts/headroom_proxy.py` write what each tool hands over to `corpus/<case>/`.
- `kept_or_cut/analyze.py` and `kept_or_cut/predictions.py` compute every number; `tests/` pins them to
  RESULTS.md and this page.

## Run it

```bash
uv sync
uv run pytest
uv run python -m kept_or_cut.predictions
```

The corpus is committed, so the tests need none of the three tools. Re-capturing it does; see
[RESULTS.md](RESULTS.md#reproduce).

Apache-2.0.
