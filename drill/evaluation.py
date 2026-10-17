"""Triāžas novērtēšana: 20 sintētiski iesniegumi ar zināmu pareizo nodaļu."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app import triage

EVAL_FILE = Path(__file__).parent / "data" / "triage_eval.json"


@dataclass(frozen=True)
class Evaluation:
    correct: int
    total: int
    threshold: int
    destinations: Counter
    errors: int  # cik pieprasījumos MI pakalpojums neatbildēja

    @property
    def passed(self) -> bool:
        return self.correct >= self.threshold

    @property
    def percent(self) -> int:
        return round(100 * self.correct / self.total)


def load_items() -> tuple[list, int]:
    data = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    return data["items"], data["threshold"]


def evaluate(config: triage.TriageConfig) -> Evaluation:
    """Automātiskās sadales tests ar doto konfigurāciju (arī manuālā režīmā)."""
    items, threshold = load_items()
    correct, errors, destinations = 0, 0, Counter()
    for item in items:
        result = triage.route(item["subject"], item["body"], config)
        destinations[result.department] += 1
        errors += 0 if result.ok else 1
        correct += 1 if result.department == item["expected"] else 0
    return Evaluation(correct, len(items), threshold, destinations, errors)
