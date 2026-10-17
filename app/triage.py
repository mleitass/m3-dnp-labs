"""Triāžas darbinieks (worker): nosaka, kurai nodaļai nodot iesniegumu.

Izmanto ārēju MI pakalpojumu (imitācija: mock_llm). Konfigurācija atrodas
servera mapē triage/: uzvedne prompt.txt, sadales noteikumi routing.json un
iestatījumi config.json (modelis, API atslēga, noildze).

Zināma vājā vieta: ja konfigurācijas nav vai pakalpojums neatbild, darbinieks
klusi izmanto noklusējumu un visus iesniegumus nosūta uz Kanceleju.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import mock_llm
from drill import runtime

logger = logging.getLogger("ezermala.triage")

DEPARTMENT_NAMES = {
    "SOCIAL": "Sociālais dienests",
    "UTILITIES": "Komunālā nodaļa",
    "BUILDING": "Būvvalde",
    "LANDSCAPING": "Labiekārtošanas nodaļa",
    "CHANCERY": "Kanceleja",
}
DEFAULT_DEPARTMENT = "CHANCERY"
MANUAL_QUEUE = "CHANCERY"  # Kanceleja ir arī manuālās sadales rinda
CONFIG_FILES = ("prompt.txt", "routing.json", "config.json")
FALLBACK_PROMPT = (
    "Nosaki, kurai nodaļai nodot iesniegumu. Ja nevari noteikt, atbildi CHANCERY."
)
DEFAULT_SETTINGS = {"model": "latest", "api_key": "", "timeout_seconds": 5}
SELF_TEST_TEXT = "Apkures pabalsts\nLūdzu piešķirt apkures pabalstu."


@dataclass
class TriageConfig:
    prompt: str
    departments: list
    settings: dict
    missing: list = field(default_factory=list)

    @property
    def model(self) -> str:
        return self.settings.get("model", "latest")


@dataclass(frozen=True)
class RouteResult:
    department: str
    ok: bool
    model_version: str | None = None
    detail: str = ""
    manual: bool = False


def load_config(config_dir: Path | None) -> TriageConfig:
    """Nolasa konfigurāciju. Ja faila nav, izmanto noklusējumu (bez brīdinājuma lietotājam)."""
    files = {}
    missing = []
    for name in CONFIG_FILES:
        path = config_dir / name if config_dir else None
        if path and path.exists():
            files[name] = path.read_text(encoding="utf-8")
        else:
            missing.append(name)
    if missing:
        logger.warning(
            "Triāžas konfigurācija nav pilna, trūkst: %s", ", ".join(missing)
        )
    prompt = files.get("prompt.txt", FALLBACK_PROMPT)
    try:
        departments = json.loads(files["routing.json"])["departments"]
    except (KeyError, ValueError):
        departments = []
    try:
        settings = {**DEFAULT_SETTINGS, **json.loads(files["config.json"])}
    except (KeyError, ValueError):
        settings = dict(DEFAULT_SETTINGS)
    return TriageConfig(prompt, departments, settings, missing)


def build_prompt(config: TriageConfig) -> str:
    lines = [
        f"- {d['code']} ({d['name']}): {', '.join(d.get('keywords', []))}"
        for d in config.departments
    ]
    return config.prompt.replace("{nodalas}", "\n".join(lines))


def route(
    subject: str, body: str, config: TriageConfig, mode: str = "auto"
) -> RouteResult:
    if mode == "manual":
        return RouteResult(MANUAL_QUEUE, True, detail="manuāla sadale", manual=True)
    try:
        answer = mock_llm.complete(
            model=config.model,
            api_key=config.settings.get("api_key", ""),
            system_prompt=build_prompt(config),
            text=f"{subject}\n{body}",
            timeout_seconds=float(config.settings.get("timeout_seconds", 5)),
        )
    except mock_llm.ProviderError as exc:
        # Vājā vieta: kļūdas gadījumā sūta uz noklusējuma nodaļu (fail-open).
        logger.warning("Triāža neizdevās: %s", exc)
        return RouteResult(DEFAULT_DEPARTMENT, False, detail=str(exc))
    code = answer.text.strip()
    known = {d["code"] for d in config.departments} | {DEFAULT_DEPARTMENT}
    if code not in known:
        return RouteResult(DEFAULT_DEPARTMENT, True, answer.model, "nezināms kods")
    return RouteResult(code, True, answer.model)


def active_config() -> TriageConfig:
    return load_config(runtime.triage_config_dir())


def route_new(subject: str, body: str) -> RouteResult:
    """Jauna iesnieguma sadale servisā (aktīvā servera konfigurācija un režīms)."""
    return route(subject, body, active_config(), runtime.triage_mode())


def self_test(config: TriageConfig | None = None) -> RouteResult:
    """Pašpārbaude: vai MI pakalpojums atbild. Sadales pareizību nepārbauda."""
    config = config or active_config()
    subject, body = SELF_TEST_TEXT.split("\n", 1)
    return route(subject, body, config)
