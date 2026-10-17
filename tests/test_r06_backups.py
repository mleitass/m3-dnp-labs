"""R-06: rezerves kopiju vēsture ar kontrolsummām, žurnālu un tvērumu."""

import tarfile

import pytest

from drill import backups, paths
from tests.drill_helpers import run


def _members(backup_id):
    with tarfile.open(backups.archive_path(backup_id)) as archive:
        return archive.getnames()


def test_history_has_depth_per_mk397_70(sistema):
    ages = sorted(backups.find(name)["id"] for name in ("D-1", "D-7", "D-30", "D-365"))
    assert ages == [
        "B-20251019-0200",
        "B-20260919-0200",
        "B-20261012-0200",
        "B-20261018-0200",
    ]


def test_backup_list_shows_history_checksums_and_failed_monday_run(sistema, capsys):
    code, out = run(capsys, "backup-list")
    assert code == 0
    assert "B-20261018-0200   svētdiena 18.10.2026 02:00   D-1" in out
    assert "B-20261012-0200*" in out
    assert out.count("atbilst") == 4
    assert "NEATBILST" not in out
    assert "pirmdiena 19.10.2026 02:00   NEIZDEVĀS" in out
    assert "199 GB" in out


def test_full_scope_contains_db_attachments_and_triage(sistema):
    names = _members("B-20261018-0200")
    assert "db/iesniegumi.db" in names
    assert any(n.startswith("pielikumi/") for n in names)
    assert "triage/prompt.txt" in names


def test_year_old_backup_predates_the_triage(sistema):
    assert not any(n.startswith("triage/") for n in _members("B-20251019-0200"))
    with tarfile.open(backups.archive_path("B-20260919-0200")) as archive:
        routing = archive.extractfile("triage/routing.json").read().decode("utf-8")
    assert '"version": "2026-04-14"' in routing


@pytest.mark.parametrize(
    ("scope", "present", "absent"),
    [
        (("db", "triage"), "triage/", "pielikumi/"),
        (("db", "attachments"), "pielikumi/", "triage/"),
    ],
)
def test_scope_is_configurable(sistema, scope, present, absent):
    backups.build_history(scope)
    names = _members("B-20261018-0200")
    assert any(n.startswith(present) for n in names)
    assert not any(n.startswith(absent) for n in names)
    job = (paths.nas_dir() / backups.JOB).read_text(encoding="utf-8")
    assert absent not in job


def test_damaged_backup_fails_checksum(sistema, capsys):
    backups.damage("B-20261018-0200")
    assert not backups.checksum_ok(backups.find("D-1"))
    _code, out = run(capsys, "backup-list")
    assert "D-1     199 GB  NEATBILST" in out


def test_unknown_backup_id_lists_available(sistema):
    with pytest.raises(backups.BackupError, match="B-20261018-0200"):
        backups.find("B-20261019-0200")
