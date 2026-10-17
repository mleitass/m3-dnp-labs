"""Atjaunošanas darbības: make restore, make failover, make triage, make triage-config."""

import shutil
import tarfile
import tempfile
from pathlib import Path

from drill import backups, clock, evaluation, paths, seed, state, triage_versions

SERVER_FOLDERS = ("db", "pielikumi", "triage")


class RecoveryError(Exception):
    pass


def _keep_previous(target: Path) -> Path | None:
    """Iepriekšējo servera stāvokli saglabā izpētei. Neko nedzēš."""
    if not target.exists():
        return None
    kept_root = paths.root() / "saglabats"
    kept_root.mkdir(exist_ok=True)
    number = len(list(kept_root.iterdir())) + 1
    kept = kept_root / f"{target.name}-{number}"
    shutil.move(str(target), str(kept))
    return kept


def restore(name: str) -> list[str]:
    if not name.strip():
        raise RecoveryError(
            "Norādiet kopiju: make restore BACKUP=B-20261018-0200 (saraksts: make backup-list)"
        )
    try:
        entry = backups.find(name)
    except backups.BackupError as exc:
        raise RecoveryError(str(exc)) from exc
    archive = backups.archive_path(entry["id"])
    if not archive.exists():
        raise RecoveryError(f"Kopijas fails {archive.name} NAS serverī nav atrasts.")
    current = state.load()
    with tempfile.TemporaryDirectory(dir=paths.root()) as tmp:
        unpacked = Path(tmp) / "serveris"
        try:
            with tarfile.open(archive) as packed:
                packed.extractall(unpacked, filter="data")
        except Exception:  # bojāts vai nepilnīgs arhīvs: jebkura atpakošanas kļūda
            raise RecoveryError(
                f"Atjaunošana neizdevās: kopiju {entry['id']} nevar atpakot "
                "(fails ir bojāts vai nepilnīgs).\nGalvenā servera stāvoklis nav mainīts."
            ) from None
        if not (unpacked / "db" / "iesniegumi.db").exists():
            raise RecoveryError(
                f"Atjaunošana neizdevās: kopijā {entry['id']} nav datubāzes."
            )
        for folder in SERVER_FOLDERS:
            (unpacked / folder).mkdir(exist_ok=True)
        target = paths.server_dir("primary")
        _keep_previous(target)
        shutil.move(str(unpacked), str(target))
    was_standby = current["active"] == "standby"
    current["servers"]["primary"] = state.SERVER_UP
    current["active"] = "primary"
    current["restored_from"] = entry["id"]
    current["recovery_point"] = entry["created_at"]
    state.save(current)
    state.log_action(f"restore {entry['id']}")
    lines = [
        f"Atjaunots no {entry['id']} ({clock.fmt_dt(entry['created_at'])}) uz galveno serveri.",
        "Galvenais serveris darbojas, serviss palaists.",
    ]
    if was_standby:
        lines.append(
            "Serviss pārslēgts atpakaļ no rezerves servera uz galveno serveri."
        )
    return lines + ["Pārbaudiet rezultātu: make verify"]


def failover() -> list[str]:
    current = state.load()
    if current["active"] == "standby":
        return ["Serviss jau darbojas uz rezerves servera."]
    if current["servers"].get("standby") != state.SERVER_UP:
        raise RecoveryError(
            "Pārslēgšana neizdevās: rezerves serveris nedarbojas (datu krātuve nav pieejama)."
        )
    current["active"] = "standby"
    current["recovery_point"] = current["standby_synced_at"]
    state.save(current)
    state.log_action("failover")
    return [
        f"Pārslēgts uz rezerves serveri (dati sinhronizēti "
        f"{clock.fmt_dt(current['standby_synced_at'])}).",
        "Rezerves serveris darbojas un apkalpo portālu.",
        "Pārbaudiet rezultātu: make verify",
    ]


def _active_triage_dir() -> Path:
    current = state.load()
    server = current["active"]
    if current["servers"].get(server) != state.SERVER_UP:
        raise RecoveryError(
            "Aktīvais serveris nedarbojas. Vispirms atjaunojiet servisu."
        )
    return paths.triage_dir(server)


def _evaluation_line() -> str:
    from app import triage

    result = evaluation.evaluate(triage.active_config())
    return (
        f"Automātiskās sadales tests: {result.correct}/{result.total} pareizi "
        f"({result.percent} %), slieksnis {result.threshold}/{result.total}."
    )


def set_triage_mode(mode: str) -> list[str]:
    if mode not in ("manual", "auto"):
        raise RecoveryError("Norādiet režīmu: make triage MODE=manual vai MODE=auto")
    _active_triage_dir()
    current = state.load()
    current["triage_mode"] = mode
    state.save(current)
    state.log_action(f"triage {mode}")
    if mode == "manual":
        head = (
            "Triāža pārslēgta uz manuālu sadali: visi jaunie iesniegumi nonāk "
            "Kancelejā, un tos sadala darbinieki."
        )
    else:
        head = "Triāža pārslēgta uz automātisku sadali (MI)."
    return [head, _evaluation_line()]


def vendor_triage_config() -> list[str]:
    """SIA "Ezerdati" atsūta konfigurāciju no ieviešanas nodošanas paketes (2026-04)."""
    config_dir = _active_triage_dir()
    present = [name for name in triage_versions.files(triage_versions.VENDOR)
               if (config_dir / name).exists()]  # fmt: skip
    if len(present) == 3:
        return ["Triāžas konfigurācija serverī jau ir. Nekas nav mainīts."]
    seed.write_triage(config_dir, triage_versions.VENDOR)
    state.log_action("triage-config (piegādātāja kopija 2026-04)")
    return [
        'SIA "Ezerdati" atsūtīja triāžas konfigurācijas kopiju no 2026. gada aprīļa',
        "nodošanas dokumentācijas. Uzstādīts serverī: prompt.txt, routing.json, config.json.",
        "Īstenībā tas nozīmē sazināties ar piegādātāju (skatiet ilguma kartīti).",
        "Pirms paļaujaties uz automātisko sadali, pārbaudiet: make verify",
    ]
