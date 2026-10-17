"""R-08: make restore, make failover, make verify katram scenārijam.

Katram scenārijam: slazda ceļš un pareizais ceļš ar gaidīto datu zuduma logu.
Pārbaude nekad neziņo patērēto laiku (D17).
"""

import re

import pytest

from drill import paths, state
from tests.drill_helpers import run


def _has(out, label, value):
    """Rindiņa 'Etiķete:   vērtība' ar jebkādu atstarpju skaitu."""
    return re.search(re.escape(label) + r":\s+" + re.escape(value), out) is not None


def _verify(capsys):
    code, out = run(capsys, "verify")
    assert code == 0
    return out


def _start(capsys, group):
    code, _out = run(capsys, "katastrofa", "--group", str(group))
    assert code == 0


def test_clean_state_has_no_loss(sistema, capsys):
    out = _verify(capsys)
    assert _has(out, "Zaudēti", "0\n")
    assert _has(out, "Datu zuduma logs", "0 min")
    assert "PROBLĒMA" not in out


# --- G1: loģisks bojājums, slazds: rezerves serveris ---


def test_g1_trap_failover_looks_fine_but_standby_is_corrupt(sistema, capsys):
    _start(capsys, 1)
    code, out = run(capsys, "failover")
    assert code == 0
    assert "Pārslēgts uz rezerves serveri" in out
    assert "bojā" not in out
    out = _verify(capsys)
    assert _has(out, "Aktīvais serveris", "rezerves serveris")
    assert _has(out, "Bojāti (saturs atšķiras)", "2 417")
    assert _has(out, "Datu zuduma logs", "10 min")
    assert "PROBLĒMA  Iesniegumi ar bojātu saturu: 2 417" in out
    assert "PROBLĒMA  Portāls: KĻŪDA" in out


def test_g1_correct_restore_from_d1(sistema, capsys):
    _start(capsys, 1)
    run(capsys, "failover")
    code, out = run(capsys, "restore", "--backup", "D-1")
    assert code == 0
    assert "pārslēgts atpakaļ" in out
    out = _verify(capsys)
    assert _has(out, "Zaudēti", "100")
    assert _has(out, "Bojāti (saturs atšķiras)", "0")
    assert _has(out, "Atjaunošanas punkts", "svētdiena 18.10.2026 02:00")
    assert _has(out, "Datu zuduma logs", "30 h 40 min")
    assert "OK        Portāls: darbojas" in out
    # Bojātais galvenā servera stāvoklis saglabāts izpētei, nevis izdzēsts.
    assert (paths.root() / "saglabats" / "galvenais-serveris-1" / "db").exists()


def test_g1_replicate_after_restore_repairs_standby(sistema, capsys):
    _start(capsys, 1)
    run(capsys, "restore", "--backup", "D-1")
    run(capsys, "replicate")
    run(capsys, "failover")
    out = _verify(capsys)
    assert _has(out, "Bojāti (saturs atšķiras)", "0")


# --- G2: datu krātuves zudums, slazds: bojāta jaunākā kopija ---


def test_g2_failover_is_not_possible(sistema, capsys):
    _start(capsys, 2)
    code, out = run(capsys, "failover")
    assert code == 1
    assert "rezerves serveris nedarbojas" in out


def test_g2_trap_latest_backup_cannot_be_restored(sistema, capsys):
    _start(capsys, 2)
    code, out = run(capsys, "restore", "--backup", "B-20261018-0200")
    assert code == 1
    assert "nevar atpakot" in out
    assert "nav mainīts" in out
    out = _verify(capsys)
    assert "datubāze nav pieejama" in out
    assert "PROBLĒMA  Portāls: NEDARBOJAS" in out


def test_g2_correct_restore_from_d7(sistema, capsys):
    _start(capsys, 2)
    run(capsys, "restore", "--backup", "D-1")
    code, _out = run(capsys, "restore", "--backup", "D-7")
    assert code == 0
    out = _verify(capsys)
    assert _has(out, "Zaudēti", "1 223")
    assert _has(out, "Atjaunošanas punkts", "pirmdiena 12.10.2026 02:00")
    assert _has(out, "Datu zuduma logs", "174 h 40 min (7 d 6 h 40 min)")
    assert _has(out, "Trūkst", "0")


# --- G3: datu krātuves zudums, slazds: pielikumi ārpus tvēruma ---


def test_g3_restore_looks_successful_but_attachments_are_missing(sistema, capsys):
    _start(capsys, 3)
    code, out = run(capsys, "restore", "--backup", "D-1")
    assert code == 0
    assert "pielikum" not in out.lower()
    _code, status = run(capsys, "status")
    assert "Portāls:             darbojas" in status
    assert "pielikum" not in status.lower()
    out = _verify(capsys)
    assert _has(out, "Datu zuduma logs", "30 h 40 min")
    assert _has(out, "Trūkst", "1 532")
    assert "PROBLĒMA  Trūkstošie pielikumi: 1 532" in out
    listed = (paths.report_dir() / "trukstosie-pielikumi.csv").read_text(
        encoding="utf-8"
    )
    assert listed.count("\n") == 1533


# --- G4: datu krātuves zudums, slazds: triāžas konfigurācija ārpus tvēruma ---


def test_g4_restore_works_but_routing_breaks(sistema, capsys):
    _start(capsys, 4)
    run(capsys, "restore", "--backup", "D-1")
    _code, status = run(capsys, "status")
    assert "Triāžas pašpārbaude: atbild" in status
    out = _verify(capsys)
    assert _has(out, "Novērtēšanas kopa", "2/20 pareizi (10 %)")
    assert "20 no 20 nosūtīti uz: Kanceleja" in out
    assert "PROBLĒMA  Triāža zem sliekšņa (2/20)" in out
    assert "OK        Pielikumi vietā" in out


def test_g4_manual_mode_then_vendor_copy(sistema, capsys):
    _start(capsys, 4)
    run(capsys, "restore", "--backup", "D-1")
    code, out = run(capsys, "triage", "--mode", "manual")
    assert code == 0
    assert "Kancelejā" in out
    out = _verify(capsys)
    assert "PIEZĪME   Triāža manuālā režīmā" in out
    code, out = run(capsys, "triage-config")
    assert code == 0
    assert "2026. gada aprīļa" in out
    out = _verify(capsys)
    assert _has(out, "Automātiskās sadales tests", "14/20 pareizi (70 %)")
    code, out = run(capsys, "triage-config")
    assert "jau ir" in out


def test_triage_mode_needs_a_valid_value(sistema, capsys):
    code, out = run(capsys, "triage", "--mode", "x")
    assert code == 1
    assert "MODE=manual" in out


# --- Kopīgi ---


def test_restore_needs_backup_name(sistema, capsys):
    code, out = run(capsys, "restore", "--backup", "")
    assert code == 1
    assert "make restore BACKUP=" in out


def test_restore_of_year_old_backup_reports_old_data(sistema, capsys):
    _start(capsys, 2)
    run(capsys, "restore", "--backup", "D-365")
    out = _verify(capsys)
    assert _has(out, "Atjaunoti", "0\n")
    assert _has(out, "Nav gaidīto sarakstā", "")
    # Pirms gada triāžas vēl nebija (ieviesta 14.04.2026): kopijā nav konfigurācijas.
    assert "PROBLĒMA  Triāža zem sliekšņa (2/20)" in out


@pytest.mark.parametrize("group", [1, 2, 3, 4])
def test_verify_never_reports_elapsed_time(sistema, capsys, group):
    _start(capsys, group)
    run(capsys, "restore", "--backup", "D-7")
    out = _verify(capsys) + run(capsys, "status")[1]
    lowered = out.lower()
    for word in ("sekund", "ilga", "patērēt", "aizņēm", "elapsed", "pagāj"):
        assert word not in lowered
    assert not re.search(r"\d+(?:[.,]\d+)? ?s\b", out)


def test_new_submission_after_restore_reuses_a_lost_number(sistema, capsys):
    from fastapi.testclient import TestClient

    from app.main import app, get_omd
    from app.omd_client import OmdCheck, OmdResult

    _start(capsys, 3)
    run(capsys, "restore", "--backup", "D-1")
    app.dependency_overrides[get_omd] = lambda: (
        lambda code: OmdCheck(OmdResult.NOT_ACTIVATED)
    )
    try:
        created = TestClient(app).post(
            "/submissions",
            json={
                "personalCode": "32000009999",
                "fullName": "Anna Paraudziņa",
                "email": "anna@example.com",
                "preferredChannel": "EMAIL",
                "topic": "HEATING_SUPPORT",
                "subject": "Apkures pabalsts",
                "body": "Lūdzu piešķirt apkures pabalstu.",
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert created.status_code == 201
    assert created.json()["receivedAt"].startswith("2026-10-19T08:41")
    out = _verify(capsys)
    assert _has(out, "Jauni pēc katastrofas", "1")
    assert "piešķirti zaudēto numuri: 1" in out
    assert _has(out, "Zaudēti", "100")


def test_actions_are_logged_for_the_debrief(sistema, capsys):
    _start(capsys, 1)
    run(capsys, "failover")
    run(capsys, "restore", "--backup", "D-1")
    log = (paths.root() / "darbibu-zurnals.txt").read_text(encoding="utf-8")
    assert "katastrofa GROUP=1\nfailover\nrestore B-20261018-0200" in log
    assert state.load()["restored_from"] == "B-20261018-0200"
