"""R-04: rotaļu sistēma: sintētiski dati, triāža ar MI imitāciju, make status."""

from collections import Counter
from datetime import datetime, timedelta

import pytest

from app import triage
from app.models import PERSONAL_CODE
from drill import evaluation, seed, state, triage_versions
from drill.clock import NOW, TZ
from tests.drill_helpers import run


def _week(records, start):
    end = start + timedelta(days=7)
    return [r for r in records if start <= r.received_at < end]


def test_volumes_match_case_numbers():
    operative, year_ago = seed.dataset()
    normal = _week(operative, datetime(2026, 9, 21, tzinfo=TZ))
    peak = _week(operative, datetime(2026, 10, 12, tzinfo=TZ))
    assert 295 <= len(normal) <= 300
    assert 1195 <= len(peak) <= 1200
    assert 2300 < len(operative) < 2600
    assert len(year_ago) < 500


def test_weekdays_and_office_hours_are_heavier():
    peak = _week(seed.dataset()[0], datetime(2026, 10, 12, tzinfo=TZ))
    by_day = Counter(r.received_at.weekday() for r in peak)
    assert by_day[0] > 2 * by_day[6]
    office = sum(1 for r in peak if 9 <= r.received_at.hour < 17)
    night = sum(1 for r in peak if r.received_at.hour < 6)
    assert office > 10 * night


def test_peak_week_is_mostly_heating_support_with_wrong_topics():
    peak = _week(seed.dataset()[0], datetime(2026, 10, 12, tzinfo=TZ))
    heating = [r for r in peak if "apkur" in (r.row["subject"] + r.row["body"]).lower()]
    assert 0.65 < len(heating) / len(peak) < 0.75
    topics = Counter(r.row["topic"] for r in heating)
    assert topics["HEATING_SUPPORT"] < 0.7 * len(heating)
    assert topics["OTHER"] > 0.2 * len(heating)


def test_data_is_synthetic():
    operative, year_ago = seed.dataset()
    for record in operative + year_ago:
        assert record.row["personalCode"].startswith("3200000")
        assert PERSONAL_CODE.fullmatch(record.row["personalCode"])
        assert record.row["email"].endswith("@example.com")


def test_dataset_is_deterministic():
    first = seed._generate(
        seed.OPERATIVE_START, NOW, 2026, seed.random.Random(seed.SEED)
    )
    operative, _ = seed.dataset()
    assert [r.row for r in first] == [r.row for r in operative]


def _config(version):
    return seed.triage_config(version)


def test_baseline_accuracy_is_19_of_20(sistema):
    result = evaluation.evaluate(_config(triage_versions.CURRENT))
    assert (result.correct, result.total) == (19, 20)
    assert result.passed


def test_missing_configuration_sends_everything_to_chancery(tmp_path):
    result = evaluation.evaluate(triage.load_config(tmp_path / "nav"))
    assert result.correct == 2
    assert result.destinations == Counter({"CHANCERY": 20})


def test_vendor_copy_misroutes_heating_support(sistema):
    result = evaluation.evaluate(_config(triage_versions.VENDOR))
    assert result.correct == 14
    assert not result.passed


def test_vendor_copy_is_the_april_2026_go_live_package():
    assert triage_versions.ROUTING[triage_versions.VENDOR]["version"] == "2026-04-14"
    assert triage_versions.version_at(datetime(2025, 10, 19, tzinfo=TZ)) is None
    assert triage_versions.version_at(datetime(2026, 9, 19, tzinfo=TZ)) == "2026-04"
    assert triage_versions.version_at(datetime(2026, 10, 18, tzinfo=TZ)) == "2026-09"


def test_vendor_copy_misses_are_mostly_heating_support():
    items, _threshold = evaluation.load_items()
    config = _config(triage_versions.VENDOR)
    misses = [
        item
        for item in items
        if triage.route(item["subject"], item["body"], config).department
        != item["expected"]
    ]
    heating = [m for m in misses if "apkur" in (m["subject"] + m["body"]).lower()]
    assert (len(misses), len(heating)) == (6, 5)


def test_records_before_go_live_have_no_triage_department():
    _operative, year_ago = seed.dataset()
    assert all(r.row["department"] is None for r in year_ago)


def test_vendor_copy_fixed_by_hand_reaches_baseline(sistema):
    """G4 papildu ceļš: SOCIAL pazīmes papildina un SOCIAL liek pirmo."""
    vendor = _config(triage_versions.VENDOR)
    departments = [dict(d) for d in vendor.departments]
    social = next(d for d in departments if d["code"] == "SOCIAL")
    social["keywords"] = [
        "apkures pabalst",
        "apkures atbalst",
        "kompensāc",
        *social["keywords"],
    ]
    departments.remove(social)
    fixed = triage.TriageConfig(vendor.prompt, [social, *departments], vendor.settings)
    assert evaluation.evaluate(fixed).correct == 19


@pytest.mark.parametrize(("mode", "correct"), [("alias", 14), ("down", 2), ("slow", 2)])
def test_provider_failure_modes(sistema, mode, correct):
    current = state.load()
    current["llm_mode"] = mode
    state.save(current)
    assert evaluation.evaluate(_config(triage_versions.CURRENT)).correct == correct


def test_pinned_model_is_not_affected_by_alias_change(sistema):
    current = state.load()
    current["llm_mode"] = "alias"
    state.save(current)
    config = _config(triage_versions.CURRENT)
    pinned = triage.TriageConfig(
        config.prompt,
        config.departments,
        {**config.settings, "model": "ezer-llm-2026-06"},
    )
    assert evaluation.evaluate(pinned).correct == 19


def test_manual_mode_routes_to_chancery_queue():
    result = triage.route(
        "Apkures pabalsts", "Lūdzu.", _config(triage_versions.CURRENT), "manual"
    )
    assert (result.department, result.manual) == ("CHANCERY", True)


def test_status_shows_counts_newest_record_and_self_test(sistema, capsys):
    code, out = run(capsys, "status")
    assert code == 0
    assert "Portāls:             darbojas" in out
    assert "Iesniegumi:          2 4" in out
    assert "Jaunākais ieraksts:  IES-2026-" in out
    assert "pirmdiena 19.10.2026 08:" in out
    assert "Triāžas pašpārbaude: atbild" in out


def test_status_self_test_reports_provider_down(sistema, capsys):
    run(capsys, "llm", "--mode", "down")
    _code, out = run(capsys, "status")
    assert "Triāžas pašpārbaude: NEATBILD" in out


def test_new_submission_is_routed_on_the_system(sistema):
    from fastapi.testclient import TestClient

    from app.main import app, get_omd
    from app.omd_client import OmdCheck, OmdResult

    app.dependency_overrides[get_omd] = lambda: (
        lambda code: OmdCheck(OmdResult.NOT_ACTIVATED)
    )
    try:
        client = TestClient(app)
        created = client.post(
            "/submissions",
            json={
                "personalCode": "32000009999",
                "fullName": "Anna Paraudziņa",
                "email": "anna@example.com",
                "preferredChannel": "EMAIL",
                "topic": "OTHER",
                "subject": "Apkures pabalsts",
                "body": "Lūdzu piešķirt apkures pabalstu.",
            },
        )
        assert created.status_code == 201
        detail = client.get(f"/submissions/{created.json()['id']}").json()
        assert detail["department"] == "SOCIAL"
        assert created.json()["id"] == "IES-2026-011836"
    finally:
        app.dependency_overrides.clear()
