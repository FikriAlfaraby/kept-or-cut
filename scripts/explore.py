"""Run the raw commands only (no compressor), to see what each planted bug produces. Not part of the study."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kept_or_cut.cases import CASES
from kept_or_cut.plant import planted, run

wanted = set(sys.argv[1:])
for case in CASES:
    if wanted and case.id not in wanted:
        continue
    with planted(case.repo, case.edits):
        r = run(case.raw, case.repo)
    lines = r.output.splitlines()
    print(f"== {case.id}: exit {r.exit_code}, {len(lines)} lines, {len(r.output)} chars, {r.seconds}s")
    print("\n".join(lines[-6:]))
