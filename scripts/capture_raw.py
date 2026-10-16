"""Capture each case's raw output: plant the bug, run the command as an agent types it, restore.

uv run python scripts/capture_raw.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.cases import CASES
from kept_or_cut.plant import planted, public, run


def untracked(repo: Path) -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "--", "."],
        capture_output=True,
        text=True,
        check=False,
    )
    return set(out.stdout.split()) if out.returncode == 0 else set()


def tidy(repo: Path, before: set[str]) -> None:
    """Remove files the command itself created (uv writes a uv.lock into a repository that has none)."""
    top = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if top.returncode:
        return
    for name in untracked(repo) - before:
        (Path(top.stdout.strip()) / name).unlink(missing_ok=True)


def clean(repo: Path) -> bool:
    inside = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inside.returncode:
        return True  # not a git repository: the planting restores files byte for byte
    return not subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "--", "."],
        capture_output=True,
        text=True,
        check=False,
    ).stdout


for case in CASES:
    if not clean(case.repo):
        raise SystemExit(f"{case.repo} has uncommitted changes; refusing to plant into it")
    before = untracked(case.repo)
    with planted(case.repo, case.edits):
        r = run(case.raw, case.repo)
    tidy(case.repo, before)
    if not clean(case.repo):
        raise SystemExit(f"{case.repo} is not clean after {case.id}")
    out = ROOT / "corpus" / case.id
    out.mkdir(parents=True, exist_ok=True)
    (out / "raw.txt").write_text(public(r.output), encoding="utf-8")
    (out / "raw.json").write_text(
        json.dumps(
            {"command": list(r.command), "exit_code": r.exit_code, "seconds": r.seconds, "what": case.what},
            indent=1,
        )
        + "\n"
    )
    print(f"{case.id}: exit {r.exit_code}, {len(r.output.splitlines())} lines")
