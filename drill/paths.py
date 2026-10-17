"""Simulētās sistēmas mapes. Sakne: sistema/ vai vides mainīgais EZERMALA_SISTEMA."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SERVER_DIRS = {"primary": "galvenais-serveris", "standby": "rezerves-serveris"}


def root() -> Path:
    return Path(os.getenv("EZERMALA_SISTEMA", str(REPO / "sistema")))


def server_dir(server: str) -> Path:
    return root() / SERVER_DIRS[server]


def db_path(server: str) -> Path:
    return server_dir(server) / "db" / "iesniegumi.db"


def attachments_dir(server: str) -> Path:
    return server_dir(server) / "pielikumi"


def triage_dir(server: str) -> Path:
    return server_dir(server) / "triage"


def nas_dir() -> Path:
    return root() / "nas"


def sim_dir() -> Path:
    """Simulācijas tehniskie dati (gaidītais stāvoklis). Nav atjaunošanas avots."""
    return root() / ".simulacija"


def state_file() -> Path:
    return root() / "stavoklis.json"


def report_dir() -> Path:
    return root() / "parskats"
