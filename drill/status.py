"""make status: serviss, serveri, ieraksti, jaunākais ieraksts, triāžas pašpārbaude."""

import sqlite3

from drill import clock, paths, runtime, state

SERVER_NAMES = {"primary": "galvenais serveris", "standby": "rezerves serveris"}


def portal_check() -> str:
    """Pārbauda portālu caur lietotni (tāpat kā to redz iedzīvotājs un darbinieks)."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    health = client.get("/health")
    if health.status_code == 503:
        return "NEDARBOJAS (kļūda 503: serviss nav pieejams)"
    if health.status_code != 200:
        return f"KĻŪDA ({health.status_code})"
    listing = client.get("/submissions")
    if listing.status_code != 200:
        return f"KĻŪDA: iesniegumu saraksts neatveras (kļūda {listing.status_code})"
    return "darbojas"


def database_facts() -> tuple[int, str, str] | None:
    """(ierakstu skaits, jaunākā ieraksta ID, laiks) vai None, ja datubāze nav pieejama."""
    try:
        path = runtime.active_db_path()
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            (total,) = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
            newest = conn.execute(
                "SELECT id, receivedAt FROM submissions ORDER BY receivedAt DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    except (runtime.Unavailable, sqlite3.DatabaseError):
        return None
    if newest is None:
        return total, "", ""
    return total, newest[0], newest[1]


def server_line(current: dict, server: str) -> str:
    status = current["servers"].get(server)
    if status == state.SERVER_UP:
        text = "darbojas"
        if server == "standby" and current.get("standby_synced_at"):
            text += f", sinhronizēts {clock.fmt_dt(current['standby_synced_at'])}"
        return text
    return "NEDARBOJAS (datu krātuve nav pieejama)"


def triage_line(current: dict) -> str:
    from app import triage

    if runtime.triage_config_dir() is None:
        return "nav iespējama (serviss nedarbojas)"
    mode = (
        "manuāla sadale (Kanceleja)"
        if current.get("triage_mode") == "manual"
        else ("automātiska sadale")
    )
    result = triage.self_test()
    if not result.ok:
        return f"NEATBILD: {result.detail} · {mode}"
    config = triage.active_config()
    return f"atbild · modelis {config.model} ({result.model_version}) · {mode}"


def run() -> list[str]:
    current = state.load()
    if not current:
        return ["Mācību sistēma vēl nav izveidota. Palaidiet: make reset"]
    lines = [
        'Ezermalas e-pakalpojums "Iesniegumi" · stāvoklis',
        f"Simulētais laiks: {clock.fmt_dt(clock.NOW)}",
        "",
        f"  Portāls:             {portal_check()}",
        f"  Aktīvais serveris:   {SERVER_NAMES[current['active']]}",
    ]
    for server in ("primary", "standby"):
        if server in current["servers"]:
            label = SERVER_NAMES[server].capitalize() + ":"
            lines.append(f"  {label:<21}{server_line(current, server)}")
    facts = database_facts()
    if facts is None:
        lines.append("  Iesniegumi:          nav nolasāmi")
    else:
        total, newest_id, newest_at = facts
        lines.append(f"  Iesniegumi:          {clock.fmt_int(total)}")
        if newest_id:
            lines.append(
                f"  Jaunākais ieraksts:  {newest_id}, {clock.fmt_dt(newest_at)}"
            )
    lines.append(f"  Triāžas pašpārbaude: {triage_line(current)}")
    if paths.nas_dir().exists():
        lines += ["", "Rezerves kopijas: make backup-list"]
    return lines
