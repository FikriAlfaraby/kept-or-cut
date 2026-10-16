"""What the model believes after reading a failing run: did it fail, how many failed, which ones, where to look.

Part 2 of the study (PREDICTIONS-2.md). Each view of a run goes to a model as the result of a Bash call it made; the
model answers in JSON. Every answer is kept under corpus/beliefs/, so a run can be resumed and re-scored without
calling a model again.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY = "http://127.0.0.1:20128/v1/chat/completions"
MODELS = {"luna": "cx/gpt-6-luna", "gemini": "ag/gemini-3.8-flash"}
SYSTEM = "You are a coding agent working in a repository. You ran a shell command to check the code."
QUESTION = """The command was: {command}

This is the tool result you got back:

<tool_result>
{text}
</tool_result>

Before you change anything, say what you now believe. Answer with one JSON object and nothing else:
{{"run_failed": true or false,
 "failing_count": the number of failing tests or errors, or null if the result does not tell you,
 "failing": [{{"name": "the test name, or null for a type or lint error", "file": "file name", "line": line number or null}}],
 "first_look": {{"file": "the file you would open first to fix it", "line": line number or null}}}}
List in "failing" only what the tool result shows. Use null where it does not say."""


def gateway_key() -> str:
    """Read at run time from the local gateway's config; never printed or written."""
    text = (Path.home() / ".omp" / "agent" / "models.yml").read_text(encoding="utf-8")
    match = re.search(r"9router:\s*\n\s*baseUrl:.*\n\s*api:.*\n\s*apiKey:\s*(\S+)", text)
    if not match:
        raise SystemExit("no 9router key in ~/.omp/agent/models.yml")
    return match.group(1).strip("'\"")


def content_of(body: str) -> str:
    """The reply text, from a JSON body or from server-sent events (some models answer in SSE either way)."""
    body = body.strip()
    if body.startswith("{"):
        data = json.loads(body)
        return data["choices"][0]["message"].get("content") or ""
    parts = []
    for line in body.splitlines():
        if not line.startswith("data:") or line.strip() == "data: [DONE]":
            continue
        chunk = json.loads(line[5:])
        for choice in chunk.get("choices") or []:
            parts.append((choice.get("delta") or choice.get("message") or {}).get("content") or "")
    return "".join(parts)


def ask(model: str, command: str, text: str, key: str, attempts: int = 4) -> str:
    payload = {
        "model": MODELS[model],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": QUESTION.format(command=command, text=text)},
        ],
    }
    request = urllib.request.Request(
        GATEWAY,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return content_of(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def parse(reply: str) -> dict | None:
    """The first JSON object in the reply, or None when there is none."""
    start = reply.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(reply)):
            if reply[end] == "{":
                depth += 1
            elif reply[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(reply[start : end + 1])
                    except json.JSONDecodeError:
                        break
        start = reply.find("{", start + 1)
    return None
