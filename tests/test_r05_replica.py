"""R-05: rezerves serveris (warm standby) un make replicate."""

import sqlite3
from datetime import datetime

from drill import faults, paths, state
from drill.clock import TZ
from tests.drill_helpers import run


def _count(server, where="1=1"):
    conn = sqlite3.connect(paths.db_path(server))
    try:
        return conn.execute(
            f"SELECT COUNT(*) FROM submissions WHERE {where}"
        ).fetchone()[0]
    finally:
        conn.close()


def test_standby_is_synced_every_15_minutes(sistema, capsys):
    current = state.load()
    assert current["standby_synced_at"] == "2026-10-19T08:30:00+03:00"
    assert _count("standby") < _count("primary")
    _code, out = run(capsys, "status")
    assert (
        "Rezerves serveris:   darbojas, sinhronizēts pirmdiena 19.10.2026 08:30" in out
    )


def test_replicate_copies_primary(sistema, capsys):
    code, out = run(capsys, "replicate")
    assert code == 0
    assert "sinhronizēts" in out
    assert _count("standby") == _count("primary")
    assert state.load()["standby_synced_at"] == "2026-10-19T08:40:00+03:00"


def test_corrupting_primary_and_replicating_gives_corrupt_standby(sistema, capsys):
    corrupted = faults.corrupt_records(
        paths.db_path("primary"), datetime(2026, 10, 19, 8, 12, tzinfo=TZ)
    )
    assert corrupted > 2000
    run(capsys, "replicate")
    assert _count("standby", "personalCode = ''") == corrupted


def test_replicate_refuses_when_primary_is_down(sistema, capsys):
    current = state.load()
    faults.lose_storage(current, ("primary",))
    state.save(current)
    code, out = run(capsys, "replicate")
    assert code == 1
    assert "galvenais serveris nedarbojas" in out
