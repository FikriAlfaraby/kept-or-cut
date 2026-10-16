"""The three compressors, each run the way an agent meets it, offline and without model calls."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from headroom.compress import CompressConfig, compress

from .plant import ENV

CAVEMAN = Path.home() / "Documents" / "Projects" / "oss" / "caveman"
CAVEMAN_ENGINE = Path.home() / "Documents" / "Projects" / "oss" / "bin" / "caveman-engine"
CAVEMAN_HOOK_SOURCE = CAVEMAN / "packages" / "cli" / "src" / "index.ts"


def rtk_rewrite(command: tuple[str, ...]) -> tuple[str, ...] | None:
    """What rtk's hook runs instead of `command`, from `rtk rewrite`, or None when it leaves the command alone."""
    done = subprocess.run(
        ["rtk", "rewrite", shlex.join(command)],
        capture_output=True,
        text=True,
        env={**os.environ, **ENV},
        check=False,
    )
    if done.returncode in (0, 3) and done.stdout.strip():
        return tuple(shlex.split(done.stdout.strip()))
    return None


def caveman_allowlist() -> set[str]:
    """SHRINK_ALLOW, read from caveman's own hook source."""
    source = CAVEMAN_HOOK_SOURCE.read_text(encoding="utf-8")
    body = re.search(r"const SHRINK_ALLOW = new Set\(\[(.*?)\]\);", source, re.DOTALL)
    if not body:
        raise SystemExit("caveman's SHRINK_ALLOW moved; reread packages/cli/src/index.ts")
    return set(re.findall(r'"([^"]+)"', body.group(1)))


def caveman_hook_wraps(command: tuple[str, ...]) -> bool:
    """caveman's shouldShrink, for the commands in this study: allowlisted first word, no shell operators, no
    streaming flags. (Its skip list of interactive subcommands never applies to these commands.)"""
    cmd = shlex.join(command)
    if re.search(r"[|&;<>`]|\$\(|\\\s*$|\n", cmd):
        return False
    if re.search(r"(^|\s)-(f|it|ti|w)\b|--follow\b|--watch\b|--interactive\b|--tail\b", cmd):
        return False
    return command[0] in caveman_allowlist()


def caveman_engine(text: str, home: Path) -> tuple[str, dict]:
    """The engine's terminal mode, which `caveman shrink` (the hook's path) uses. Returns what shrink prints on
    stdout, and the engine's report, with the stderr shrink passes on (an agent sees it when the command failed)."""
    done = subprocess.run(
        [str(CAVEMAN_ENGINE), "compress", "--type", "terminal"],
        input=text,
        capture_output=True,
        text=True,
        env={**os.environ, **ENV, "CAVEMAN_HOME": str(home)},
        check=False,
    )
    if done.returncode:
        raise SystemExit(f"caveman-engine failed: {done.stderr[:300]}")
    stats: dict = {}
    for line in reversed(done.stderr.splitlines() + done.stdout.splitlines()):
        if line.startswith("{") and '"tokens_before"' in line:
            stats = json.loads(line)
            break
    out = "\n".join(
        ln for ln in done.stdout.splitlines() if not (ln.startswith("{") and '"tokens_before"' in ln)
    )
    out += "\n" if done.stdout.endswith("\n") else ""
    return out + shrink_footer(out, stats), {**stats, "stderr": done.stderr}


def shrink_footer(out: str, stats: dict) -> str:
    """The line `caveman shrink` prints under a shrunk output when the engine kept the original (emitShrunk in
    packages/cli/src/index.ts at d262ab3). Added after review: the first runs left it out."""
    handle = stats.get("recovery_handle") or ""
    if not handle:
        return ""
    before, after = stats.get("tokens_before"), stats.get("tokens_after")
    valid = all(isinstance(n, int) and n >= 0 for n in (before, after))
    counts = (
        f"{before}→{after} estimated tokens"
        if valid and after <= before
        else "estimated token count unavailable"
    )
    basis = str(stats.get("token_count_basis") or "").strip() or "unavailable"
    newline = "\n" if out and not out.endswith("\n") else ""
    return f"{newline}‹caveman: shrank · {counts} · counter {basis} · inferred · recover: caveman retrieve {handle}›\n"


def headroom(
    text: str, command: tuple[str, ...], aggressive: bool, unprotected: bool = False
) -> tuple[str, dict]:
    """headroom's compress() on a short agent conversation whose last message is the command's output."""
    messages = [
        {"role": "user", "content": "The checks are failing. Find the cause and fix it."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "bash", "arguments": json.dumps({"command": shlex.join(command)})},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": text},
    ]
    if unprotected:  # exploratory: nothing shielded, to see what its compressors do to the output itself
        config = CompressConfig(protect_recent=0, protect_analysis_context=False, diagnostics=True)
    elif aggressive:
        config = CompressConfig(protect_recent=0, diagnostics=True)
    else:
        config = CompressConfig(diagnostics=True)  # the defaults; diagnostics only records each decision
    result = compress(messages, config=config)
    out = result.messages[-1]["content"]
    # headroom's own reason for what it did to the output (e.g. "protected:error_output", "passthrough:small")
    decision = next(
        (d.action for d in result.diagnostics or [] if d.message_index == len(messages) - 1), None
    )
    return out, {
        "tokens_before": result.tokens_before,
        "tokens_after": result.tokens_after,
        "transforms": list(result.transforms_applied or []),
        "decision": decision,
    }
