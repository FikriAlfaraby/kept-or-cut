"""What a coding agent needs from a failing run, read from the raw output by fixed rules, and whether it survives.

For every failing item (a test, a collection error, a type error, a lint error, an exception) the needed facts are:

- name: which test or file failed (not used for type and lint errors, where the location names them);
- message: the error message, its first 60 characters with whitespace collapsed;
- location: the file and line to open, matched by the file's base name and the line number.

A fact survives when it can still be found in the compressed output. The rules are deliberately lenient about
format (a tool may regroup lines, shorten paths or reorder fields) and strict about content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MESSAGE_CHARS = 60
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class Fact:
    item: str  # the failing item this fact belongs to
    field: str  # name | message | location
    text: str  # what must be found
    line: int | None = None  # for a location: the line number; `text` is then the file's base name


def flat(text: str) -> str:
    return " ".join(ANSI.sub("", text).split())


def base(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def message(text: str) -> str:
    return flat(text)[:MESSAGE_CHARS]


# --- pytest -------------------------------------------------------------------------------------------------

SECTION = re.compile(r"^_+ (.+?) _+$", re.MULTILINE)  # long titles get a single underscore each side
# a frame: "path.py:12: AssertionError", or "path.py:12: " when the frame's code follows on the next lines
WHERE = re.compile(r"^(\S+\.py):(\d+):(?: |$)", re.MULTILINE)
# the agent needs a line in the project, not in Python itself or an installed package (amended after review)
OUTSIDE = ("/lib/python", "site-packages", "<frozen")


def _pytest(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    heads = list(SECTION.finditer(raw))
    for i, head in enumerate(heads):
        body = raw[head.end() : heads[i + 1].start() if i + 1 < len(heads) else len(raw)]
        body = body.split("=========================== short test summary info", 1)[0]
        title = head.group(1).strip()
        if title.startswith("ERROR collecting "):
            path = title.removeprefix("ERROR collecting ")
            item = base(path)
            facts.append(Fact(item, "name", item))
            # a syntax error names the line in an `E  File "...", line N` row; an import error in a `path:N: in` row
            where = re.search(r'^E\s+File "([^"]+)", line (\d+)', body, re.MULTILINE) or re.search(
                rf"^({re.escape(path)}):(\d+): in ", body, re.MULTILINE
            )
            if where:
                facts.append(Fact(item, "location", base(where.group(1)), int(where.group(2))))
            last_e = [ln for ln in body.splitlines() if re.match(r"^E\s+\w+(\.\w+)*(Error|Exception)\b", ln)]
            if last_e:
                facts.append(Fact(item, "message", message(re.sub(r"^E\s+", "", last_e[-1]))))
            continue
        title = re.sub(r"^ERROR at (setup|teardown) of ", "", title)  # an error in a fixture names its test
        head_name = title.split("[", 1)[0]
        item = (
            title[head_name.rindex(".") + 1 :] if "." in head_name else title
        )  # TestClass.test_x[...] -> test_x[...]
        facts.append(Fact(item, "name", item))
        if m := re.search(r"^E\s+(.+)$", body, re.MULTILINE):
            facts.append(Fact(item, "message", message(m.group(1))))
        wheres = [(p, ln) for p, ln in WHERE.findall(body) if not any(o in p for o in OUTSIDE)]
        if wheres:
            path, line = wheres[-1]
            facts.append(Fact(item, "location", base(path), int(line)))
    return facts


# --- vitest -------------------------------------------------------------------------------------------------

VITEST_FAIL = re.compile(r"^ FAIL  (\S+) > (.+)$", re.MULTILINE)


def _vitest(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    detail = raw.split("Failed Tests", 1)[-1]
    blocks = list(VITEST_FAIL.finditer(detail))
    for i, head in enumerate(blocks):
        body = detail[head.end() : blocks[i + 1].start() if i + 1 < len(blocks) else len(detail)]
        item = head.group(2).split(" > ")[-1].strip()
        facts.append(Fact(item, "name", item))
        if m := re.search(r"^(\w*Error: .+)$", body, re.MULTILINE):
            facts.append(Fact(item, "message", message(m.group(1))))
        if m := re.search(r"❯ (\S+):(\d+):\d+", body):
            facts.append(Fact(item, "location", base(m.group(1)), int(m.group(2))))
    return facts


# --- tsc, eslint --------------------------------------------------------------------------------------------

TSC = re.compile(r"^(\S+)\((\d+),\d+\): error (TS\d+): (.+)$", re.MULTILINE)


def _tsc(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    for path, line, code, text in TSC.findall(raw):
        item = f"{base(path)}:{line} {code}"
        facts.append(Fact(item, "message", message(f"{code}: {text}")))
        facts.append(Fact(item, "location", base(path), int(line)))
    return facts


ESLINT_FILE = re.compile(r"^(/\S+|\S+\.[jt]sx?)$")
ESLINT_ROW = re.compile(r"^\s+(\d+):\d+\s+(error|warning)\s+(.+?)\s{2,}(\S+)$")


def _eslint(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    current = ""
    for row in raw.splitlines():
        if ESLINT_FILE.match(row.strip()) and not row.startswith(" "):
            current = base(row.strip())
        elif m := ESLINT_ROW.match(row):
            line, _, text, rule = m.groups()
            item = f"{current}:{line} {rule}"
            facts.append(Fact(item, "message", message(text)))
            facts.append(Fact(item, "location", current, int(line)))
    return facts


# --- Python tracebacks, go test -----------------------------------------------------------------------------

FRAME = re.compile(r'^\s+File "([^"]+)", line (\d+), in ', re.MULTILINE)


def _traceback(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    for n, chunk in enumerate(raw.split("Traceback (most recent call last):")[1:], 1):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        exc = next((ln for ln in lines if re.match(r"^[\w.]+(Error|Exception)\b", ln)), None)
        item = f"exception {n}"
        if exc:
            facts.append(Fact(item, "message", message(exc)))
        own = [
            (p, int(ln)) for p, ln in FRAME.findall(chunk) if "/lib/python" not in p and "<frozen" not in p
        ]
        if own:
            facts.append(Fact(item, "location", base(own[-1][0]), own[-1][1]))
    return facts


def _gotest(raw: str) -> list[Fact]:
    facts: list[Fact] = []
    for name in re.findall(r"^--- FAIL: (\w+)", raw, re.MULTILINE):
        facts.append(Fact(name, "name", name))
    for path, line, text in re.findall(r"^\s+(\w+_test\.go):(\d+): (.+)$", raw, re.MULTILINE):
        item = f"{path}:{line} {text}"
        facts.append(Fact(item, "message", message(text)))
        facts.append(Fact(item, "location", path, int(line)))
    if m := re.search(r"^(panic: .+?)(?: \[recovered.*)?$", raw, re.MULTILINE):
        facts.append(Fact("panic", "message", message(m.group(1))))
        own = [
            (p, int(ln))
            for p, ln in re.findall(r"^\s+(/\S+\.go):(\d+)", raw, re.MULTILINE)
            if "/libexec/src/" not in p and "/go/src/" not in p
        ]
        if own:
            facts.append(Fact("panic", "location", base(own[0][0]), own[0][1]))
    return facts


EXTRACT = {
    "pytest": _pytest,
    "vitest": _vitest,
    "tsc": _tsc,
    "eslint": _eslint,
    "traceback": _traceback,
    "gotest": _gotest,
}


def needed(kind: str, raw: str) -> list[Fact]:
    facts = EXTRACT[kind](raw)
    if not facts:
        raise ValueError(f"no failing item found in a {kind} output")
    return facts


def survives(fact: Fact, compressed: str) -> bool:
    text = ANSI.sub("", compressed)
    if fact.field in ("name", "message"):
        return flat(fact.text) in flat(text)
    # a location: the base name, then the line number written as a location (":12", "(12,", "line 12", "L12"),
    # on the same line, or opening a row under it ("12:5  error", "L12:", "line 12"; a tool that groups errors by
    # file), within the next 30 lines. Amended after review: any number on a later row counted, so "(14 tests)"
    # under a file name passed for line 14.
    lines = text.splitlines()
    number = re.compile(rf"(?:[:(]|\bline |\bL|^\s*)\s*{fact.line}(?=[:,)\s]|$)")
    grouped = re.compile(rf"^\s*(?:L?{fact.line}[:,]|line {fact.line}\b)")
    for i, row in enumerate(lines):
        if fact.text in row:
            if number.search(row.split(fact.text, 1)[1]):
                return True
            for later in lines[i + 1 : i + 31]:
                if (
                    re.search(r"\S+\.(py|ts|tsx|js|go)\b", later)
                    and fact.text not in later
                    and not later.startswith(" ")
                ):
                    break  # the next file's block
                if grouped.search(later):
                    return True
    return False
