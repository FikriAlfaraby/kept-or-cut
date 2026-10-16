"""What Claude Code puts in front of the model when a Bash command fails. Added after review; not pre-registered.

Read from Claude Code 2.1.294, the shipped binary. The Bash tool writes a command's output to a file and reads back
only its first 30,000 bytes (BASH_MAX_OUTPUT_LENGTH's default, `Jar=30000`; `#m` reads the file from offset 0 up to
that many bytes). The tool result is "Exit code N" and that block, joined by a newline and trimmed. Above 11,024
characters it keeps the first 5,000 and the last 5,000, with "... [N characters truncated] ..." between them.

Checked against my own transcripts. One cut run (2.1.295) is 10,040 characters with the marker at character 5,002,
and its last characters stop mid-word, about 30,000 characters into the output: the read-back, which my first
version of this file left out (a reviewer found it).
One failed vitest run shows the block as stdout, then stderr: the summary vitest prints on stdout comes before the
failure details it prints on stderr, though through a single pipe vitest writes the details first. The raw capture
stored stdout and then stderr, so raw.txt is that block.

Each configuration's view is that text, built from what the configuration hands Claude Code:

- cc-raw: the command itself.
- cc-rtk: rtk's output, with rtk's exit code; the command's own output when rtk leaves the command alone.
- cc-caveman-engine: what `caveman shrink` prints: the shrunk output and its recover line, then the engine's
  report, which it writes on stderr.
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


def views(case_dir: Path, runs: dict) -> dict[str, str]:
    run = runs[case_dir.name]
    raw = (case_dir / "raw.txt").read_text(encoding="utf-8")
    exit_code = json.loads((case_dir / "raw.json").read_text(encoding="utf-8"))["exit_code"]
    out = {"cc-raw": failed_command(exit_code, raw)}
    rtk = run["rtk"]
    out["cc-rtk"] = (
        failed_command(rtk["exit_code"], (case_dir / "rtk.txt").read_text(encoding="utf-8"))
        if rtk["command"]
        else out["cc-raw"]
    )
    engine = (case_dir / "caveman-engine.txt").read_text(encoding="utf-8")
    out["cc-caveman-engine"] = failed_command(exit_code, engine + run["caveman-engine"]["stderr"])
    out["cc-caveman-hook"] = out["cc-caveman-engine"] if run["caveman-hook"]["wraps"] else out["cc-raw"]
    proxy = case_dir / "cc-headroom-proxy.txt"
    if proxy.exists():
        out["cc-headroom-proxy"] = proxy.read_text(encoding="utf-8")
    return out
