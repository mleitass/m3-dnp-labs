"""make verify: atjaunošanas rezultāts pret gaidīto stāvokli katastrofas brīdī.

Ziņo: atjaunotie un gaidītie iesniegumi, jaunākais atjaunotais ieraksts un datu
zuduma logs (izmērītais RPO), pielikumu integritāte, triāžas precizitāte
novērtēšanas kopā. Patērēto laiku neziņo: atjaunošanas laiku simulē ar kartītēm.
"""

import csv
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

import mock_llm
from drill import clock, evaluation, paths, runtime, seed, state
from drill.status import SERVER_NAMES, portal_check

RESTORED_FIELDS = ", ".join(seed.HASH_FIELDS)
MISSING_LIST = "trukstosie-pielikumi.csv"
LABEL_WIDTH = 28


@dataclass
class Findings:
    expected: int = 0
    readable: bool = False
    restored: int = 0
    corrupted: int = 0
    lost: list = field(default_factory=list)  # (laiks, ID) zaudētajiem
    extra_old: int = 0
    new_after: int = 0
    reused_ids: int = 0
    newest: tuple | None = None  # (ID, laiks) jaunākajam atjaunotajam pirms katastrofas
    attachments_expected: int = 0
    attachments_ok: int = 0
    attachments_missing: list = field(default_factory=list)
    attachments_damaged: int = 0


def _row(label: str, value) -> str:
    return f"  {label + ':':<{LABEL_WIDTH}}{value}"


def _count(number: int) -> str:
    return f"{clock.fmt_int(number):>6}"


def _expected() -> dict:
    return json.loads((paths.sim_dir() / "gaidits.json").read_text(encoding="utf-8"))


def _read_active() -> tuple[list, list] | None:
    try:
        path = runtime.active_db_path()
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(f"SELECT {RESTORED_FIELDS} FROM submissions").fetchall()
            files = conn.execute(
                "SELECT submission_id, filename, sha256 FROM attachments"
            ).fetchall()
        finally:
            conn.close()
    except (runtime.Unavailable, sqlite3.DatabaseError):
        return None
    return [dict(row) for row in rows], [tuple(f) for f in files]


def _check_attachments(findings: Findings, files: list, restored_ids: set) -> None:
    folder = paths.attachments_dir(runtime.active_server())
    for submission_id, filename, digest in files:
        if submission_id not in restored_ids:
            continue
        findings.attachments_expected += 1
        path = folder / seed.attachment_name(submission_id, filename)
        if not path.exists():
            findings.attachments_missing.append((submission_id, filename))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            findings.attachments_damaged += 1
        else:
            findings.attachments_ok += 1


def collect() -> Findings:
    expected = _expected()
    disaster_at = clock.parse(expected["disaster_at"])
    records = expected["records"]
    findings = Findings(expected=len(records))
    data = _read_active()
    seen = set()
    if data is not None:
        findings.readable = True
        rows, files = data
        for row in rows:
            received = clock.parse(row["receivedAt"])
            if received > disaster_at:
                # Jauni iesniegumi pēc atjaunošanas (portālā, make run).
                findings.new_after += 1
                findings.reused_ids += 1 if row["id"] in records else 0
                continue
            if row["id"] not in records:
                findings.extra_old += 1
                continue
            seen.add(row["id"])
            findings.restored += 1
            if seed.content_hash(row) != records[row["id"]][1]:
                findings.corrupted += 1
            if findings.newest is None or received > findings.newest[1]:
                findings.newest = (row["id"], received)
        _check_attachments(findings, files, seen)
    findings.lost = sorted(
        (clock.parse(received), record_id)
        for record_id, (received, _digest) in records.items()
        if record_id not in seen
    )
    return findings


def recovery_point(current: dict, findings: Findings) -> datetime | None:
    """Brīdis, līdz kuram dati ir atjaunoti (kopijas vai sinhronizācijas laiks)."""
    if not findings.lost:
        return None
    if current["active"] == "standby" and current.get("standby_synced_at"):
        return clock.parse(current["standby_synced_at"])
    if current.get("recovery_point"):
        return clock.parse(current["recovery_point"])
    return findings.newest[1] if findings.newest else None


def _write_missing_list(missing: list) -> str:
    folder = paths.report_dir()
    folder.mkdir(exist_ok=True)
    path = folder / MISSING_LIST
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["iesniegums", "pielikums"])
        writer.writerows(missing)
    return str(path.relative_to(paths.root().parent))


def _records_section(findings: Findings, summary: list) -> list[str]:
    lines = ["Iesniegumi", _row("Gaidīti katastrofas brīdī", _count(findings.expected))]
    if not findings.readable:
        summary.append(
            ("PROBLĒMA", "Datubāze nav pieejama: neviens iesniegums nav atjaunots")
        )
        return lines + [_row("Atjaunoti", "  nav (datubāze nav pieejama)")]
    lines += [
        _row("Atjaunoti", _count(findings.restored)),
        _row("Zaudēti", _count(len(findings.lost))),
        _row("Bojāti (saturs atšķiras)", _count(findings.corrupted)),
    ]
    if findings.extra_old:
        lines.append(
            _row("Nav gaidīto sarakstā", _count(findings.extra_old) + "  (vecāki dati)")
        )
    if findings.new_after:
        lines.append(_row("Jauni pēc katastrofas", _count(findings.new_after)))
    if findings.reused_ids:
        lines.append(
            f"  Uzmanību: jauniem iesniegumiem piešķirti zaudēto numuri: {findings.reused_ids}"
        )
    if findings.corrupted:
        summary.append(
            (
                "PROBLĒMA",
                f"Iesniegumi ar bojātu saturu: {clock.fmt_int(findings.corrupted)}",
            )
        )
    else:
        summary.append(("OK", "Atjaunoto iesniegumu saturs nav bojāts"))
    return lines


def _loss_section(current: dict, findings: Findings, summary: list) -> list[str]:
    lines = ["Datu zudums (izmērītais RPO)"]
    if not findings.readable:
        return lines + ["  Nav izmērāms: dati nav atjaunoti."]
    if not findings.lost:
        summary.append(("OK", "Nav zaudētu iesniegumu"))
        return lines + [_row("Datu zuduma logs", "0 min (nav zaudētu iesniegumu)")]
    point = recovery_point(current, findings)
    if point:
        lines.append(_row("Atjaunošanas punkts", clock.fmt_dt(point)))
    if findings.newest:
        newest_id, newest_at = findings.newest
        lines.append(
            _row("Jaunākais atjaunotais", f"{newest_id}, {clock.fmt_dt(newest_at)}")
        )
    first, last = findings.lost[0][0], findings.lost[-1][0]
    lines.append(
        _row("Zaudētie saņemti", f"{clock.fmt_dt(first)} – {clock.fmt_dt(last)}")
    )
    window = clock.fmt_duration(clock.NOW - (point or findings.newest[1]))
    lines.append(_row("Datu zuduma logs", window))
    summary.append(
        ("PROBLĒMA", f"Zaudētie iesniegumi: {clock.fmt_int(len(findings.lost))}; "
         f"datu zuduma logs {window}")
    )  # fmt: skip
    return lines


def _attachments_section(findings: Findings, summary: list) -> list[str]:
    lines = ["Pielikumi"]
    if not findings.readable:
        return lines + ["  Nav pārbaudāmi: datubāze nav pieejama."]
    lines += [
        _row("Atjaunotajiem iesniegumiem", _count(findings.attachments_expected)),
        _row("Atrasti un nebojāti", _count(findings.attachments_ok)),
        _row("Trūkst", _count(len(findings.attachments_missing))),
        _row("Bojāti", _count(findings.attachments_damaged)),
    ]
    if findings.attachments_missing:
        lines.append(
            _row(
                "Trūkstošo saraksts", _write_missing_list(findings.attachments_missing)
            )
        )
        summary.append(
            (
                "PROBLĒMA",
                f"Trūkstošie pielikumi: {clock.fmt_int(len(findings.attachments_missing))}",
            )
        )
    elif findings.attachments_damaged:
        summary.append(
            ("PROBLĒMA", f"Bojātie pielikumi: {findings.attachments_damaged}")
        )
    else:
        summary.append(("OK", "Pielikumi vietā, kontrolsummas atbilst"))
    return lines


def _model_text(config) -> str:
    try:
        return f"{config.model} ({mock_llm.resolve_model(config.model, runtime.llm_mode())})"
    except mock_llm.ProviderError:
        return f"{config.model} (nav atrasts)"


def _triage_section(current: dict, summary: list) -> list[str]:
    from app import triage

    lines = ["Triāža (MI sadale pa nodaļām)"]
    if runtime.triage_config_dir() is None:
        summary.append(("PROBLĒMA", "Triāža nedarbojas"))
        return lines + ["  Nav pārbaudāma: serviss nedarbojas."]
    config = triage.active_config()
    result = evaluation.evaluate(config)
    manual = current.get("triage_mode") == "manual"
    score = (
        f"{result.correct}/{result.total} pareizi ({result.percent} %), "
        f"slieksnis {result.threshold}/{result.total}"
    )
    lines += [
        _row(
            "Režīms",
            "manuāla sadale: visi jaunie → Kanceleja"
            if manual
            else "automātiska sadale",
        ),
        _row("Modelis", _model_text(config)),
        _row("Automātiskās sadales tests" if manual else "Novērtēšanas kopa", score),
    ]
    if result.errors:
        lines.append(
            _row("MI pakalpojums neatbildēja", f"{result.errors} no {result.total}")
        )
    department, count = result.destinations.most_common(1)[0]
    if count >= 0.75 * result.total and not result.passed:
        name = triage.DEPARTMENT_NAMES.get(department, department)
        lines.append(f"  Uzmanību: {count} no {result.total} nosūtīti uz: {name}")
    if manual:
        summary.append(
            ("PIEZĪME", "Triāža manuālā režīmā: jaunos iesniegumus sadala Kanceleja")
        )
    elif result.passed:
        summary.append(
            ("OK", f"Triāža sadala pareizi ({result.correct}/{result.total})")
        )
    else:
        summary.append(
            ("PROBLĒMA", f"Triāža zem sliekšņa ({result.correct}/{result.total})")
        )
    return lines


def run() -> list[str]:
    current = state.load()
    if not current:
        return ["Mācību sistēma vēl nav izveidota. Palaidiet: make reset"]
    findings = collect()
    portal = portal_check()
    server = SERVER_NAMES[current["active"]]
    if current["active"] == "primary" and current.get("restored_from"):
        server += f" (atjaunots no {current['restored_from']})"
    summary = [("OK" if portal == "darbojas" else "PROBLĒMA", f"Portāls: {portal}")]
    lines = [
        'Pārbaude · Ezermalas e-pakalpojums "Iesniegumi"',
        _row("Katastrofas brīdis", clock.fmt_dt(clock.NOW)),
        _row("Aktīvais serveris", server),
        "",
        *_records_section(findings, summary),
        "",
        *_loss_section(current, findings, summary),
        "",
        *_attachments_section(findings, summary),
        "",
        *_triage_section(current, summary),
        "",
        "Kopsavilkums",
        *(f"  {mark:<9} {text}" for mark, text in summary),
    ]
    if findings.lost and findings.readable:
        lines += ["", "Izmērīto datu zuduma logu salīdziniet ar sava plāna RPO mērķi."]
    state.log_action("verify")
    return lines
