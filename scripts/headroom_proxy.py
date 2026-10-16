"""headroom the way a coding agent meets it: through its own proxy, started as `headroom wrap claude` starts it.

    uv run python scripts/headroom_proxy.py                  # the full output; writes into corpus/
    uv run python scripts/headroom_proxy.py OUT              # a repeat run, written to OUT/ instead
    uv run python scripts/headroom_proxy.py --claude-code    # what Claude Code sends (kept_or_cut/claude_code.py)

Added after the results; not pre-registered. The pre-registered headroom runs called compress() in a minimal install
(no extras, so no compression model). Here headroom-ai[all] 0.41.0 runs its proxy with the flags `headroom wrap claude`
passes (a port and one worker, so the default cache mode), and again in token mode. Its compression model must be
loaded before the first case is sent, or the run stops.

Each case is sent as a failed Bash call: the call, then a tool result marked is_error whose text starts with
"Exit code N" (the shape Claude Code writes in its own transcripts). By default the text is the full output, and
what the proxy forwarded is written to <case>/headroom-proxy[-token].txt without the "Exit code N" line. With
--claude-code the text is exactly what Claude Code would send, cut included, and the forwarded text is written whole
to corpus/<case>/cc-headroom-proxy[-token].txt. The proxy forwards to a stub on this machine that keeps the request
and answers "ok"; nothing leaves the machine.
"""

import gzip
import json
import os
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.cases import CASES, EXPLORATORY
from kept_or_cut.claude_code import failed_command

PROMPT = "The checks are failing. Find the cause and fix it."  # the request the compress() runs used
MODEL = "claude-sonnet-5-5"
CONFIGS = {"headroom-proxy": [], "headroom-proxy-token": ["--mode", "token"]}
QUIET = {
    "DO_NOT_TRACK": "1",
    "HEADROOM_TELEMETRY": "off",
    "HEADROOM_BEACON": "off",
    "HEADROOM_TELEMETRY_WARN": "off",
    "HEADROOM_OFFLINE": "1",  # the model is already in the local cache; nothing is fetched
    "HF_HUB_OFFLINE": "1",
}

received: list[dict] = []


class Stub(BaseHTTPRequestHandler):
    """The model's API, played on this machine: keeps every request and answers with one short reply."""

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        encoding = self.headers.get("Content-Encoding", "")
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding:
            raise ValueError(f"the proxy sent a body encoded as {encoding}")
        received.append({"path": self.path, "body": json.loads(body or b"{}")})
        self._answer(
            {
                "id": "msg_stub",
                "type": "message",
                "role": "assistant",
                "model": MODEL,
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

    def do_GET(self) -> None:
        self._answer({})

    def _answer(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except OSError:
        return 0, {}


def wait_for_model(base: str, proxy: subprocess.Popen, timeout: float = 240) -> dict:
    """Until /debug/warmup reports the Kompress model loaded; a run without it would not be headroom's default."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proxy.poll() is not None:
            raise SystemExit("the proxy exited before it was ready")
        status, warmup = get(f"{base}/debug/warmup")
        kompress = {k: v for k, v in warmup.items() if "kompress" in k.lower()}
        if status == 200 and kompress and all(v.get("status") == "loaded" for v in kompress.values()):
            return kompress
        time.sleep(2)
    raise SystemExit("the Kompress model did not load; refusing to record a run without it")


def request(case, content: str) -> dict:
    tool_id = f"toolu_{case.id.replace('-', '_')}"
    return {
        "model": MODEL,
        "max_tokens": 1024,
        "stream": False,
        "tools": [
            {
                "name": "Bash",
                "description": "Run a shell command.",
                "input_schema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}, "description": {"type": "string"}},
                    "required": ["command"],
                },
            }
        ],
        "messages": [
            {"role": "user", "content": PROMPT},
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_id,
                        "name": "Bash",
                        "input": {"command": shlex.join(case.raw), "description": "Run the checks"},
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "is_error": True,
                        "content": content,
                    }
                ],
            },
        ],
    }


def tool_text(body: dict, tool_id: str) -> tuple[str, dict]:
    for message in body["messages"]:
        for block in message.get("content") if isinstance(message.get("content"), list) else []:
            if block.get("type") == "tool_result" and block.get("tool_use_id") == tool_id:
                content = block.get("content")
                if isinstance(content, list):
                    content = "\n".join(part.get("text", "") for part in content)
                return content, block
    raise SystemExit(f"the forwarded request has no result for {tool_id}")


def run_config(
    name: str, flags: list[str], stub_port: int, log: dict, out_root: Path, claude_code: bool
) -> None:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    with (
        tempfile.TemporaryDirectory(prefix="headroom-proxy-") as tmp,
        open(Path(tmp) / "stdio.log", "w") as stdio,
    ):
        requests_log = Path(tmp) / "requests.jsonl"
        cmd = [
            sys.executable,
            "-m",
            "headroom.cli",
            "proxy",
            "--port",
            str(port),
            "--workers",
            "1",
            *flags,
            "--anthropic-api-url",
            f"http://127.0.0.1:{stub_port}",
            "--log-file",
            str(requests_log),
        ]
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANTHROPIC_")} | QUIET
        proxy = subprocess.Popen(cmd, env=env, stdout=stdio, stderr=subprocess.STDOUT)
        try:
            warmup = wait_for_model(base, proxy)
            for case in CASES + EXPLORATORY:
                case_dir = ROOT / "corpus" / case.id
                raw = (case_dir / "raw.txt").read_text(encoding="utf-8")
                exit_code = json.loads((case_dir / "raw.json").read_text(encoding="utf-8"))["exit_code"]
                prefix = f"Exit code {exit_code}\n"
                content = failed_command(exit_code, raw) if claude_code else prefix + raw
                body = request(case, content)
                before = len(received)
                req = urllib.request.Request(
                    f"{base}/v1/messages",
                    data=json.dumps(body).encode(),
                    method="POST",
                    headers={
                        "content-type": "application/json",
                        "anthropic-version": "2023-06-01",
                        "x-api-key": "local-stub",
                    },
                )
                with urllib.request.urlopen(req, timeout=300) as r:
                    if r.status != 200:
                        raise SystemExit(f"{case.id}: the proxy answered {r.status}")
                forwarded = [x for x in received[before:] if x["path"].endswith("/v1/messages")]
                if len(forwarded) != 1:
                    raise SystemExit(f"{case.id}: expected one forwarded request, got {len(forwarded)}")
                tool_id = body["messages"][1]["content"][0]["id"]
                text, block = tool_text(forwarded[0]["body"], tool_id)
                kept_prefix = text.startswith(prefix)
                (out_root / case.id).mkdir(parents=True, exist_ok=True)
                kept = text if claude_code else text.removeprefix(prefix)
                (out_root / case.id / f"{name}.txt").write_text(kept, encoding="utf-8")
                log.setdefault(case.id, {})[name] = {
                    "exit_code_line_kept": kept_prefix,
                    "is_error_kept": block.get("is_error") is True,
                    "tools_added": sorted(
                        {t["name"] for t in forwarded[0]["body"].get("tools", [])} - {"Bash"}
                    ),
                }
                print(name, case.id, "done")
        except BaseException:
            stdio.flush()
            print("".join((Path(tmp) / "stdio.log").read_text(encoding="utf-8").splitlines(True)[-40:]))
            raise
        finally:
            proxy.terminate()
            proxy.wait(timeout=30)
        entries = [json.loads(line) for line in requests_log.read_text(encoding="utf-8").splitlines() if line]
        for case, entry in zip(CASES + EXPLORATORY, entries, strict=True):
            log[case.id][name] |= {
                k: entry.get(k)
                for k in ("input_tokens_original", "input_tokens_optimized", "transforms_applied")
            }
        log.setdefault("_proxy", {})[name] = {"command": ["headroom", "proxy", *flags], "kompress": warmup}


def main() -> None:
    stub = ThreadingHTTPServer(("127.0.0.1", free_port()), Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()
    args = sys.argv[1:]
    claude_code = "--claude-code" in args
    folders = [a for a in args if a != "--claude-code"]
    out_root = Path(folders[0]) if folders else ROOT / "corpus"
    runs = out_root / "runs.json"
    log = json.loads(runs.read_text(encoding="utf-8")) if runs.exists() else {}
    try:
        proxy_log: dict = {}
        for name, flags in CONFIGS.items():
            name = f"cc-{name}" if claude_code else name
            run_config(name, flags, stub.server_address[1], proxy_log, out_root, claude_code)
    finally:
        stub.shutdown()
    for case_id, entry in proxy_log.items():
        log.setdefault(case_id, {}).update(entry)
    runs.write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
