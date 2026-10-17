"""Sintētisku datu ģenerators. Deterministisks: katrā datorā vienādi skaitļi.

Visi dati ir izdomāti. Personas kodi ir acīmredzami viltoti (3200000NNNN),
uzvārdi ir izdomāti, e-pasti ir example.com domēnā.

Iesniegumu skaits: parasti 300 nedēļā, apkures pabalsta pieteikšanās laikā
(no 12.10.2026) ap 1200 nedēļā, no tiem ap 70 % par apkures pabalstu.
Darba dienās vairāk nekā brīvdienās, darba laikā vairāk nekā naktī.
"""

import hashlib
import json
import random
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import mock_llm
from app import storage, triage
from drill import triage_versions
from drill.clock import NOW, TZ

SEED = 20261019
OPERATIVE_START = datetime(2026, 9, 14, tzinfo=TZ)  # darba datubāzē: 5 nedēļas
PEAK_START = datetime(2026, 10, 12, tzinfo=TZ)  # apkures pabalsta pieteikšanās sākums
HEATING_TOPIC_FROM = triage_versions.CURRENT_FROM  # tēma "Apkures pabalsts" portālā
YEAR_AGO_START = datetime(2025, 9, 15, tzinfo=TZ)
YEAR_AGO_END = datetime(2025, 10, 19, 2, 0, tzinfo=TZ)
WEEKLY_NORMAL = 300
WEEKLY_PEAK = 1200
WEEKLY_YEAR_AGO = 80
FIRST_SEQ = {2025: 6850, 2026: 9412}
REPLY_DAYS = 30

# Pirmdiena..svētdiena un stundas 00..23 (relatīvais svars).
DAY_WEIGHTS = (1.2, 1.15, 1.1, 1.05, 0.95, 0.45, 0.4)
HOUR_WEIGHTS = (
    0.05, 0.03, 0.02, 0.02, 0.03, 0.08, 0.25, 0.6, 1.2, 1.6, 1.7, 1.6,
    1.3, 1.4, 1.5, 1.4, 1.2, 0.9, 0.8, 0.7, 0.6, 0.45, 0.3, 0.12,
)  # fmt: skip

SHARES_NORMAL = {
    "heating": 0.04,
    "social": 0.10,
    "roads": 0.26,
    "waste": 0.18,
    "building": 0.14,
    "landscaping": 0.14,
    "chancery": 0.14,
}
HEATING_SHARE_PEAK = 0.70
CORRECT_TOPIC = {
    "heating": "HEATING_SUPPORT",
    "social": "OTHER",
    "roads": "ROADS",
    "waste": "WASTE",
    "building": "PLANNING",
    "landscaping": "PARKS",
    "chancery": "OTHER",
}
WRONG_TOPICS = ("ROADS", "WASTE", "PLANNING", "PARKS")

STREETS = ("Ezera", "Liepu", "Krasta", "Dārza", "Meža", "Niedru", "Kalna", "Upes")
TEMPLATES = {
    "heating": (
        ("Apkures pabalsts", "Lūdzu piešķirt apkures pabalstu 2026./2027. gada "
         "apkures sezonai. Mājsaimniecībā {n} personas."),
        ("Pieteikums apkures pabalstam", "Piesakos apkures pabalstam. Dzīvoju "
         "{ielaa} {nr}, mājā ir {apkure} apkure."),
        ("Iesniegums", "Vēlos pieteikties apkures atbalstam. Esmu pensionārs, "
         "dzīvoju viens."),
        ("Apkures pabalsta pieteikums", "Lūdzu pārskatīt manu pieteikumu, "
         "iesniedzu to {kad}."),
        ("Kompensācija par apkuri", "Lūdzu kompensēt apkures izdevumus, jo "
         "ģimenē ir {n} bērni."),
        ("Jautājums par apkures pabalstu", "Vai apkures pabalstu var saņemt arī "
         "par malku? Mājā ir krāsns apkure."),
        ("Apkures pabalsts pensionārei", "Mana māte ir pensionāre, lūdzu "
         "piešķirt viņai apkures pabalstu. Pielikumā pilnvara."),
        ("Atbalsts apkures izdevumiem", "Lūdzu apkures atbalstu, jo rēķins par "
         "{menesis} ir {summa} eiro."),
    ),
    "social": (
        ("Palīdzība vientuļam pensionāram", "Kaimiņienei {ielaa} {nr} "
         "nepieciešama aprūpe mājās."),
        ("Sociālā palīdzība", "Lūdzu izvērtēt, vai ģimenei pienākas "
         "maznodrošinātās ģimenes statuss."),
        ("Trūcīgas personas statuss", "Lūdzu pagarināt trūcīgas personas "
         "statusu. Pielikumā izziņa."),
        ("Aprūpe mājās", "Lūdzu piešķirt aprūpi mājās manam tēvam pēc operācijas."),
    ),
    "roads": (
        ("Bedre {ielaa}", "{Ielaa} pie {nr}. mājas ir dziļa bedre. Lūdzu, "
         "salabojiet to."),
        ("Ietve pilna ar lapām", "{Ielas} ietve pilna ar kritušām lapām, "
         "gājēji slīd."),
        ("Ielu apgaismojums", "{Ielaa} nedeg {n} laternas jau nedēļu."),
        ("Bojāts asfalts", "{Ielaa} pēc remonta asfalts atkal saplaisājis."),
        ("Ceļa zīme", "Krustojumā pie {ielas} nogāzta ceļa zīme."),
    ),
    "waste": (
        ("Atkritumu konteiners netiek iztukšots", "Konteiners {ielaa} {nr} nav "
         "iztukšots divas nedēļas."),
        ("Šķirošanas konteineri", "Lūdzu uzstādīt šķirošanas konteinerus pie "
         "{ielas} {nr}. mājas."),
        ("Nelegāli izmesti atkritumi", "Meža malā aiz {ielas} kāds izmetis "
         "atkritumus."),
    ),
    "building": (
        ("Būvatļauja šķūnim", "Vēlos uzbūvēt šķūni savā zemes vienībā. Vai "
         "vajag būvatļauju?"),
        ("Detālplānojums", "Lūdzu informāciju par detālplānojuma grozījumiem "
         "Ezermalas centrā."),
        ("Žogs pie kaimiņa", "Kaimiņš būvē žogu uz robežas bez saskaņošanas. "
         "Vai tam vajadzēja būvvaldes atļauju?"),
        ("Būvniecības iecere", "Kāds ir manas būvniecības ieceres statuss? "
         "Iesniedzu to {kad}."),
        ("Teritorijas plānojums", "Vai teritorijas plānojumā mana zemes vienība "
         "ir apbūves teritorija?"),
    ),
    "landscaping": (
        ("Soliņi parkā", "Ezermalas parkā salauzti {n} soliņi."),
        ("Nokaltis koks", "Skvērā pie bibliotēkas nokaltis koks, tas var uzkrist "
         "garāmgājējiem."),
        ("Rotaļu laukums", "Bērnu rotaļu laukumā {ielaa} ir bojātas šūpoles."),
        ("Zāliena pļaušana", "Skvērā pie {ielas} zālienu nav pļāvuši visu vasaru."),
        ("Puķu dobes", "Paldies par puķu dobēm parkā! Varbūt var iestādīt arī "
         "pie {ielas}?"),
    ),
    "chancery": (
        ("Pateicība", "Paldies klientu apkalpošanas centra darbiniecei par "
         "laipnu palīdzību."),
        ("Dokumentu kopija", "Lūdzu izsniegt man iepriekš iesniegtā iesnieguma "
         "kopiju."),
        ("Jautājums", "Kāds ir pašvaldības darba laiks svētku dienās?"),
        ("Izziņa", "Lūdzu izsniegt izziņu par deklarēto dzīvesvietu."),
        ("Sūdzība par darbinieku", "Zvanot uz informatīvo tālruni, neviens "
         "neatbildēja visu dienu."),
    ),
}  # fmt: skip
ATTACHMENTS = {
    "heating": (0.6, ("izzina-par-ienakumiem.pdf", "pilnvara.pdf")),
    "social": (0.3, ("izzina.pdf",)),
    "roads": (0.5, ("foto-1.jpg", "foto-2.jpg")),
    "waste": (0.35, ("foto-1.jpg",)),
    "building": (0.6, ("skice.pdf", "zemes-robezu-plans.pdf")),
    "landscaping": (0.4, ("foto-1.jpg",)),
    "chancery": (0.1, ("dokuments.pdf",)),
}

FIRST_NAMES = (
    ("Jānis", "m"), ("Andris", "m"), ("Pēteris", "m"), ("Edgars", "m"),
    ("Kārlis", "m"), ("Roberts", "m"), ("Valdis", "m"), ("Oskars", "m"),
    ("Anna", "f"), ("Līga", "f"), ("Ilze", "f"), ("Inese", "f"),
    ("Laura", "f"), ("Dace", "f"), ("Evija", "f"), ("Zane", "f"),
)  # fmt: skip
SURNAMES = (
    ("Paraudziņš", "Paraudziņa"),
    ("Testiņš", "Testiņa"),
    ("Izdomātais", "Izdomātā"),
    ("Ezermalnieks", "Ezermalniece"),
    ("Parauglauks", "Parauglauka"),
    ("Simulāns", "Simulāne"),
)
PERSON_COUNT = 1600
HASH_FIELDS = (
    "id", "personalCode", "fullName", "email", "topic",
    "subject", "body", "receivedAt", "dueDate",
)  # fmt: skip


@dataclass
class Record:
    seq: int
    row: dict
    attachments: list = field(default_factory=list)  # (fails, izmērs, sha256)

    @property
    def id(self) -> str:
        return self.row["id"]

    @property
    def received_at(self) -> datetime:
        return datetime.fromisoformat(self.row["receivedAt"])


def content_hash(row: dict) -> str:
    joined = "\x1f".join(str(row.get(name)) for name in HASH_FIELDS)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def attachment_bytes(submission_id: str, filename: str, size: int) -> bytes:
    rng = random.Random(f"{submission_id}/{filename}")
    header = (
        b"\xff\xd8\xff\xe0"
        if filename.endswith(".jpg")
        else (b"%PDF-1.4\n% Sintetisks pielikums macibam\n")
    )
    return header + rng.randbytes(size - len(header))


def _persons() -> list[tuple[str, str, str]]:
    rng = random.Random(SEED + 1)
    persons = []
    for number in range(PERSON_COUNT):
        first, gender = rng.choice(FIRST_NAMES)
        surname = rng.choice(SURNAMES)[0 if gender == "m" else 1]
        code = f"3200000{1000 + number:04d}"
        persons.append(
            (code, f"{first} {surname}", f"iedzivotajs{1000 + number}@example.com")
        )
    return persons


@lru_cache(maxsize=4)
def triage_config(version: str) -> triage.TriageConfig:
    files = triage_versions.files(version)
    return triage.TriageConfig(
        prompt=files["prompt.txt"],
        departments=json.loads(files["routing.json"])["departments"],
        settings=json.loads(files["config.json"]),
    )


def _route(subject: str, body: str, moment: datetime) -> str | None:
    version = triage_versions.version_at(moment)
    if version is None:  # pirms triāžas ieviešanas nodaļu triāža nenoteica
        return None
    config = triage_config(version)
    return mock_llm.classify(triage.build_prompt(config), f"{subject}\n{body}")


def _shares(moment: datetime) -> dict:
    if moment < PEAK_START or moment.year < 2026:
        return SHARES_NORMAL
    rest = 1 - SHARES_NORMAL["heating"]
    shares = {
        key: value * (1 - HEATING_SHARE_PEAK) / rest
        for key, value in SHARES_NORMAL.items()
        if key != "heating"
    }
    return {"heating": HEATING_SHARE_PEAK, **shares}


def _weekly(moment: datetime) -> float:
    if moment.year < 2026:
        return WEEKLY_YEAR_AGO
    return WEEKLY_PEAK if moment >= PEAK_START else WEEKLY_NORMAL


def _timestamps(start: datetime, end: datetime, rng: random.Random) -> list[datetime]:
    """Laika zīmogi pa stundām: sagaidāmais skaits pēc dienas un stundas svara."""
    day_total, hour_total = sum(DAY_WEIGHTS), sum(HOUR_WEIGHTS)
    stamps, carry, moment = [], 0.0, start
    while moment < end:
        hour_end = min(moment + timedelta(hours=1), end)
        share = (hour_end - moment) / timedelta(hours=1)
        carry += (
            _weekly(moment)
            * DAY_WEIGHTS[moment.weekday()]
            / day_total
            * HOUR_WEIGHTS[moment.hour]
            / hour_total
            * share
        )
        count = int(carry)
        carry -= count
        span = int((hour_end - moment).total_seconds())
        offsets = sorted(rng.randrange(span) for _ in range(count))
        stamps.extend(moment + timedelta(seconds=s) for s in offsets)
        moment = hour_end
    return stamps


def _status(moment: datetime, rng: random.Random) -> str:
    age = (NOW - moment).days
    if age < 2:
        return "RECEIVED"
    if age < 7:
        return rng.choice(("RECEIVED", "IN_PROGRESS"))
    if age < 14:
        return rng.choices(("IN_PROGRESS", "FORWARDED", "ANSWERED"), (5, 1, 4))[0]
    return rng.choices(("ANSWERED", "IN_PROGRESS", "WITHDRAWN"), (16, 3, 1))[0]


def _topic(category: str, moment: datetime, rng: random.Random) -> str:
    correct = CORRECT_TOPIC[category]
    if correct == "HEATING_SUPPORT":
        if moment < HEATING_TOPIC_FROM:
            return rng.choices(("OTHER", rng.choice(WRONG_TOPICS)), (85, 15))[0]
        return rng.choices(
            ("HEATING_SUPPORT", "OTHER", rng.choice(WRONG_TOPICS)), (55, 35, 10)
        )[0]
    return rng.choices((correct, "OTHER", rng.choice(WRONG_TOPICS)), (80, 15, 5))[0]


def _text(category: str, rng: random.Random) -> tuple[str, str]:
    subject, body = rng.choice(TEMPLATES[category])
    street = rng.choice(STREETS)
    values = {
        "ielaa": f"{street} ielā",
        "Ielaa": f"{street} ielā",
        "ielas": f"{street} ielas",
        "Ielas": f"{street} ielas",
        "nr": rng.randint(1, 48),
        "n": rng.randint(2, 5),
        "kad": rng.choice(("pagājušajā nedēļā", "pirms trim dienām", "pirmdien")),
        "apkure": rng.choice(("centrālā", "krāsns", "gāzes")),
        "menesis": rng.choice(("septembri", "oktobri")),
        "summa": rng.randint(85, 240),
    }
    return subject.format(**values), body.format(**values)


def _generate(start: datetime, end: datetime, year: int, rng: random.Random) -> list:
    persons = _persons()
    records = []
    for number, moment in enumerate(_timestamps(start, end, rng)):
        seq = FIRST_SEQ[year] + number
        shares = _shares(moment)
        category = rng.choices(list(shares), list(shares.values()))[0]
        subject, body = _text(category, rng)
        code, name, email = persons[rng.randrange(len(persons))]
        preferred = rng.choices(("EMAIL", "E_ADDRESS", "POST"), (60, 25, 15))[0]
        reply, reason = preferred, None
        if preferred == "E_ADDRESS" and rng.random() < 0.3:
            reply, reason = "EMAIL", "E_ADDRESS_NOT_ACTIVE"
        row = {
            "id": f"IES-{year}-{seq:06d}",
            "personalCode": code,
            "fullName": name,
            "email": email,
            "preferredChannel": preferred,
            "topic": _topic(category, moment, rng),
            "subject": subject,
            "body": body,
            "status": _status(moment, rng),
            "receivedAt": moment.isoformat(),
            "dueDate": (moment.date() + timedelta(days=REPLY_DAYS)).isoformat(),
            "replyChannel": reply,
            "reasonCode": reason,
            "department": _route(subject, body, moment),
        }
        record = Record(seq, row)
        chance, names = ATTACHMENTS[category]
        if rng.random() < chance:
            for filename in names[: rng.randint(1, len(names))]:
                size = rng.randint(300, 1500)
                digest = hashlib.sha256(
                    attachment_bytes(row["id"], filename, size)
                ).hexdigest()
                record.attachments.append((filename, size, digest))
        records.append(record)
    return records


@lru_cache(maxsize=1)
def dataset() -> tuple[list, list]:
    """(darba datubāze līdz katastrofai, ieraksti pirms gada D-365 kopijai)."""
    operative = _generate(OPERATIVE_START, NOW, 2026, random.Random(SEED))
    year_ago = _generate(YEAR_AGO_START, YEAR_AGO_END, 2025, random.Random(SEED + 2))
    return operative, year_ago


def records_until(moment: datetime) -> list:
    """Darba datubāzes saturs brīdī moment."""
    operative, year_ago = dataset()
    source = year_ago if moment.year < 2026 else operative
    return [r for r in source if r.received_at <= moment]


def write_database(
    path: Path, records: list, snapshot_at: datetime | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(storage.SCHEMA)
    storage.insert_rows(conn, [{**r.row, "seq": r.seq} for r in records])
    conn.executemany(
        "INSERT INTO attachments VALUES (?, ?, ?, ?)",
        [
            (r.id, name, size, digest)
            for r in records
            for name, size, digest in r.attachments
        ],
    )
    meta = {"system": 'Ezermalas novada pašvaldība · e-pakalpojums "Iesniegumi"'}
    if snapshot_at:
        meta["snapshot_at"] = snapshot_at.isoformat()
    conn.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
    conn.commit()
    conn.close()


def attachment_name(submission_id: str, filename: str) -> str:
    """Faila nosaukums pielikumu mapē: IES-2026-011835_foto-1.jpg."""
    return f"{submission_id}_{filename}"


def attachment_files(records: list):
    """(faila nosaukums mapē pielikumi/, saturs) katram pielikumam."""
    for record in records:
        for filename, size, _digest in record.attachments:
            yield (
                attachment_name(record.id, filename),
                attachment_bytes(record.id, filename, size),
            )


def write_server(
    server_dir: Path, records: list, triage_version: str | None,
    snapshot_at: datetime | None = None,
) -> None:  # fmt: skip
    """Servera disks: datubāze, pielikumi un triāžas konfigurācija (no tukšas mapes)."""
    if server_dir.exists():
        shutil.rmtree(server_dir)
    write_database(server_dir / "db" / "iesniegumi.db", records, snapshot_at)
    folder = server_dir / "pielikumi"
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in attachment_files(records):
        (folder / name).write_bytes(content)
    if triage_version:
        write_triage(server_dir / "triage", triage_version)


def write_triage(config_dir: Path, version: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    for name, content in triage_versions.files(version).items():
        (config_dir / name).write_text(content, encoding="utf-8")


def expected_state(records: list) -> dict:
    """Gaidītais stāvoklis katastrofas brīdī: tikai ID, laiki un kontrolsummas."""
    return {
        "disaster_at": NOW.isoformat(),
        "records": {r.id: [r.row["receivedAt"], content_hash(r.row)] for r in records},
        "attachments": {
            r.id: [[name, digest] for name, _size, digest in r.attachments]
            for r in records
            if r.attachments
        },
    }
