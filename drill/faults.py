"""Kļūmes, ko izmanto scenāriji: loģiski bojāti dati un zudusi datu krātuve."""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from drill import paths, state


def corrupt_records(db_path: Path, before: datetime) -> int:
    """Loģisks bojājums: kļūdains datu tīrīšanas darbs notīra laukus.

    Ieraksti paliek datubāzē, bet personas kods, vārds, e-pasts un teksts ir
    tukši, un termiņš nav derīgs datums. Atgriež bojāto ierakstu skaitu.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE submissions
            SET personalCode = '', fullName = '', email = '', body = '', dueDate = ''
            WHERE receivedAt < ?
            """,
            (before.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def lose_storage(current: dict, servers: tuple[str, ...]) -> None:
    """Datu krātuves masīva kļūme: serveru diski zūd, serveri nedarbojas."""
    for server in servers:
        directory = paths.server_dir(server)
        if directory.exists():
            shutil.rmtree(directory)
        current["servers"][server] = state.SERVER_DOWN
