"""Triāžas konfigurācijas versijas. Simulācijas dati, nav atjaunošanas avots.

- 2026-04: ieviešana (14.04.2026), SIA "Ezerdati" nodošanas pakete.
- 2026-09: pašvaldības labojums apkures pabalsta pieteikšanās laikam
  (apkures pabalsts pāriet no Komunālās nodaļas uz Sociālo dienestu).
Pirms ieviešanas triāžas nebija: iesniegumus nodaļām sadalīja Kanceleja.
"""

import json
from datetime import datetime

from drill.clock import TZ

CURRENT = "2026-09"
VENDOR = "2026-04"
GO_LIVE = datetime(2026, 4, 14, tzinfo=TZ)
CURRENT_FROM = datetime(2026, 9, 28, tzinfo=TZ)

_PROMPT_HEAD = (
    'Tu esi Ezermalas novada pašvaldības e-pakalpojuma "Iesniegumi" šķirotājs.\n'
    "Izlasi iedzīvotāja iesniegumu un nosaki, kurai nodaļai to nodot.\n"
)
PROMPTS = {
    VENDOR: _PROMPT_HEAD
    + "\nNodaļas un pazīmes:\n{nodalas}\n\n"
    + "Atbildi tikai ar nodaļas kodu. Ja nevari noteikt, atbildi CHANCERY.\n",
    CURRENT: _PROMPT_HEAD
    + "Iedzīvotāja izvēlēto tēmu neņem vērā: tā bieži ir kļūdaina.\n"
    + "\nNodaļas un pazīmes:\n{nodalas}\n\n"
    + "Atbildi tikai ar nodaļas kodu. Ja nevari noteikt, atbildi CHANCERY.\n",
}

_UTILITIES = [
    "bedr", "iel", "ietv", "ceļ", "asfalt", "apgaismoj", "latern",
    "atkritum", "konteiner", "šķirot",
]  # fmt: skip
_BUILDING = [
    "būvatļauj", "būvniec", "būvvald", "detālplānoj",
    "teritorijas plānojum", "zemes vienīb", "žog",
]  # fmt: skip
_LANDSCAPING = [
    "park", "skvēr", "soliņ", "kok", "zālien", "puķ", "rotaļu laukum", "strūklak",
]  # fmt: skip
_SOCIAL = ["pabalst", "sociāl", "trūcīg", "maznodrošināt", "aprūp"]


def _department(code: str, name: str, keywords: list) -> dict:
    return {"code": code, "name": name, "keywords": keywords}


ROUTING = {
    VENDOR: {
        "version": "2026-04-14",
        "departments": [
            _department(
                "UTILITIES", "Komunālā nodaļa", _UTILITIES + ["apkur", "siltum"]
            ),
            _department("SOCIAL", "Sociālais dienests", _SOCIAL),
            _department("BUILDING", "Būvvalde", _BUILDING),
            _department("LANDSCAPING", "Labiekārtošanas nodaļa", _LANDSCAPING),
            _department("CHANCERY", "Kanceleja", []),
        ],
    },
    CURRENT: {
        "version": "2026-09-28",
        "note": "Apkures pabalsts: Sociālais dienests (pieteikšanās no 12.10.2026)",
        "departments": [
            _department(
                "SOCIAL",
                "Sociālais dienests",
                ["apkures pabalst", "apkures atbalst", "kompensāc"] + _SOCIAL,
            ),
            _department("UTILITIES", "Komunālā nodaļa", _UTILITIES),
            _department("BUILDING", "Būvvalde", _BUILDING),
            _department("LANDSCAPING", "Labiekārtošanas nodaļa", _LANDSCAPING),
            _department("CHANCERY", "Kanceleja", []),
        ],
    },
}

# Atslēga ir viltota. Īsta atslēga konfigurācijas failā būtu vājā vieta.
SETTINGS = {
    "provider": "ezer-llm (ārējs MI API, ES reģions)",
    "model": "latest",
    "api_key": "FAKE-KEY-ezermala-0000",
    "timeout_seconds": 5,
    "temperature": 0,
}


def version_at(moment: datetime) -> str | None:
    """Konfigurācijas versija brīdī moment; None pirms triāžas ieviešanas."""
    if moment < GO_LIVE:
        return None
    return CURRENT if moment >= CURRENT_FROM else VENDOR


def files(version: str) -> dict[str, str]:
    """Konfigurācijas faili, kā tie atrodas servera mapē triage/."""
    return {
        "prompt.txt": PROMPTS[version],
        "routing.json": json.dumps(ROUTING[version], ensure_ascii=False, indent=2),
        "config.json": json.dumps(SETTINGS, ensure_ascii=False, indent=2),
    }
