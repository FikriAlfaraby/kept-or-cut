# Results

16 October 2026. The predictions were tagged before any compressor ran on the cases (`v0.1-prereg`,
[PREDICTIONS.md](PREDICTIONS.md)). Every number here comes from `kept_or_cut/analyze.py` and
`kept_or_cut/predictions.py`, and `tests/test_results.py` holds this file to them. What I added or changed after
the results, including after a review, is listed near the end.

**In short.** In Claude Code, the agent never reads the middle of a long failing run: Claude Code itself keeps the
first and last 5,000 characters of a failed command's output. On these 16 runs that alone leaves 101 of 159 failing
items fully visible. With rtk it is 75, at 46% fewer tokens; with caveman's engine, 104; with headroom's proxy, 88,
because it rewrites the assertions that are left. rtk's summary of a run with 18 errors reads as a pass, "Pytest:
255 passed"; only the exit code above it says something failed.

## In Claude Code

Added after the results. Claude Code 2.1.294 builds a failed command's tool result from "Exit code N" and the
command's output, stdout before stderr; above 11,024 characters it keeps the first 5,000 and the last 5,000
([kept_or_cut/claude_code.py](kept_or_cut/claude_code.py) has the rule and how I checked it). Five of the 16
outputs are that long. rtk and caveman's hook change the command, so Claude Code cuts what they print. headroom's
proxy sits after Claude Code, so it receives the cut text.

| What the model reads | Facts kept | Items fully visible | Outputs with every fact | Tokens |
|---|---:|---:|---:|---:|
| Claude Code alone | 340 | 101 | 12 | 18,720 |
| rtk, then Claude Code | 270 | 75 | 9 | 10,030 (−46%) |
| caveman's hook, then Claude Code | 340 | 101 | 12 | 18,790 (0%) |
| caveman's engine, then Claude Code | 340 | 104 | 10 | 19,853 (+6%) |
| Claude Code, then headroom's proxy | 308 | 88 | 11 | 15,754 (−16%) |

Failing items fully visible in the five long runs:

| Run | Claude Code alone | rtk | caveman's engine | headroom's proxy |
|---|---:|---:|---:|---:|
| pytest, 44 failures | 13 | 10 | 28 | 8 |
| pytest, 6 failures | 3 | 6 | 4 | 2 |
| pytest, 32 failures and errors | 18 | 10 | 18 | 18 |
| vitest, 7 failures | 7 | 5 | 3 | 0 |
| tsc, 43 errors | 29 | 29 | 29 | 29 |

A shorter output can show more. rtk's summary of the 6-failure run fits under the cut, so all six tests are
visible, against three for Claude Code alone. caveman's engine packs the 44-failure run tightly enough that 28
tests fit in the window, against 13.

Getting the dropped text back works differently behind the cut. rtk's recall line and caveman's retrieve line
fetch the full output the command printed. headroom's retrieve gives back what headroom received, which Claude Code
had already cut. Claude Code alone offers no way back; the agent has to run the command again.

## Each tool on the full output

The pre-registered comparison: what each tool hands over, against the full raw output. 16 planted bugs; 159
failing items; 418 needed facts (each item's name, message and file:line); 60,387 tokens (o200k).

| What the agent receives | Facts kept | Items fully visible | Outputs with every fact | Tokens |
|---|---:|---:|---:|---:|
| The raw output | 418 | 159 | 16 | 60,387 |
| rtk 1.0.1, through its hook | 282 | 85 | 10 | 11,118 (−82%) |
| caveman 4.0.1, through its hook | 418 | 159 | 16 | 60,387 (0%) |
| caveman's engine on every output | 404 | 145 | 13 | 35,464 (−41%) |
| headroom 0.41.0's proxy, given the full output (added later) | 407 | 152 | 15 | 55,592 (−8%) |
| headroom `compress()`, as pre-registered | 418 | 159 | 16 | 60,387 (0%) |

An item is fully visible when its name, message and location all survive; items are the count to read. The 418
facts hold only 237 different ones. The 44 failing tests in one run share 6 messages and 2 locations, so a tool
that shows a few of them keeps most of their message facts: rtk keeps 42 of those 44 messages and shows 10 of the
44 tests.

## rtk

rtk's hook rewrites the command (`uv run pytest` becomes `uv run rtk pytest`) and the agent reads rtk's summary.

- **Errors drop out of the summary.** A run with 14 failing tests and 18 errors in setup came back as "Pytest: 241
  passed, 14 failed". rtk counts passed, failed, skipped, xfailed and xpassed, not errors
  ([pytest_cmd.rs:182](https://github.com/rtk-ai/rtk/blob/v1.0.1/src/cmds/python/pytest_cmd.rs#L182)). It reads
  failures from pytest's FAILURES section, not its ERRORS section, and it runs pytest with `-rxX`, which replaces
  the default short summary that lists each error
  ([pytest_cmd.rs:46](https://github.com/rtk-ai/rtk/blob/v1.0.1/src/cmds/python/pytest_cmd.rs#L46)). This was
  already reported in [rtk-ai/rtk#4426](https://github.com/rtk-ai/rtk/issues/4426) (3 October), and a fix is open
  in [rtk-ai/rtk#4466](https://github.com/rtk-ai/rtk/pull/4466).
- **A broken run can read as a clean one.** In a case I added after the results to test this, a fixture cannot
  build its object, so 18 tests error and none fail. pytest ends with "255 passed, 1 warning, 18 errors". rtk
  printed "Pytest: 255 passed in 18.56s" and a recall id, nothing else
  ([pytest_cmd.rs:217](https://github.com/rtk-ai/rtk/blob/v1.0.1/src/cmds/python/pytest_cmd.rs#L217)). 0 of the
  54 needed facts survived; in Claude Code, only the "Exit code 1" line above the summary says something failed.
  rtk does pass a run through whole when it can parse nothing
  ([pytest_cmd.rs:65](https://github.com/rtk-ai/rtk/blob/v1.0.1/src/cmds/python/pytest_cmd.rs#L65)); this run
  reported its passes, so that guard did not fire.
- **Past ten failures, a count, and the count is short.** With 44 failing tests rtk shows 10 and says "+31 more
  failures"; 34 remain. It splits failures on lines that start with three underscores, and pytest draws shorter
  rules around long test names, so three failures were merged into their neighbours
  ([pytest_cmd.rs:150](https://github.com/rtk-ai/rtk/blob/v1.0.1/src/cmds/python/pytest_cmd.rs#L150)). With 32
  failing or erroring tests it showed 10 and said "+4 more".
- **Lint becomes counts.** Both eslint runs came back as errors per rule and per file: no line numbers, no
  messages. 0 of 30 facts.
- **A Go panic loses its place.** rtk kept the panic message and frames from Go's own testing package, and cut the
  frame in my code (`shipping.go:12`).
- **Where it did well.** Both collection errors came through whole and said the run failed, so my prediction 1 was
  wrong. The pytest runs with 2 and 6 failures kept every name and location. It leaves `python3 script.py` alone,
  so both tracebacks were untouched.

Every output where rtk dropped something ends with `[full output: rtk recall <id>]`, so the text can be
recovered. The agent has to know it needs it, and nothing in "255 passed" says what failed.

## caveman

- **The hook looks only at the first word.** It shrinks a command when the first word is on a list of 41
  ([`SHRINK_ALLOW` and `shouldShrink`](https://github.com/JuliusBrussee/caveman/blob/d262ab3882952a59312ff3537cd86d894523c5ab/packages/cli/src/index.ts#L16611)).
  `pytest`, `npm`, `pnpm`, `vitest`, `tsc` and `eslint` are on it; `uv`, `npx` and `python3` are not. With my
  commands it wrapped the two `go test` runs, and both came back unchanged. I typed the TypeScript checks as
  `npx vitest run`, `npx tsc --noEmit` and `npx eslint`; that project's README and CI run them as `npm test`,
  `npm run typecheck` and `npm run lint`, and typed that way the hook would wrap 8 of the 16 commands. The engine
  rows show what wrapping gives.
- **The engine keeps nearly everything.** 404 of 418 facts, 41% fewer tokens. It lost the file name above each
  group of lint errors (9 of 12 lint errors lost their file), 4 of 7 `❯ file:line` pointers in the vitest run, and
  one frame line in a pytest run. An elided line becomes `… 2 lines elided (caveman) …`, and the output ends with
  `recover: caveman retrieve <handle>`, so the original is one command away.
- **In Claude Code it helps some long runs and hurts one.** Its outputs for the five long runs are still over the
  cut, but denser: it shows more of two pytest runs (28 of 44 tests against 13, 4 of 6 against 3), the same of two,
  and fewer of the vitest run (3 of 7 against 7). It also prints a one-line JSON report on stderr, which Claude Code
  shows for a failed command, so it costs 6% more tokens than Claude Code alone.

## headroom

- **My pre-registered setup was wrong.** I called headroom's `compress()` in a minimal install, without its
  compression model or its content detector. That run changed nothing, but it is not what a coding agent gets.
  After the results I ran its proxy the way `headroom wrap claude` starts it: `headroom-ai[all]`, its model
  (Kompress, 261 MB, pinned by headroom) loaded first, each case sent as a failed Bash result (`is_error`, starting
  "Exit code N") and forwarded to a stub on this machine ([scripts/headroom_proxy.py](scripts/headroom_proxy.py)).
- **Small failures stay verbatim, on purpose.** headroom never compresses a failed tool result up to 8,000
  characters
  ([content_router.py:1977](https://github.com/headroomlabs-ai/headroom/blob/v0.41.0/headroom/transforms/content_router.py#L1977)).
- **Behind Claude Code, it compresses exactly what Claude Code already cut.** Each cut output arrives at about
  10,040 characters, just over that limit. Its model then drops words, and sometimes operators: "assert 134570 ==
  (((2 * 59000) + 15000) + 570)" became "assert 134570 == (((2 * 59000) 15000) + 570)", and "AssertionError:
  assert 199000 == 198000" became "AssertionError: 199000 198000". In the vitest run no failing test kept its
  name: "parses '800jt' as 800 million" became "parses '800jt' 800 million". It kept 308 facts against 340 for
  Claude Code alone, for 16% fewer tokens. Each compressed block ends with "Retrieve more: hash=…" and the proxy
  adds a `headroom_retrieve` tool, which returns the text headroom received: the cut one.
- **Given the full output** (a client that sends long failures whole), it left 11 of the 16 outputs unchanged,
  reworded the vitest names the same way, and kept 407 facts for 8% fewer tokens.
- **Repeatability.** Behind Claude Code, three runs gave the same output every time, in both modes
  ([corpus/cc-headroom-proxy-repeats.json](corpus/cc-headroom-proxy-repeats.json)). Given the full output, six
  runs: token mode gave the same output every time; cache mode, the default, gave two versions of the 32-failure
  pytest output (19,341 and 19,353 tokens), both with every fact
  ([corpus/headroom-proxy-repeats.json](corpus/headroom-proxy-repeats.json)). Runs I made while building the
  harness, not kept, also varied on the 6-failure output.
- `headroom wrap` also sets `PYTEST_ADDOPTS=-q` and quiets npm for the agent; my outputs were captured without
  those settings.

## Predictions

Scored in code against the five pre-registered configurations: 6 held, 2 wrong, 2 half.

| # | Prediction | Verdict | What happened |
|---|---|---|---|
| 1 | rtk hides collection errors | wrong | both came through whole, saying the run failed |
| 2 | rtk drops failing tests past ten | held | names lost: 34 of 44, 22 of 32 |
| 3 | rtk drops every lint line number | held | 0 of 3 and 0 of 12 kept |
| 4 | rtk keeps the names but loses places | half | it kept the names, and the places too |
| 5 | rtk leaves tracebacks alone | held | both unchanged |
| 6 | caveman's hook wraps only Go | held | it wraps the two `go test` runs |
| 7 | caveman's engine keeps nearly everything | held | 13 of 16 outputs whole |
| 8 | caveman merges numbers | wrong | all four Go rows kept |
| 9 | headroom's default changes nothing | held | 16 of 16 unchanged |
| 10 | headroom aggressive is safe on small outputs, not on large ones | half | it changed none of them |

Predictions 5, 6 and 9 follow from reading each tool's source; they test my reading more than the tools.
Predictions 9 and 10 were scored on the headroom setup I should not have used. Prediction 10 called its four
outputs "the four largest"; by size the fourth largest is the pytest run with 6 failures, not the tsc run, and
headroom changed neither. What I said would surprise me did: rtk reported a collection error as an error.

## Added or changed after the results

- **Added:** the case with errors in setup; headroom through its proxy, on the full output and behind Claude Code;
  the Claude Code view; repeat runs of the proxy.
- **Fixed after a review:**
  - A number on a later row, such as "(14 tests)" under a file name, counted as a line number. Now a later row
    counts only when it opens with the number, as in "14:5  error" or "line 14". One fact changed: caveman's
    engine, vitest run.
  - A pytest failure's location could be a frame inside Python itself (`json/decoder.py`). Now it is the last
    frame in the project. One fact changed for every configuration.
  - caveman's outputs were missing the recover line `caveman shrink` prints.
  - Prediction 4 has two parts and is now scored like prediction 10: half.
  - The proxy runs first sent the full output and called that the shape Claude Code sends. Claude Code cuts long
    failures first; both runs are reported now. My first Claude Code view also put stderr before stdout, which
    Claude Code does for some errors but not for a failed Bash command; a recorded run settled it.
- **Before the runs:** the tagged harness set `RTK_RECALL=0`, which hides rtk's recall line. I removed it, so rtk
  ran as installed.

## Limits

- 16 bugs, planted in four of my repositories and two small fixtures, one run of each command. Python, Go and
  TypeScript tools only.
- A fact counts as kept only when its exact text survives. headroom's reworded names count as lost, though a
  person would recognise most of them.
- The commands are mine. The TypeScript project's own npm scripts would route differently through both hooks.
- The Claude Code view is rebuilt from the shipped code, not captured from a live session; it matches the one cut
  in my own transcripts.
- rtk ran its command live in the same planted state, so its timings differ from the raw run.
- No model was asked to fix anything. Whether an agent would run `rtk recall`, `caveman retrieve` or
  `headroom_retrieve` when it needs the dropped text was not measured.

## Reproduce

```bash
uv sync
uv run python scripts/capture_raw.py                   # plants each bug, runs the command, restores the repo
uv run python scripts/compress.py                      # rtk, caveman, headroom compress()
uv run python scripts/headroom_proxy.py                # headroom's proxy on the full output
uv run python scripts/headroom_proxy.py --claude-code  # and on what Claude Code sends
uv run python scripts/headroom_proxy.py RUN1           # a repeat into its own folder; then:
uv run python scripts/proxy_repeats.py RUN1 RUN2 RUN3 RUN4 RUN5
uv run python -m kept_or_cut.predictions
uv run pytest
```

The capture needs the four repositories checked out next to this one, plus rtk 1.0.1, the caveman engine built at
d262ab3, and Go 1.26.
