# Results, part 2: what the model believes after reading it

16 October 2026. The predictions were tagged before any model read a case (`v0.2-prereg`,
[PREDICTIONS-2.md](PREDICTIONS-2.md)). GPT-6 Luna and Gemini 3.8 Flash each read five views of 17 failing runs,
three times: 510 answers, every one kept in [corpus/beliefs/](corpus/beliefs/). Every number here comes from
`kept_or_cut/beliefs_score.py` and `kept_or_cut/predictions2.py`, and `tests/test_beliefs.py` holds this file to
them. What I added or changed after the results is listed near the end.

**In short.** Every view still told both models the run failed: 480 of 480 answers on the 16 runs. What changed
was what they could act on, and it followed part 1 closely: each model listed about as many failing tests as the
text still held, and no more. Through rtk, the run with 18 setup errors became "it failed, nothing says what": no
count, no test, no file, in all six answers. On the run with 14 failures and 18 errors, rtk's header says "14
failed"; both models reported 14 in every trial and lost the file with the bug, which every other view led them
to. Where Claude Code's cut removed the totals of the two longest pytest runs, Gemini counted the marks in
pytest's progress bar and got both right; Luna mostly said it could not tell, and once answered 83, a number that
appears nowhere in the text.

## Setup

As pre-registered. Each answer is one request: the command, then the view as the tool result of that command, and
a question asking for JSON: did the run fail, how many things failed, which ones (name, file, line), and which file
to open first. The model has no tools and no repository. The five views are the full output with "Exit code N"
above it, and the four Claude Code views from part 1: Claude Code alone, rtk then Claude Code, caveman's engine then
Claude Code, Claude Code then headroom's proxy. Temperature 0 was requested; answers still varied between trials.

## What each model got right

Luna first, Gemini second. 16 runs; a run counts when 2 of 3 trials agree.

| What the model reads | Count right (of 12) | Failing tests listed | Opens the file with the bug first (of 16) |
|---|---:|---:|---:|
| Full output, no cut | 12 · 12 | 98% · 98% | 11 · 10 |
| Claude Code alone | 9 · 11 | 31% · 33% | 9 · 9 |
| rtk, then Claude Code | 11 · 11 | 38% · 38% | 6 · 8 |
| caveman's engine, then Claude Code | 9 · 10 | 65% · 66% | 8 · 11 |
| Claude Code, then headroom's proxy | 10 · 11 | 24% · 24% | 8 · 10 |

"Count right" is against the run's own summary, on the 12 runs that have one (pytest, vitest, tsc, eslint).
"Failing tests listed" is the share of the 96 failing tests the part 1 rules name, over all trials.

## The model knows what reaches it

| What the model reads | Test names left in the text (part 1) | Listed by Luna | Listed by Gemini |
|---|---:|---:|---:|
| Claude Code alone | 35% | 31% | 33% |
| rtk, then Claude Code | 40% | 38% | 38% |
| caveman's engine, then Claude Code | 68% | 65% | 66% |
| Claude Code, then headroom's proxy | 26% | 24% | 24% |

Part 1 counted what reaches the model; that count predicts what the model reports, view by view. Through Claude
Code alone, no answer listed a test whose name the cut removed. Through caveman's engine, two answers (one per
model) listed a test whose header line the engine had elided, `test_reference_actions_run_without_error[ot-04]`:
the parameter "ot-04" and the function name were both still in the text, and the rebuilt name was right.

## rtk on the run with 18 errors

The model reads three lines: "Exit code 1", "Pytest: 255 passed in 14.89s" and "[full output: rtk recall …]". I
predicted that at least one model would read this as a pass. Neither did: all six answers say the run failed. All
six also give no count, list no failing test and name no file to open. Through every other view, both models
counted the 18 errors in every trial.

A real agent would not stop there. The last line offers the full output, and an agent that runs `rtk recall` gets
it back. This study measures the first read only.

## rtk on the run with 14 failures and 18 errors

rtk's header reads "Pytest: 241 passed, 14 failed in 15.40s"; its summary has no place for errors (part 1). Both
models reported 14 failures in all three trials, against 32 in the run's own summary. The 18 errors are where the
traceback reaches `tools.py`, the file with the renamed attribute. `tools.py` is named 18 times in the full output,
5 times through Claude Code alone, and not once through rtk. Every other view sent both models to `tools.py` in
every trial. Through rtk, Gemini would open the test file each time, and Luna gave three different answers: a class
name, the test file, nothing.

The short count I had predicted was a different one. On the 44-failure run rtk lists ten failures and says "+31
more", and I expected both models to report 41. They both reported 44, from rtk's first line, "Pytest: 153 passed,
44 failed".

## When the cut hides the total

Claude Code's read-back drops the end of the two longest pytest runs, summary line included. The progress bar at
the top survives.

| Run (the run's own total) | Luna, Claude Code alone | Gemini, Claude Code alone |
|---|---|---|
| pytest, 44 failures | none, 83, none | 44, 44, 44 |
| pytest, 14 failures and 18 errors (32) | none, none, 33 | 32, 32, 32 |
| tsc, 43 errors | none, none, none | none, none, none |

The first run's progress bar holds exactly 44 F marks; the second's, 14 F and 18 E. "83" appears nowhere in the
text Luna read. On the tsc run, 31 of the 43 error lines remain, and neither model passed 31 off as the total.

## Where the model would look first

The pre-registered score counts a first look at a file the bug was planted in. It is low for every view, the full
output included, because on five runs neither model opens that file first in any view. On three they start
elsewhere, mostly from the failing test (the 2-failure and 44-failure pytest runs, the 1-failure vitest run). On
two the bug was planted in the test file, and they open the module it imports (the pytest import error, the Go
panic). Predictions 6 and 7 held for Gemini and
failed for Luna: Luna lost two runs through Claude Code alone (11 to 9, where I allowed one) and three more through
rtk (9 to 6).

Added after the results, to compare views without that noise: on how many runs a view changes the file the model
would open first, against the full output (2 of 3 trials agree).

| What the model reads | Runs where the first file changed, Luna | Gemini |
|---|---:|---:|
| Claude Code alone | 3 | 2 |
| rtk, then Claude Code | 7 | 4 |
| caveman's engine, then Claude Code | 4 | 2 |
| Claude Code, then headroom's proxy | 4 | 1 |

One run changes in every view. On the 44-failure run with the full output, Gemini starts from `test_trace.py` line
41, the test of the module with the bug, in every trial (Luna once there, twice from the source folder). Through
every Claude Code view, both start from `test_mutants.py`, where 43 of the 44 failures are: of the one failure in
`test_trace.py`, the cut leaves only its progress mark, "tests/test_trace.py F..", and rtk not even that.

## Predictions: 3 held, 4 wrong

| # | Prediction | Verdict | What happened |
|---|---|---|---|
| 1 | Every view says failed | held | 480 of 480 answers (after the parser fix below) |
| 2 | rtk's "255 passed" read as a pass | wrong | 0 of 3 trials for each model; "Exit code 1" won |
| 3 | rtk's short count believed (41) | wrong | 44 from rtk's header, every trial; the short count that was believed is 14, on another run |
| 4 | No names out of thin air | held | 31% and 33% listed, 35% left in the text |
| 5 | Reworded names stay reworded | held | 0 exact names from headroom's vitest run, every trial |
| 6 | The first file survives the cut | wrong | Luna 11 to 9; Gemini 10 to 9 |
| 7 | rtk keeps the first file | wrong | Luna 9 to 6; Gemini 9 to 8 |

## Added or changed after the results

- **A parser bug.** One reply of 510 (Gemini, the 7-failure vitest run through Claude Code alone, trial 2) stopped
  mid-string after 1,168 characters. My first parser then took the first complete object inside it, one failing
  test, as the answer, and the scorer read that as "did not say the run failed": prediction 1 showed 479 of 480.
  The parser now accepts only an object with `run_failed`; a reply without one is asked again, and the cut-off
  reply stays in the record under `earlier`. The new reply says the run failed, with 7 failures. Every stored reply
  is parsed again from the text as received, and no other answer changed. The cut-off reply's first line already
  said `"run_failed": true`.
- **The first-file comparison** and **the table of names left in the text against names listed**: both computed
  after the results.
- **The check for listed names that are not in the text.** Prediction 4 is scored as written, by shares; the
  direct check backs it.

## Limits

- First read only. The model answers before it can run anything: no `rtk recall`, no rerun, no file to open.
- Two models, through a local gateway, three trials each.
- The file the bug was planted in is not always the one to fix: on the import error and the Go panic, opening the
  imported module first is reasonable. Those runs count against every view alike.
- Names are matched as text; a name rebuilt from parts counts as listed.
- 16 runs, from my own repositories and two small fixtures, plus the run with 18 errors.

## Reproduce

```bash
uv run python scripts/beliefs_run.py          # asks only for missing or unreadable answers; needs the gateway
uv run python -m kept_or_cut.beliefs_score    # the totals and the first-file comparison
uv run python -m kept_or_cut.predictions2     # the seven verdicts
uv run pytest tests/test_beliefs.py
```
