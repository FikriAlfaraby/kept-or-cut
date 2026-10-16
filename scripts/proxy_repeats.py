"""How repeatable headroom's proxy is: the same outputs sent again, each time through a freshly started proxy.

    uv run python scripts/headroom_proxy.py RUN1        # once per repeat, each into its own folder
    uv run python scripts/proxy_repeats.py RUN1 RUN2 ...
    uv run python scripts/proxy_repeats.py --claude-code RUN1 RUN2 ...   # the runs behind Claude Code's cut

Writes corpus/headroom-proxy-repeats.json (or cc-headroom-proxy-repeats.json). The corpus run comes first. For every run, configuration and case it
records the output's sha256 (first 16 hex digits), its tokens and how many needed facts it keeps; the summary gives,
per configuration and case, how many different outputs the runs produced and the range of facts kept.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.analyze import tokens
from kept_or_cut.cases import CASES, EXPLORATORY
from kept_or_cut.needed import needed, survives

CONFIGS = ("headroom-proxy", "headroom-proxy-token")


def describe(folder: Path, configs: tuple[str, ...]) -> dict:
    out: dict = {}
    for config in configs:
        for case in CASES + EXPLORATORY:
            raw = (ROOT / "corpus" / case.id / "raw.txt").read_text(encoding="utf-8")
            text = (folder / case.id / f"{config}.txt").read_text(encoding="utf-8")
            out.setdefault(config, {})[case.id] = {
                "sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
                "tokens": tokens(text),
                "kept": sum(survives(f, text) for f in needed(case.kind, raw)),
            }
    return out


def main() -> None:
    claude_code = "--claude-code" in sys.argv[1:]
    configs = tuple(f"cc-{c}" for c in CONFIGS) if claude_code else CONFIGS
    folders = [ROOT / "corpus", *(Path(a) for a in sys.argv[1:] if a != "--claude-code")]
    runs = [describe(folder, configs) for folder in folders]
    summary: dict = {}
    for config in configs:
        for case in CASES + EXPLORATORY:
            rows = [run[config][case.id] for run in runs]
            summary.setdefault(config, {})[case.id] = {
                "different_outputs": len({r["sha256"] for r in rows}),
                "kept": [min(r["kept"] for r in rows), max(r["kept"] for r in rows)],
                "tokens": [min(r["tokens"] for r in rows), max(r["tokens"] for r in rows)],
            }
    data = {"runs": len(runs), "summary": summary, "per_run": runs}
    name = "cc-headroom-proxy-repeats.json" if claude_code else "headroom-proxy-repeats.json"
    (ROOT / "corpus" / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
