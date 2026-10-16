"""Plant one bug in a real repository, run a command, put the repository back exactly as it was.

The edit is a plain text replacement (or a new file). Every edited file is backed up before it is touched,
and the original bytes are written back in a `finally`, so an interrupted run leaves no change behind.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# What an agent's shell looks like to a tool: no colour, no pager, no interactive prompts, no telemetry.
ENV = {
    "NO_COLOR": "1",
    "FORCE_COLOR": "0",
    "CI": "1",
    "PAGER": "cat",
    "DO_NOT_TRACK": "1",
    "HEADROOM_BEACON": "off",
    "HEADROOM_OFFLINE": "1",
    "HEADROOM_TELEMETRY_WARN": "off",
}


@dataclass(frozen=True)
class Edit:
    path: str  # relative to the repository
    old: str | None  # None: create the file with `new`
    new: str


@dataclass(frozen=True)
class Run:
    command: tuple[str, ...]
    exit_code: int
    output: str  # stdout and stderr together, as an agent's shell tool returns them
    seconds: float


@contextmanager
def planted(repo: Path, edits: tuple[Edit, ...]) -> Iterator[None]:
    backup = Path(tempfile.mkdtemp(prefix="kept-or-cut-"))
    originals: dict[Path, bytes | None] = {}
    try:
        for edit in edits:
            target = repo / edit.path
            if target not in originals:
                originals[target] = target.read_bytes() if target.exists() else None
                if target.exists():
                    (backup / str(len(originals))).write_bytes(originals[target])
            if edit.old is None:
                if target.exists():
                    raise SystemExit(f"{target} exists; a created file must be new")
                target.write_text(edit.new, encoding="utf-8")
                continue
            text = target.read_text(encoding="utf-8")
            if text.count(edit.old) != 1:
                raise SystemExit(
                    f"{target}: the text to replace appears {text.count(edit.old)} times, not once"
                )
            target.write_text(text.replace(edit.old, edit.new), encoding="utf-8")
        yield
    finally:
        for target, data in originals.items():
            if data is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(data)
        shutil.rmtree(backup, ignore_errors=True)


HOME = str(Path.home())


def public(text: str) -> str:
    """The published copy: this machine's home folder written as a neutral one."""
    return text.replace(HOME + "/", "/home/dev/")


def run(command: tuple[str, ...], cwd: Path, timeout: int = 600) -> Run:
    started = time.time()
    done = subprocess.run(
        list(command),
        cwd=cwd,
        env={**os.environ, **ENV},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    # stdout then stderr: what a tool call returns when both are captured
    output = done.stdout + (
        ("\n" if done.stdout and not done.stdout.endswith("\n") else "") + done.stderr if done.stderr else ""
    )
    return Run(command, done.returncode, output, round(time.time() - started, 2))
