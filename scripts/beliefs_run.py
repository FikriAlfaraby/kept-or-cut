"""Ask both models what they believe after reading each view of each run (PREDICTIONS-2.md).

    uv run python scripts/beliefs_run.py            # every missing answer; finished ones are kept
    uv run python scripts/beliefs_run.py luna       # one model

Answers go to corpus/beliefs/<model>/<case>/<view>-<trial>.json with the reply as received and the parsed JSON.
A reply that holds no complete answer (one was cut off mid-string) is asked again; the earlier reply stays in the
record under "earlier".
"""

import json
import shlex
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kept_or_cut.beliefs import MODELS, ask, gateway_key, parse
from kept_or_cut.beliefs_score import TRIALS, VIEWS, answer_path, views
from kept_or_cut.cases import CASES, EXPLORATORY


def main() -> None:
    models = [m for m in sys.argv[1:] if m in MODELS] or list(MODELS)
    runs = json.loads((ROOT / "corpus" / "runs.json").read_text(encoding="utf-8"))
    key = gateway_key()
    jobs = []
    for case in CASES + EXPLORATORY:
        texts = views(case, runs)
        for model in models:
            for view in VIEWS:
                for trial in range(TRIALS):
                    path = answer_path(model, case.id, view, trial)
                    earlier = []
                    if path.exists():
                        old = json.loads(path.read_text(encoding="utf-8"))
                        if parse(old["reply"]) is not None:
                            continue
                        earlier = old.get("earlier", []) + [
                            {"reply": old["reply"], "seconds": old["seconds"]}
                        ]
                    jobs.append((model, case, view, trial, texts[view], path, earlier))

    def one(job):
        model, case, view, trial, text, path, earlier = job
        started = time.time()
        reply = ask(model, shlex.join(case.raw), text, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "model": MODELS[model],
            "case": case.id,
            "view": view,
            "trial": trial,
            "seconds": round(time.time() - started, 1),
            "reply": reply,
            "answer": parse(reply),
        }
        if earlier:
            record["earlier"] = earlier
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return f"{model} {case.id} {view} {trial} {record['seconds']}s parsed={record['answer'] is not None}"

    print(len(jobs), "answers to get", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        for done in as_completed([pool.submit(one, job) for job in jobs]):
            print(done.result(), flush=True)


if __name__ == "__main__":
    main()
