"""Rezerves kopijas NAS serverī: vēsture, kontrolsummas, žurnāls, tvērums.

Kopēšanas darbs notiek katru nakti 02:00. Glabā vienu kopiju katram dziļumam
(MK 397 70. punkts): iepriekšējā diena, ap nedēļu, ap mēnesi, ap gadu.
Nedēļas kopija tiek nosūtīta arī ārpus vietnes. Pirmdienas 02:00 darbs
neizdevās, un paziņojums netika nosūtīts.

Tvērums (kas ir kopijā) ir scenārija iestatījums: datubāze, pielikumi,
triāžas konfigurācija.
"""

import gzip
import hashlib
import io
import json
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from drill import clock, paths, seed, triage_versions
from drill.clock import TZ

SCOPE_FULL = ("db", "attachments", "triage")
SCOPE_LABELS = {
    "db": "db/iesniegumi.db",
    "attachments": "pielikumi/",
    "triage": "triage/",
}


@dataclass(frozen=True)
class Plan:
    id: str
    created_at: datetime
    db_gb: int
    attachments_gb: int
    offsite: bool = False


HISTORY = (
    Plan("B-20261018-0200", datetime(2026, 10, 18, 2, 0, tzinfo=TZ), 30, 169),
    Plan("B-20261012-0200", datetime(2026, 10, 12, 2, 0, tzinfo=TZ), 29, 162, True),
    Plan("B-20260919-0200", datetime(2026, 9, 19, 2, 0, tzinfo=TZ), 27, 151),
    Plan("B-20251019-0200", datetime(2025, 10, 19, 2, 0, tzinfo=TZ), 21, 118),
)
FAILED_RUN = datetime(2026, 10, 19, 2, 0, tzinfo=TZ)
FAILED_REASON = "mērķa diskā nav vietas (paziņojums netika nosūtīts)"
CATALOG = "katalogs.json"
LOG = "kopesanas-zurnals.log"
JOB = "kopesanas-darbs.conf"


class BackupError(Exception):
    pass


def archive_path(backup_id: str) -> Path:
    return paths.nas_dir() / f"{backup_id}.tar.gz"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _add_bytes(
    archive: tarfile.TarFile, name: str, content: bytes, mtime: float
) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mtime = mtime
    info.mode = 0o644
    archive.addfile(info, io.BytesIO(content))


def _write_archive(plan: Plan, scope: tuple[str, ...]) -> Path:
    records = seed.records_until(plan.created_at)
    target = archive_path(plan.id)
    mtime = plan.created_at.timestamp()
    with tempfile.TemporaryDirectory() as tmp:
        db_file = Path(tmp) / "iesniegumi.db"
        seed.write_database(db_file, records, snapshot_at=plan.created_at)
        with (
            target.open("wb") as raw,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=int(mtime), compresslevel=1
            ) as packed,
            tarfile.open(fileobj=packed, mode="w") as archive,
        ):
            _add_bytes(archive, "db/iesniegumi.db", db_file.read_bytes(), mtime)
            if "attachments" in scope:
                for name, content in seed.attachment_files(records):
                    _add_bytes(archive, f"pielikumi/{name}", content, mtime)
            version = triage_versions.version_at(plan.created_at)
            if "triage" in scope and version:  # pirms ieviešanas triāžas nav
                for name, content in triage_versions.files(version).items():
                    _add_bytes(
                        archive, f"triage/{name}", content.encode("utf-8"), mtime
                    )
    return target


def build_history(scope: tuple[str, ...] = SCOPE_FULL) -> None:
    """Izveido visu kopiju vēsturi ar doto tvērumu, katalogu, žurnālu un darba iestatījumus."""
    nas = paths.nas_dir()
    nas.mkdir(parents=True, exist_ok=True)
    for old in nas.glob("*.tar.gz"):
        old.unlink()
    catalog, log = [], []
    for plan in sorted(HISTORY, key=lambda p: p.created_at):
        path = _write_archive(plan, scope)
        digest = sha256_file(path)
        size_gb = plan.db_gb + (plan.attachments_gb if "attachments" in scope else 0)
        catalog.append(
            {
                "id": plan.id,
                "created_at": plan.created_at.isoformat(),
                "sha256": digest,
                "size_gb": size_gb,
                "offsite": plan.offsite,
            }
        )
        note = "  nedēļas kopija nosūtīta arī ārpus vietnes" if plan.offsite else ""
        log.append(
            f"{plan.created_at:%Y-%m-%d %H:%M}  OK         {plan.id}  "
            f"{size_gb} GB  sha256={digest}{note}"
        )
    log.append(
        f"{FAILED_RUN:%Y-%m-%d %H:%M}  NEIZDEVĀS  darbs pārtraukts: {FAILED_REASON}"
    )
    (nas / CATALOG).write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    (nas / LOG).write_text("\n".join(log) + "\n", encoding="utf-8")
    included = "\n".join(
        f"  - {SCOPE_LABELS[part]}" for part in SCOPE_FULL if part in scope
    )
    (nas / JOB).write_text(
        "# Rezerves kopēšanas darbs. NAS serveru telpā, katru nakti 02:00.\n"
        "avots: galvenais-serveris\n"
        f"iekļaut:\n{included}\n"
        "glabāt: pēdējā diena, ap nedēļu, ap mēnesi, ap gadu\n"
        "ārpus vietnes: nedēļas kopija\n"
        "paziņojumi par kļūdām: nav konfigurēti\n",
        encoding="utf-8",
    )


def damage(backup_id: str) -> None:
    """Bojā arhīvu pēc tam, kad kontrolsumma ierakstīta (daļa faila zudusi)."""
    path = archive_path(backup_id)
    content = path.read_bytes()
    path.write_bytes(content[: int(len(content) * 0.6)])


def catalog() -> list[dict]:
    try:
        return json.loads((paths.nas_dir() / CATALOG).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def find(name: str) -> dict:
    """Kopija pēc ID (B-20261018-0200) vai vecuma (D-1, D-7, D-30, D-365)."""
    wanted = name.strip().upper()
    for entry in catalog():
        if wanted in (
            entry["id"].upper(),
            clock.day_offset(clock.parse(entry["created_at"])),
        ):
            return entry
    known = ", ".join(e["id"] for e in catalog())
    raise BackupError(f"Rezerves kopija '{name}' nav atrasta. Pieejamās: {known}")


def checksum_ok(entry: dict) -> bool:
    path = archive_path(entry["id"])
    return path.exists() and sha256_file(path) == entry["sha256"]


def list_lines() -> list[str]:
    entries = catalog()
    if not entries:
        return ["Rezerves kopiju katalogs nav atrasts. Palaidiet: make reset"]
    lines = [
        "Rezerves kopijas · NAS serveru telpā",
        "Kontrolsummas (SHA-256) pārbaudītas tagad.",
        "",
        "  ID                Izveidota                    Vecums  Izmērs  Kontrolsumma",
    ]
    for entry in sorted(entries, key=lambda e: e["created_at"], reverse=True):
        created = clock.parse(entry["created_at"])
        mark = "*" if entry["offsite"] else " "
        check = "atbilst" if checksum_ok(entry) else "NEATBILST"
        lines.append(
            f"  {entry['id']}{mark}  {clock.fmt_dt(created):<27}  "
            f"{clock.day_offset(created):<6}  {entry['size_gb']:>3} GB  {check}"
        )
    lines += ["  * nedēļas kopija ir arī ārpus vietnes", "", "Kopēšanas žurnāls:"]
    log = (paths.nas_dir() / LOG).read_text(encoding="utf-8").splitlines()
    for line in reversed(log):
        moment = datetime.strptime(line[:16], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        parts = line[16:].split()
        if parts[0] == "OK":
            lines.append(f"  {clock.fmt_dt(moment):<27}  OK         {parts[1]}")
        else:
            lines.append(f"  {clock.fmt_dt(moment):<27}  NEIZDEVĀS  {FAILED_REASON}")
    lines += [
        "",
        "Atjaunot: make restore BACKUP=<ID>  (vai BACKUP=D-1, D-7, D-30, D-365)",
    ]
    return lines
