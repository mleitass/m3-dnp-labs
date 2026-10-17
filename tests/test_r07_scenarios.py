"""R-07: make katastrofa GROUP=1..4 atveido katras grupas slazdu no sākuma stāvokļa."""

import sqlite3
import tarfile

import pytest

from drill import backups, paths, state
from tests.drill_helpers import run


def _members(backup_id):
    with tarfile.open(backups.archive_path(backup_id)) as archive:
        return archive.getnames()


def _blank_codes(server):
    conn = sqlite3.connect(paths.db_path(server))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE personalCode = ''"
        ).fetchone()[0]
    finally:
        conn.close()


@pytest.mark.parametrize("group", ["", "0", "5", "x"])
def test_group_must_be_1_to_4(sistema, capsys, group):
    code, out = run(capsys, "katastrofa", "--group", group)
    assert code == 1
    assert "make katastrofa GROUP=1" in out


def test_second_disaster_needs_reset(sistema, capsys):
    run(capsys, "katastrofa", "--group", "2")
    code, out = run(capsys, "katastrofa", "--group", "3")
    assert code == 1
    assert "make reset" in out


def test_g1_logical_corruption_also_on_standby(sistema, capsys):
    code, out = run(capsys, "katastrofa", "--group", "1")
    assert code == 0
    assert "kļūda 500" in out
    assert _blank_codes("primary") > 2000
    assert _blank_codes("standby") > 2000
    assert state.load()["standby_synced_at"] == "2026-10-19T08:30:00+03:00"
    _code, status = run(capsys, "status")
    assert "Portāls:             KĻŪDA" in status
    assert (
        "Rezerves serveris:   darbojas, sinhronizēts pirmdiena 19.10.2026 08:30"
        in status
    )


@pytest.mark.parametrize("group", ["2", "3", "4"])
def test_storage_loss_takes_primary_and_standby(sistema, capsys, group):
    code, out = run(capsys, "katastrofa", "--group", group)
    assert code == 0
    assert "kļūdu 503" in out
    assert not paths.server_dir("primary").exists()
    _code, status = run(capsys, "status")
    assert "Portāls:             NEDARBOJAS" in status
    assert "Rezerves serveris:   NEDARBOJAS" in status


def test_storage_loss_symptoms_are_identical_for_g2_g3_g4(sistema, capsys):
    _code, out = run(capsys, "katastrofa", "--group", "2")
    assert out.replace("grupa 2", "grupa N") == _symptoms_for("3", capsys).replace(
        "grupa 3", "grupa N"
    )


def _symptoms_for(group, capsys):
    run(capsys, "reset")
    return run(capsys, "katastrofa", "--group", group)[1]


def test_g2_latest_backup_fails_checksum(sistema, capsys):
    run(capsys, "katastrofa", "--group", "2")
    assert not backups.checksum_ok(backups.find("D-1"))
    assert backups.checksum_ok(backups.find("D-7"))


def test_g3_backups_have_no_attachments(sistema, capsys):
    run(capsys, "katastrofa", "--group", "3")
    for entry in backups.catalog():
        names = _members(entry["id"])
        assert "db/iesniegumi.db" in names
        assert not any(n.startswith("pielikumi/") for n in names)
        assert backups.checksum_ok(entry)


def test_g4_backups_have_no_triage_configuration(sistema, capsys):
    run(capsys, "katastrofa", "--group", "4")
    for entry in backups.catalog():
        names = _members(entry["id"])
        assert any(n.startswith("pielikumi/") for n in names)
        assert not any(n.startswith("triage/") for n in names)


def test_disaster_output_does_not_reveal_the_trap(sistema, capsys):
    for group in ("1", "2", "3", "4"):
        run(capsys, "reset")
        _code, out = run(capsys, "katastrofa", "--group", group)
        lowered = out.lower()
        for word in ("kontrolsum", "pielikum", "triāž", "rezerves serveris", "kopij"):
            assert word not in lowered
