"""What Claude Code really sends the model for each failing command: captured, not rebuilt.

    uv run python scripts/capture_claude_code.py

Added after review. A real `claude -p` runs in each planted repository, pointed at a stub on this machine that plays
the model: its first answer asks for one Bash call (the case's command as an agent types it, then the command rtk's
hook rewrites it to), and it keeps the tool result Claude Code sends back. Nothing leaves the machine and no model is
called. `--bare` skips the user's hooks, plugins, CLAUDE.md and keychain; a throwaway config folder keeps the real one
untouched; the API key is a placeholder only the stub sees; permissions are bypassed because the stub asks for
exactly one command. Writes corpus/<case>/captured-cc-raw.txt and captured-cc-rtk.txt and corpus/captured.json.
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.cases import CASES, EXPLORATORY
from kept_or_cut.plant import ENV, planted, public

sys.path.insert(0, str(ROOT / "scripts"))
from capture_raw import clean, tidy, untracked

TOOL_ID = "toolu_capture_1"
state: dict = {"command": "", "results": [], "requests": 0}


def sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


def reply(model: str, block: dict, stop: str) -> str:
    start = {
        "type": "message_start",
        "message": {
            "id": "msg_stub",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    }
    if block["type"] == "tool_use":
        opened = {"type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}
        delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
    else:
        opened, delta = {"type": "text", "text": ""}, {"type": "text_delta", "text": block["text"]}
    return "".join(
        [
            sse("message_start", start),
            sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": opened}),
            sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
            sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
            sse(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop, "stop_sequence": None},
                    "usage": {"output_tokens": 1},
                },
            ),
            sse("message_stop", {"type": "message_stop"}),
        ]
    )


class Stub(BaseHTTPRequestHandler):
    """The model's API, played on this machine."""

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        state["requests"] += 1
        tools = {t.get("name") for t in body.get("tools") or []}
        last = (body.get("messages") or [{}])[-1].get("content")
        results = [b for b in (last if isinstance(last, list) else []) if b.get("type") == "tool_result"]
        state["results"] += results
        if "Bash" in tools and not results:
            block = {
                "type": "tool_use",
                "id": TOOL_ID,
                "name": "Bash",
                "input": {"command": state["command"], "description": "Run the checks"},
            }
            payload, stop = block, "tool_use"
        else:
            payload, stop = {"type": "text", "text": "Done."}, "end_turn"
        model = body.get("model", "stub")
        if body.get("stream"):
            data, kind = reply(model, payload, stop).encode(), "text/event-stream"
        else:
            data = json.dumps(
                {
                    "id": "msg_stub",
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [payload],
                    "stop_reason": stop,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            ).encode()
            kind = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args) -> None:
        pass


def environment(port: int, config: str) -> dict[str, str]:
    venv = str(ROOT / ".venv")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV" and not k.startswith("ANTHROPIC_")}
    env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep) if not p.startswith(venv))
    return (
        env
        | ENV
        | {
            "CLAUDE_CONFIG_DIR": config,
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}",
            "ANTHROPIC_API_KEY": "sk-ant-local-stub-not-a-key",  # a placeholder: only the stub ever sees it
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
        }
    )


def capture(case, command: str, port: int, config: str) -> dict:
    state.update(command=command, results=[], requests=0)
    before = untracked(case.repo)
    with planted(case.repo, case.edits):
        done = subprocess.run(
            [
                "claude",
                "-p",
                "Run the checks.",
                "--bare",
                "--no-session-persistence",
                "--output-format",
                "json",
                "--permission-mode",
                "bypassPermissions",
            ],
            cwd=case.repo,
            env=environment(port, config),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    tidy(case.repo, before)
    if not clean(case.repo):
        raise SystemExit(f"{case.repo} is not clean after {case.id}")
    mine = [r for r in state["results"] if r.get("tool_use_id") == TOOL_ID]
    if len(mine) != 1:
        raise SystemExit(
            f"{case.id}: expected one tool result, got {len(mine)}; claude said {done.stdout[-400:]}"
        )
    content = mine[0]["content"]
    if isinstance(content, list):
        content = "\n".join(part.get("text", "") for part in content)
    return {
        "text": public(content),
        "is_error": mine[0].get("is_error") is True,
        "requests": state["requests"],
        "claude_exit": done.returncode,
    }


def main() -> None:
    version = subprocess.run(
        ["claude", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    runs = json.loads((ROOT / "corpus" / "runs.json").read_text(encoding="utf-8"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log: dict = {"claude": version, "cases": {}}
    try:
        with tempfile.TemporaryDirectory(prefix="claude-config-") as config:
            for case in CASES + EXPLORATORY:
                for name, command in (("cc-raw", case.raw), ("cc-rtk", runs[case.id]["rtk"]["command"])):
                    if command is None:  # rtk leaves this command alone: its view is the command's own
                        continue
                    got = capture(case, shlex.join(command), server.server_address[1], config)
                    (ROOT / "corpus" / case.id / f"captured-{name}.txt").write_text(
                        got.pop("text"), encoding="utf-8"
                    )
                    log["cases"].setdefault(case.id, {})[name] = {"command": shlex.join(command), **got}
                    print(case.id, name, got)
    finally:
        server.shutdown()
    (ROOT / "corpus" / "captured.json").write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
