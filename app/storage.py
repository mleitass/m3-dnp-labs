"""Iesniegumu glabātuve: SQLite.

Divi režīmi:
- sistēma (noklusējums): datubāzes fails aktīvajā serverī mapē sistema/.
  Ja serveris nedarbojas vai datubāzes nav, glabātuve ziņo ServiceUnavailable.
- atmiņa: testiem. reset() izveido datubāzi atmiņā ar trim sintētiskiem iesniegumiem.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from drill import clock, runtime

COLUMNS = (
    "id",
    "personalCode",
    "fullName",
    "email",
    "preferredChannel",
    "topic",
    "subject",
    "body",
    "status",
    "receivedAt",
    "dueDate",
    "replyChannel",
    "reasonCode",
    "department",
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    personalCode TEXT NOT NULL,
    fullName TEXT NOT NULL,
    email TEXT NOT NULL,
    preferredChannel TEXT NOT NULL,
    topic TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    receivedAt TEXT NOT NULL,
    dueDate TEXT NOT NULL,
    replyChannel TEXT NOT NULL,
    reasonCode TEXT,
    department TEXT
);
CREATE TABLE IF NOT EXISTS attachments (
    submission_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (submission_id, filename)
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Sintētiski dati. Personas kodi neatbilst reālām personām.
SEED = (
    {
        "personalCode": "32000000101",
        "fullName": "Jānis Paraudziņš",
        "email": "janis.paraudzins@example.com",
        "preferredChannel": "EMAIL",
        "topic": "ROADS",
        "subject": "Bedre Ezera ielā",
        "body": "Ezera ielā pie 12. mājas ir dziļa bedre. Lūdzu, salabojiet to.",
        "status": "RECEIVED",
        "receivedAt": "2026-10-01T09:15:00+00:00",
        "dueDate": "2026-11-02",
        "replyChannel": "EMAIL",
        "reasonCode": None,
        "department": "UTILITIES",
    },
    {
        "personalCode": "32000000102",
        "fullName": "Līga Testiņa-Izdomātā",
        "email": "liga.testina@example.com",
        "preferredChannel": "POST",
        "topic": "PLANNING",
        "subject": "Bojāta uzbrauktuve pie bibliotēkas",
        "body": (
            "Es pārvietojos ratiņkrēslā, un uzbrauktuve pie bibliotēkas ir bojāta. "
            "Lūdzu, salabojiet to."
        ),
        "status": "IN_PROGRESS",
        "receivedAt": "2026-08-20T10:00:00+00:00",
        "dueDate": "2026-09-21",
        "replyChannel": "POST",
        "reasonCode": None,
        "department": "BUILDING",
    },
    {
        "personalCode": "32000000103",
        "fullName": "Ņikita Ezermalnieks",
        "email": "nikita.ezermalnieks@example.com",
        "preferredChannel": "E_ADDRESS",
        "topic": "WASTE",
        "subject": "Atkritumu konteiners netiek iztukšots",
        "body": "Konteiners Liepu ielā 3 nav iztukšots divas nedēļas.",
        "status": "ANSWERED",
        "receivedAt": "2026-09-01T08:30:00+00:00",
        "dueDate": "2026-10-01",
        "replyChannel": "E_ADDRESS",
        "reasonCode": None,
        "department": "UTILITIES",
    },
)

_INSERT = f"""
    INSERT INTO submissions (seq, {", ".join(COLUMNS)})
    VALUES (?, {", ".join("?" for _ in COLUMNS)})
"""


class ServiceUnavailable(Exception):
    """Datubāze nav pieejama: serveris nedarbojas vai fails ir bojāts."""


_lock = threading.Lock()
_memory: sqlite3.Connection | None = None


def use_system() -> None:
    """Glabātuve izmanto aktīvā servera datubāzi (mācību sistēmu)."""
    global _memory
    with _lock:
        _memory = None


def reset(seed: bool = True) -> None:
    """Testiem: tukša datubāze atmiņā, pēc izvēles ar trim sintētiskiem iesniegumiem."""
    global _memory
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    with _lock:
        _memory = conn
    if seed:
        for record in SEED:
            add(record)


@contextmanager
def _connection():
    with _lock:
        if _memory is not None:
            yield _memory
            _memory.commit()
            return
        try:
            path = runtime.active_db_path()
        except runtime.Unavailable as exc:
            raise ServiceUnavailable(str(exc)) from exc
        conn = sqlite3.connect(f"file:{path}?mode=rw", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.DatabaseError as exc:
            raise ServiceUnavailable("datubāze nav nolasāma") from exc
        finally:
            conn.close()


def insert_rows(conn: sqlite3.Connection, records) -> None:
    """Ieraksti ar zināmu kārtas numuru (seq). Izmanto arī datu ģenerators."""
    conn.executemany(
        _INSERT,
        [[r["seq"], *(r.get(column) for column in COLUMNS)] for r in records],
    )


def add(data: dict) -> dict:
    with _connection() as conn:
        (seq,) = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM submissions"
        ).fetchone()
        record = {**data, "id": f"IES-2026-{seq:06d}", "seq": seq}
        insert_rows(conn, [record])
    record.pop("seq")
    return record


def list_submissions(status: str | None = None, topic: str | None = None) -> list:
    # Parametrizēts vaicājums: ievade nekad nekļūst par SQL daļu.
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM submissions
            WHERE (:status IS NULL OR status = :status)
              AND (:topic IS NULL OR topic = :topic)
            ORDER BY seq
            """,
            {"status": status, "topic": topic},
        ).fetchall()
    return [{column: row[column] for column in COLUMNS} for row in rows]


def get(submission_id: str) -> dict | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
    if row is None:
        return None
    return {column: row[column] for column in COLUMNS}


def now() -> datetime:
    """Servisa pulkstenis. Mācību sistēmā tas ir apturēts tūlīt pēc katastrofas brīža."""
    if _memory is not None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    return clock.NOW + timedelta(minutes=1)


def count() -> int:
    """Veselības pārbaudei: vai datubāzi var nolasīt."""
    with _connection() as conn:
        (total,) = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()
    return total
