"""Simulācijas stāvoklis: kuri serveri darbojas, kurš ir aktīvs, scenārijs, režīmi."""

import json

from drill import paths

SERVER_UP = "up"
SERVER_DOWN = "down"


def initial() -> dict:
    return {
        "version": 1,
        "scenario": None,
        "active": "primary",
        "servers": {"primary": SERVER_UP},
        "standby_synced_at": None,
        "restored_from": None,
        "triage_mode": "auto",
        "llm_mode": "normal",
    }


def exists() -> bool:
    return paths.state_file().exists()


def load() -> dict:
    """Atgriež stāvokli. Ja sistēma vēl nav izveidota, atgriež tukšu vārdnīcu."""
    try:
        return json.loads(paths.state_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save(state: dict) -> None:
    path = paths.state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def log_action(text: str) -> None:
    """Darbību žurnāls pasniedzējam: kuru ceļu grupa izvēlējās. Bez laika zīmogiem."""
    path = paths.root() / "darbibu-zurnals.txt"
    if not path.parent.exists():
        return
    with path.open("a", encoding="utf-8") as log:
        log.write(text + "\n")
