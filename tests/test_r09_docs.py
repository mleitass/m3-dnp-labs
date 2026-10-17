"""R-09: CLAUDE.md noteikumi, RUNBOOK.md veidne un Claude Code atļaujas."""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PARTICIPANT_FILES = ("CLAUDE.md", "RUNBOOK.md", "README.md", "Makefile")


def _text(name):
    return (REPO / name).read_text(encoding="utf-8")


def test_claude_md_has_the_drill_rules():
    text = _text("CLAUDE.md")
    for rule in (
        "Pirms katras komandas paskaidrojiet",
        "Nekad nedzēsiet un nemainiet rezerves kopijas",
        "apstājieties un jautājiet apstiprinājumu",
        "Nekad nepievienojiet reālus datus",
        "Sekojiet `RUNBOOK.md`",
        "Neziņojiet patērēto laiku",
    ):
        assert rule in text


def test_runbook_template_has_all_sections():
    text = _text("RUNBOOK.md")
    for section in (
        "Aktivizēšanas kritērijs",
        "Katastrofas izsludināšana",
        "Lomas",
        "Priekšnosacījumi",
        "Lēmumu punkti",
        "Paredzamais ilgums",
        "Pārbaude",
        "Komunikācijas kontrolpunkti",
        "Atgriešanās (failback)",
        "Žurnāls",
    ):
        assert section in text


def test_claude_permissions_protect_backups():
    settings = json.loads(_text(".claude/settings.json"))
    deny = settings["permissions"]["deny"]
    assert "Bash(rm:*)" in deny
    assert "Edit(sistema/nas/**)" in deny
    assert "Write(sistema/nas/**)" in deny


@pytest.mark.parametrize("name", PARTICIPANT_FILES)
def test_scope_is_tverums_never_apjoms(name):
    assert "apjom" not in _text(name).lower()
