# kept-or-cut

**Does the error line a coding agent needs survive token compression?**

Replay what the model reads, run by run and tool by tool: [fikrialfaraby.com/compress](https://fikrialfaraby.com/compress/).

Token-compression tools shrink what a coding agent reads from the shell. rtk (83k GitHub stars) "reduces LLM
token consumption by 60-90% on common dev commands". headroom (75k) promises "20% fewer tokens for coding agents"
and "same answers". caveman (113k) reports 18 of 18 answers right. Those are averages. An agent fixing a failing
run needs a few exact lines: the failing test's name, the error message, the file and line.

I planted 16 bugs in four of my repositories and two small fixtures, ran each failing command, and checked by
fixed rules which of those lines each tool keeps. The predictions were tagged before any tool ran on the cases
([PREDICTIONS.md](PREDICTIONS.md), tag `v0.1-prereg`).

## Results

In Claude Code, the agent never reads the middle of a long failing run. Claude Code reads back the first 30,000
bytes of a failed command's output and keeps the first and last 5,000 characters of that, and each tool sits
before or after that cut. Captured from a real Claude Code session, 159 failing items:

| What the model reads | Items fully visible | Tokens |
|---|---:|---:|
| Claude Code alone | 83 | 18,973 |
| rtk, then Claude Code | 75 | 10,034 (−47%) |
| caveman's hook, then Claude Code | 83 | 19,038 (0%) |
| caveman's engine, then Claude Code | 102 | 19,917 (+5%) |
| Claude Code, then headroom's proxy | 69 | 15,857 (−16%) |

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
wrong at first, and two reviews by separate AI agents caught what I had missed of Claude Code's own cut; RESULTS.md
says what changed after the results.

## Does the model still find the bug?

Part 2 asked two models, GPT-6 Luna and Gemini 3.8 Flash, what they believe after reading each view: did the run
fail, how many things failed, which ones, and which file to open first. 510 answers, predictions tagged first
([PREDICTIONS-2.md](PREDICTIONS-2.md), tag `v0.2-prereg`), results in [RESULTS-2.md](RESULTS-2.md).

- **The model knows what reaches it.** Both models said the run failed in all 480 answers on the 16 runs, and
  listed about as many failing tests as the text still held: 31% and 33% through Claude Code alone, where 35% of
  the names are left; 65% and 66% through caveman's engine, where 68% are.
- **rtk can leave nothing to act on.** On the run with 18 errors, all six answers say it failed, and none gives a
  count, a test or a file. On the run with 14 failures and 18 errors, rtk's header says "14 failed"; both models
  reported 14 in every trial and lost the file with the bug, which every other view led them to.
- **A total the cut removed is rebuilt or left blank.** Through Claude Code alone, Gemini gave the totals of the
  two longest pytest runs right in every trial, though only pytest's progress bar still showed them; Luna mostly
  said it could not tell, and once answered 83, a number that is not in the text.

My predictions: 3 held, 4 wrong.

## How it works

- `kept_or_cut/cases.py`: the 16 cases (repository, planted edit, command), plus one added after the results.
- `kept_or_cut/needed.py`: what an agent needs from each kind of output, read from the raw text by fixed rules.
- `kept_or_cut/claude_code.py`: what Claude Code 2.1.294 shows the model for a failed command.
- `scripts/capture_raw.py` plants each bug, runs the command and restores the repository; `scripts/compress.py`
  and `scripts/headroom_proxy.py` write what each tool hands over to `corpus/<case>/`.
- `kept_or_cut/analyze.py` and `kept_or_cut/predictions.py` compute every number; `tests/` pins them to
  RESULTS.md and this page.
- Part 2: `kept_or_cut/beliefs.py` asks a model through a local gateway, `scripts/beliefs_run.py` asks all 510
  questions, and `kept_or_cut/beliefs_score.py` and `kept_or_cut/predictions2.py` score the answers kept in
  `corpus/beliefs/`.

## Run it

```bash
uv sync
uv run pytest
uv run python -m kept_or_cut.predictions
uv run python -m kept_or_cut.predictions2
```

The corpus and the models' answers are committed, so the tests need none of the three tools and no model. Re-capturing it does; see
[RESULTS.md](RESULTS.md#reproduce).

Apache-2.0.
