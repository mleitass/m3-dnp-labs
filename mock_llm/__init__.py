"""Ārējā MI pakalpojuma imitācija "ezer-llm" (izdomāts). Tīkla izsaukumu nav.

Modelis ir deterministisks. Tas no uzvednes nolasa nodaļu sarakstu un izvēlas
nodaļu, kuras pazīmes iesnieguma tekstā sastopamas visbiežāk. Vienādu punktu
gadījumā uzvar nodaļa, kas uzvednē minēta pirmā. Ja neviena pazīme neder,
modelis atbild ar kodu, ko uzvedne norāda neskaidriem gadījumiem.

Pakalpojuma režīmi (pasniedzējam: make llm MODE=...):

| Režīms | Uzvedība                                                           |
|--------|--------------------------------------------------------------------|
| normal | alias "latest" = ezer-llm-2026-06                                  |
| down   | pakalpojums nav pieejams (HTTP 503)                                |
| slow   | atbilde pēc 12 s (simulēts; klienta noildze ir mazāka)             |
| alias  | alias "latest" = ezer-llm-2026-10: jaunais modelis lasa tikai      |
|        | iesnieguma pirmo rindu (tematu), tāpēc sadala citādi               |
"""

import re
from dataclasses import dataclass

from drill import runtime

MODES = ("normal", "down", "slow", "alias")
STABLE_MODEL = "ezer-llm-2026-06"
NEW_MODEL = "ezer-llm-2026-10"
MODELS = (STABLE_MODEL, NEW_MODEL)
LATENCY_SECONDS = {"normal": 0.4, "slow": 12.0, "alias": 0.4}

_DEPARTMENT_LINE = re.compile(r"^- ([A-Z_]+) \([^)]*\):(.*)$", re.MULTILINE)
_FALLBACK = re.compile(r"atbildi ([A-Z_]+)")
_WORD = re.compile(r"\w+")


class ProviderError(Exception):
    """Pakalpojuma kļūda. Teksts ir īss un saprotams žurnālā."""


class ProviderUnavailable(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class UnknownModel(ProviderError):
    pass


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    latency_seconds: float


def resolve_model(model: str, mode: str) -> str:
    if model == "latest":
        return NEW_MODEL if mode == "alias" else STABLE_MODEL
    if model in MODELS:
        return model
    raise UnknownModel(f"modelis '{model}' nav atrasts (HTTP 404)")


def _departments(system_prompt: str) -> list[tuple[str, list[str]]]:
    result = []
    for code, keywords in _DEPARTMENT_LINE.findall(system_prompt):
        words = [k.strip().lower() for k in keywords.split(",") if k.strip()]
        result.append((code, words))
    return result


def _matches(keyword: str, tokens: list[str]) -> bool:
    parts = keyword.split()
    for i in range(len(tokens) - len(parts) + 1):
        if all(tokens[i + j].startswith(part) for j, part in enumerate(parts)):
            return True
    return False


def classify(system_prompt: str, text: str) -> str:
    """Modeļa 'domāšana': pazīmju skaitīšana. Tīra funkcija, bez stāvokļa."""
    fallback = _FALLBACK.search(system_prompt)
    best_code = fallback.group(1) if fallback else "CHANCERY"
    tokens = _WORD.findall(text.lower())
    best_score = 0
    for code, keywords in _departments(system_prompt):
        score = sum(1 for keyword in keywords if _matches(keyword, tokens))
        if score > best_score:
            best_code, best_score = code, score
    return best_code


def complete(
    model: str, api_key: str, system_prompt: str, text: str, timeout_seconds: float
) -> Completion:
    """Viens pieprasījums pakalpojumam. API atslēgu imitācija nepārbauda."""
    mode = runtime.llm_mode()
    if mode == "down":
        raise ProviderUnavailable("pakalpojums nav pieejams (HTTP 503)")
    latency = LATENCY_SECONDS.get(mode, 0.4)
    if latency > timeout_seconds:
        raise ProviderTimeout(
            f"nav atbildes {timeout_seconds:g} s laikā (pakalpojums atbild lēni)"
        )
    version = resolve_model(model, mode)
    if version == NEW_MODEL:
        text = text.splitlines()[0] if text else ""
    return Completion(classify(system_prompt, text), version, latency)
