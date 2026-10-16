"""Reads a settings file, used as a fixture: a planted bug gives a chained exception."""

import json
from pathlib import Path


class ConfigError(Exception):
    pass


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path.name} is not valid JSON") from exc


def main() -> None:
    settings = load(Path(__file__).with_name("settings.json"))
    print(f"shipping from {settings['warehouse']} with {settings['courier']}")


if __name__ == "__main__":
    main()
