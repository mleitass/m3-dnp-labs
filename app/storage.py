"""Iesniegumu glabātuve: SQLite datubāze atmiņā.

Pēc restarta dati atgriežas sākuma stāvoklī ar trim sintētiskiem iesniegumiem.
"""

import sqlite3
import threading

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
)

# Sintētiski dati. Personas kodi neatbilst reālām personām.
SEED = (
    {
        "personalCode": "32000000101",
        "fullName": "Jānis Bērziņš",
        "email": "janis.berzins@example.com",
        "preferredChannel": "EMAIL",
        "topic": "ROADS",
        "subject": "Bedre Ezera ielā",
        "body": "Ezera ielā pie 12. mājas ir dziļa bedre. Lūdzu, salabojiet to.",
        "status": "RECEIVED",
        "receivedAt": "2026-10-01T09:15:00+00:00",
        "dueDate": "2026-11-02",
        "replyChannel": "EMAIL",
        "reasonCode": None,
    },
    {
        "personalCode": "32000000102",
        "fullName": "Līga Ozoliņa-Kalniņa",
        "email": "liga.ozolina@example.com",
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
    },
    {
        "personalCode": "32000000103",
        "fullName": "Ņikita Šķēle",
        "email": "nikita.skele@example.com",
        "preferredChannel": "E_ADDRESS",
        "topic": "WASTE",
        "subject": "Atkritumu konteiners netiek iztukšots",
        "body": "Konteiners Liepu ielā 3 nav iztukšots divas nedēļas.",
        "status": "ANSWERED",
        "receivedAt": "2026-09-01T08:30:00+00:00",
        "dueDate": "2026-10-01",
        "replyChannel": "E_ADDRESS",
        "reasonCode": None,
    },
)

_INSERT = """
    INSERT INTO submissions (
        id, personalCode, fullName, email, preferredChannel, topic, subject, body,
        status, receivedAt, dueDate, replyChannel, reasonCode
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE submissions (
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
            reasonCode TEXT
        )
        """
    )
    return conn


def reset(seed: bool = True) -> None:
    global _conn
    with _lock:
        _conn = _connect()
    if seed:
        for record in SEED:
            add(record)


def add(data: dict) -> dict:
    with _lock:
        (seq,) = _conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM submissions"
        ).fetchone()
        record = {**data, "id": f"IES-2026-{seq:06d}"}
        _conn.execute(_INSERT, [record.get(column) for column in COLUMNS])
    return record


def list_submissions(status: str | None = None, topic: str | None = None) -> list:
    # Parametrizēts vaicājums: ievade nekad nekļūst par SQL daļu.
    with _lock:
        rows = _conn.execute(
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
    with _lock:
        row = _conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
    if row is None:
        return None
    return {column: row[column] for column in COLUMNS}
