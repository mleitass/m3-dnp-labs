"""Scenāriji: katrai grupai sava katastrofa (make katastrofa GROUP=1..4).

Izvade apraksta tikai simptomus, ko redz cilvēki. Scenārija būtību grupa
atklāj pati, strādājot pēc sava runbook.
"""

from dataclasses import dataclass
from datetime import datetime

from drill import backups, clock, faults, paths, replica, seed, state, triage_versions
from drill.clock import TZ

CORRUPTION_AT = datetime(2026, 10, 19, 8, 12, tzinfo=TZ)


@dataclass(frozen=True)
class Scenario:
    kind: str  # "corruption" vai "storage"
    backup_scope: tuple[str, ...] = backups.SCOPE_FULL
    damaged_backup: str | None = None


SCENARIOS = {
    1: Scenario("corruption"),
    2: Scenario("storage", damaged_backup="B-20261018-0200"),
    3: Scenario("storage", backup_scope=("db", "triage")),
    4: Scenario("storage", backup_scope=("db", "attachments")),
}

_FOOTER = [
    'Ārpakalpojuma sniedzējs SIA "Ezerdati" darbu sāk 09:00.',
    "Apkures pabalsta pieteikšanās beidzas piektdien 23:59.",
    "",
    "Rīkojieties pēc sava RUNBOOK.md. Stāvoklis: make status",
]
SYMPTOMS = {
    "corruption": [
        "Klientu apkalpošanas centrs ziņo:",
        "  - darbinieku iesniegumu saraksts neatveras (kļūda 500);",
        "  - atvērtajos iesniegumos trūkst iesniedzēja datu un teksta.",
        "Serveri darbojas.",
    ],
    "storage": [
        "Portāls atgriež kļūdu 503. Uzraudzības sistēma ziņo:",
        "  datu krātuves masīvs serveru telpā nav pieejams.",
    ],
}


class ScenarioError(Exception):
    pass


def _check_clean(current: dict) -> None:
    if current.get("scenario"):
        raise ScenarioError(
            f"Katastrofa jau sākta (grupa {current['scenario']}). "
            "Lai sāktu no jauna: make reset"
        )
    if current["active"] != "primary" or current.get("restored_from"):
        raise ScenarioError("Sistēma nav sākuma stāvoklī. Vispirms: make reset")


def _corrupt_primary_and_standby(current: dict) -> None:
    faults.corrupt_records(paths.db_path("primary"), CORRUPTION_AT)
    # Rezerves serveris sinhronizēts 08:15 un 08:30, pēc bojājuma: tas kopēja arī to.
    synced_at = replica.last_scheduled_sync(clock.NOW)
    standby = paths.server_dir("standby")
    seed.write_server(standby, seed.records_until(synced_at), triage_versions.CURRENT)
    faults.corrupt_records(paths.db_path("standby"), CORRUPTION_AT)
    current["standby_synced_at"] = synced_at.isoformat()


def start(group_text: str) -> list[str]:
    try:
        group = int(group_text)
        scenario = SCENARIOS[group]
    except (ValueError, KeyError):
        raise ScenarioError(
            "Norādiet savas grupas numuru: make katastrofa GROUP=1 (1, 2, 3 vai 4)"
        ) from None
    current = state.load()
    _check_clean(current)
    if scenario.backup_scope != backups.SCOPE_FULL:
        backups.build_history(scenario.backup_scope)
    if scenario.damaged_backup:
        backups.damage(scenario.damaged_backup)
    if scenario.kind == "corruption":
        _corrupt_primary_and_standby(current)
    else:
        faults.lose_storage(current, ("primary", "standby"))
    current["scenario"] = group
    state.save(current)
    state.log_action(f"katastrofa GROUP={group}")
    return [
        f"KATASTROFA · {clock.fmt_dt(clock.NOW)} · grupa {group}",
        "",
        *SYMPTOMS[scenario.kind],
        *_FOOTER,
    ]
