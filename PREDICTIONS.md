# Predictions, written before any compressor ran on the cases

16 October 2026. The question: when a token-compression tool for coding agents shrinks the output of a failing
command, does the line the agent needs to fix the problem survive?

## The tools, as installed

- **rtk** 1.0.1 (Homebrew core). Its hook rewrites an agent's shell command; `rtk rewrite "<command>"` prints that
  rewrite, and a command it does not rewrite reaches the agent unchanged.
- **caveman** engine v4.0.1 (built from github.com/JuliusBrussee/caveman at d262ab3). Its hook routes a command
  through `caveman shrink` (the engine's terminal mode) only when the command's first word is on its allowlist and
  the command has no shell operators (`packages/cli/src/index.ts`, `shouldShrink`).
- **headroom** 0.41.0 (PyPI). It compresses tool results inside a conversation; by default it protects the 4 most
  recent messages (`protect_recent=4`), and its own token benchmark sets `protect_recent=0`.

All three run offline here, with telemetry off and no model calls.

## The cases

16 planted bugs in real repositories (oracle-mutants, auditor-mutants, toko-wa-bench, wa-lead-extractor) and
two small fixtures (Python scripts, a Go package), each run with the command an agent would type
(`kept_or_cut/cases.py`): six pytest runs (2, 44 and 6 failing tests; 14 failing tests plus 18 errors in setup; a
syntax error and an import error at collection), two Python tracebacks (a KeyError four frames deep; a chained exception), two `go test` runs (four
failing table rows; a panic), two vitest runs (1 and 7 failing tests), two `tsc` runs (1 and 43 errors) and two
eslint runs (3 and 12 errors). The raw outputs were captured before this file was written.

## What counts as needed

`kept_or_cut/needed.py` reads the raw output by fixed rules: for every failing item, its **name** (the test, or
the file that failed to collect), its **message** (the first 60 characters of the error, whitespace collapsed) and
its **location** (the file's base name with the line number written as a location). 418 facts in all; every one
is present in the raw output. A fact survives when it can still be found in the compressed output.

## The configurations

1. **rtk**: the command `rtk rewrite` gives, run in the same planted state; the raw output when it does not rewrite.
2. **caveman hook**: the engine's terminal mode on the raw output when `shouldShrink` would wrap the command as
   typed; the raw output otherwise.
3. **caveman engine**: terminal mode on every raw output, as if the hook had wrapped it.
4. **headroom default**: `compress()` with the raw output as the latest tool message.
5. **headroom aggressive**: the same with `protect_recent=0`, the setting of headroom's own benchmark.

## Predictions

1. **rtk hides collection errors.** In both pytest runs that fail at collection, rtk's output does not say the run
   failed, and the error message is lost.
2. **rtk drops failing tests past ten.** In the runs with 44 failing tests and with 32 failing or erroring tests,
   at least one failing test's name is missing.
3. **rtk drops every lint line number.** In both eslint runs, no error's line number survives.
4. **rtk keeps the names but loses places.** In the pytest runs with 2 and 6 failures, every failing test's name
   survives and at least one location is lost.
5. **rtk leaves tracebacks alone.** It does not rewrite `python3 <script>`, so both tracebacks reach the agent
   unchanged.
6. **caveman's hook wraps only Go.** Of the 16 commands as typed, it wraps the two `go test` runs and no other.
7. **caveman's engine keeps nearly everything.** In at least 12 of the 16 cases, terminal mode keeps every needed
   fact.
8. **caveman merges numbers.** In the Go run with four failing rows that differ only in their numbers, terminal
   mode loses at least one of the four messages.
9. **headroom's default changes nothing.** With the output as the latest message, every case comes back unchanged.
10. **headroom aggressive is safe on small outputs, not on large ones.** Every output under 8,000 characters comes
    back with all its needed facts, and at least one of the four largest outputs (44 failing tests, 32 failing or
    erroring tests, 7 failing vitest tests, 43 tsc errors) loses at least one.

What would surprise me: rtk reporting a collection error as an error, which would mean my reading of its pytest
parser is wrong; or caveman losing a needed fact in a short single-failure output.
