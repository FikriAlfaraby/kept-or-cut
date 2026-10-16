# Predictions, part 2: what the model believes after reading it

Written 16 October 2026, before any model read a case. Part 1 counted which lines reach the model. This part asks
the model what it believes after reading them: did the run fail, how many things failed, which ones, and where it
would look first.

## Setup

- **Views**, five per run: the full output (no cut, "Exit code N" above it); and as a Claude Code session hands it
  to the model, from part 1: Claude Code alone (captured), rtk then Claude Code (captured), caveman's engine then
  Claude Code (rebuilt), Claude Code then headroom's proxy.
- **Runs:** the 16 cases, and the run with 18 errors added after part 1's results, reported apart.
- **Models:** GPT-6 Luna (`cx/gpt-6-luna`) and Gemini 3.8 Flash (`ag/gemini-3.8-flash`) through a local gateway,
  temperature 0 requested, three trials each: 17 x 5 x 2 x 3 = 510 answers.
- **Prompt** (`kept_or_cut/beliefs.py`): a coding agent that ran the case's command gets the view as the tool result
  and answers in JSON: `run_failed`, `failing_count`, `failing` (name, file, line of each failure it can see) and
  `first_look` (the file it would open first). It has no repository access.

## Scoring, by code (`kept_or_cut/beliefs_score.py`)

- **Knows it failed:** `run_failed` is true.
- **Count:** `failing_count` equals what the run's own summary counts, for the runs that have one: pytest (failed
  plus errors), vitest (failed tests), tsc (errors), eslint (problems). Go and traceback runs are not counted.
- **Names:** of the failing tests the part 1 rules name (pytest, vitest, go), the share the model lists, matched as
  text (the model may add the file or class before the name).
- **First look:** the file named in `first_look` is a file the bug was planted in (by base name).

## Predictions

1. **Every view says failed.** Through every view of the 16 runs, both models say the run failed, in every trial.
2. **A pass read as a pass.** Given rtk's summary of the run with 18 errors ("Exit code 1" above "Pytest: 255
   passed"), at least one model says the run did not fail in at least 2 of its 3 trials.
3. **A short count is believed.** Given rtk's summary of the 44-failure run ("… +31 more failures"), both models
   report 41 failures in at least 2 of 3 trials.
4. **No names out of thin air.** Through Claude Code alone, neither model lists a failing test whose name the cut
   removed: over the runs with names, each model's name share is at most the share of names left in the text, plus
   0.02.
5. **Reworded names stay reworded.** Given headroom's proxy on the 7-failure vitest run, both models list none of
   the 7 test names exactly, in every trial.
6. **The first file survives the cut.** With the full output, each model's first look is a planted file in at least
   9 of the 16 runs (in at least 2 of 3 trials). Through Claude Code alone, each model loses at most one of those.
7. **rtk keeps the first file.** Through rtk, each model's first-look count is within one run of its count through
   Claude Code alone.

What would surprise me: a model listing a cut test name exactly (it would have to guess it), or either model saying a
run passed when the view shows a failure in plain words.
