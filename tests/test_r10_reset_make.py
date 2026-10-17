"""R-10: make reset atgriež sākuma stāvokli; make komandas strādā caur Makefile."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from drill import paths, state, system
from tests.drill_helpers import run

REPO = paths.REPO


def test_tests_never_touch_the_groups_system():
    assert paths.root() != REPO / "sistema"


def test_reset_after_disaster_restores_identical_clean_state(sistema, capsys):
    expected_before = (paths.sim_dir() / "gaidits.json").read_text(encoding="utf-8")
    run(capsys, "katastrofa", "--group", "1")
    run(capsys, "failover")
    code, out = run(capsys, "reset")
    assert code == 0
    assert "pirms katastrofas" in out
    assert "rezerves kopijas: 4" in out
    current = state.load()
    assert current["scenario"] is None
    assert current["active"] == "primary"
    assert current["servers"] == {"primary": "up", "standby": "up"}
    assert (paths.sim_dir() / "gaidits.json").read_text(
        encoding="utf-8"
    ) == expected_before
    assert not (paths.root() / "saglabats").exists()
    _code, verify = run(capsys, "verify")
    assert "PROBLĒMA" not in verify


def test_reset_refuses_a_folder_that_is_not_the_drill_system(tmp_path, monkeypatch):
    foreign = tmp_path / "cits"
    foreign.mkdir()
    (foreign / "svarigs.txt").write_text("nedzēst", encoding="utf-8")
    monkeypatch.setenv("EZERMALA_SISTEMA", str(foreign))
    with pytest.raises(system.SetupError):
        system.reset()
    assert (foreign / "svarigs.txt").exists()


def test_commands_before_reset_ask_for_reset(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EZERMALA_SISTEMA", str(tmp_path / "nav"))
    for command in ("status", "verify", "backup-list", "failover"):
        _code, out = run(capsys, command)
        assert "make reset" in out


needs_make = pytest.mark.skipif(shutil.which("make") is None, reason="nav make")


def _make(target_dir, *args):
    env = {**os.environ, "EZERMALA_SISTEMA": str(target_dir), "PY": sys.executable}
    result = subprocess.run(
        ["make", "--no-print-directory", *args],
        cwd=REPO, env=env, capture_output=True, text=True, check=False,
    )  # fmt: skip
    return result.returncode, result.stdout + result.stderr


@needs_make
def test_make_help_lists_participant_commands_only():
    _code, out = _make(paths.root(), "help")
    for target in ("status", "katastrofa", "backup-list", "restore", "failover",
                   "replicate", "verify", "triage", "reset", "test"):  # fmt: skip
        assert f"make {target} " in out
    assert "triage-config" not in out
    assert "make llm" not in out


@needs_make
def test_make_targets_pass_group_backup_and_mode(sistema):
    code, out = _make(sistema, "katastrofa", "GROUP=4")
    assert code == 0, out
    assert "grupa 4" in out
    code, out = _make(sistema, "restore", "BACKUP=D-1")
    assert "B-20261018-0200" in out
    code, out = _make(sistema, "triage", "MODE=manual")
    assert "Kancelejā" in out
    code, out = _make(sistema, "verify")
    assert "Triāža manuālā režīmā" in out
    assert "Error" not in out


@needs_make
def test_make_hides_error_noise_but_strict_keeps_exit_code(sistema):
    _make(sistema, "katastrofa", "GROUP=2")
    code, out = _make(sistema, "failover")
    assert code == 0
    assert "Error" not in out
    code, _out = _make(sistema, "failover", "STRICT=1")
    assert code != 0


def test_state_file_is_plain_json(sistema):
    data = json.loads(paths.state_file().read_text(encoding="utf-8"))
    assert data["triage_mode"] == "auto"
