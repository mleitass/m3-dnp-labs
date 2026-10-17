"""Ko redz lietotne: aktīvā servera datubāze, triāžas konfigurācija un režīms."""

from pathlib import Path

from drill import paths, state


class Unavailable(Exception):
    """Aktīvais serveris vai tā datubāze nav pieejama."""


def active_server() -> str | None:
    current = state.load()
    return current.get("active") if current else None


def active_db_path() -> Path:
    current = state.load()
    if not current:
        raise Unavailable("sistēma nav izveidota (make reset)")
    server = current["active"]
    if current["servers"].get(server) != state.SERVER_UP:
        raise Unavailable("serveris nedarbojas")
    path = paths.db_path(server)
    if not path.exists():
        raise Unavailable("datubāze nav atrasta")
    return path


def triage_config_dir() -> Path | None:
    current = state.load()
    if not current:
        return None
    server = current["active"]
    if current["servers"].get(server) != state.SERVER_UP:
        return None
    return paths.triage_dir(server)


def triage_mode() -> str:
    return state.load().get("triage_mode", "auto")


def llm_mode() -> str:
    return state.load().get("llm_mode", "normal")
