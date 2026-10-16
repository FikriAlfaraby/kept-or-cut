"""What Claude Code puts in front of the model when a Bash command fails. Added after review; not pre-registered.

Captured from a real session (scripts/capture_claude_code.py): `claude -p`, Claude Code 2.1.294, runs each failing
command in its planted repository, pointed at a stub on this machine that plays the model and keeps the tool result
Claude Code sends back. Those captures are cc-raw and cc-rtk below.

The same behaviour, read from the shipped binary, rebuilds those two from raw.txt (`rebuilt`, kept as a cross-check
and for the views no session ran). The Bash tool writes a command's output to a file and reads back only its first
30,000 bytes (BASH_MAX_OUTPUT_LENGTH's default, `Jar=30000`; `#m` reads the file from offset 0 up to that many bytes).
The tool result is "Exit code N" and that block, joined by a newline and trimmed. Above 11,024 characters it keeps
the first 5,000 and the last 5,000, with "... [N characters truncated] ..." between them. The rebuild gives the
captured count of whole failures for every case. The texts differ in timings, temporary names and, for vitest, the
order: Claude Code keeps stdout and stderr in the order the command wrote them, and raw.txt stored stdout first.

Each configuration's view:

- cc-raw: the command itself, captured.
- cc-rtk: the command rtk's hook rewrites it to, captured; the command's own output when rtk leaves it alone.
- cc-caveman-engine: rebuilt: what `caveman shrink` prints (the shrunk output and its recover line, then the engine's
  report on stderr), read back and cut as above. No session ran caveman's CLI.
- cc-caveman-hook: cc-caveman-engine when the hook wraps the command, else cc-raw.
- cc-headroom-proxy: what headroom's proxy forwarded when the tool result was cc-raw (scripts/headroom_proxy.py).
"""

from __future__ import annotations

import json
from pathlib import Path

LIMIT = 10_000  # the default of Claude Code's head-and-tail cut
GRACE = 1_024  # a text this much over the limit is left whole
READ_BACK = 30_000  # bytes of a command's output the Bash tool reads back before anything else
VIEWS = ("cc-raw", "cc-rtk", "cc-caveman-hook", "cc-caveman-engine", "cc-headroom-proxy")


def cut(text: str, limit: int = LIMIT) -> str:
    if len(text) <= limit + GRACE:
        return text
    head = limit // 2
    tail = limit - head
    return f"{text[:head]}\n\n... [{len(text) - head - tail} characters truncated] ...\n\n{text[-tail:]}"


def read_back(output: str, limit: int = READ_BACK) -> str:
    data = output.encode("utf-8")
    # a character split at the limit decodes to U+FFFD, as Node's Buffer.toString does
    return output if len(data) <= limit else data[:limit].decode("utf-8", errors="replace")


def failed_command(exit_code: int, output: str) -> str:
    return cut("\n".join(part for part in (f"Exit code {exit_code}", read_back(output)) if part).strip())


def rebuilt(case_dir: Path, runs: dict) -> dict[str, str]:
    """cc-raw and cc-rtk as the binary's rules make them from raw.txt and rtk.txt."""
    raw = (case_dir / "raw.txt").read_text(encoding="utf-8")
    exit_code = json.loads((case_dir / "raw.json").read_text(encoding="utf-8"))["exit_code"]
    rtk = runs[case_dir.name]["rtk"]
    out = {"cc-raw": failed_command(exit_code, raw)}
    out["cc-rtk"] = (
        failed_command(rtk["exit_code"], (case_dir / "rtk.txt").read_text(encoding="utf-8"))
        if rtk["command"]
        else out["cc-raw"]
    )
    return out


def views(case_dir: Path, runs: dict) -> dict[str, str]:
    run = runs[case_dir.name]
    exit_code = json.loads((case_dir / "raw.json").read_text(encoding="utf-8"))["exit_code"]
    out = {"cc-raw": (case_dir / "captured-cc-raw.txt").read_text(encoding="utf-8")}
    rtk = case_dir / "captured-cc-rtk.txt"
    out["cc-rtk"] = rtk.read_text(encoding="utf-8") if rtk.exists() else out["cc-raw"]
    engine = (case_dir / "caveman-engine.txt").read_text(encoding="utf-8")
    out["cc-caveman-engine"] = failed_command(exit_code, engine + run["caveman-engine"]["stderr"])
    out["cc-caveman-hook"] = out["cc-caveman-engine"] if run["caveman-hook"]["wraps"] else out["cc-raw"]
    proxy = case_dir / "cc-headroom-proxy.txt"
    if proxy.exists():
        out["cc-headroom-proxy"] = proxy.read_text(encoding="utf-8")
    return out
