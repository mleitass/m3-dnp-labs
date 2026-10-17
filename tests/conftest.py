import os
import tempfile

# Testi nekad neaiztiek grupas mācību sistēmu mapē sistema/.
os.environ["EZERMALA_SISTEMA"] = tempfile.mkdtemp(prefix="ezermala-tests-")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import storage  # noqa: E402
from app.main import app, get_omd  # noqa: E402
from app.omd_client import OmdCheck, OmdResult  # noqa: E402


class FakeOmd:
    """Viltots OMD klients (test double): testi nesazinās ar īstu reģistru."""

    def __init__(self):
        self.results = {"32000000001": OmdCheck(OmdResult.ACTIVE)}
        self.calls = []

    def __call__(self, personal_code: str) -> OmdCheck:
        self.calls.append(personal_code)
        return self.results.get(personal_code, OmdCheck(OmdResult.NOT_ACTIVATED))


@pytest.fixture
def fake_omd():
    return FakeOmd()


@pytest.fixture
def sistema(tmp_path, monkeypatch):
    """Svaiga mācību sistēma pagaidu mapē (tāpat kā pēc make reset)."""
    from drill import system

    monkeypatch.setenv("EZERMALA_SISTEMA", str(tmp_path / "sistema"))
    storage.use_system()
    system.reset()
    return tmp_path / "sistema"


@pytest.fixture
def client(fake_omd):
    storage.reset(seed=False)
    app.dependency_overrides[get_omd] = lambda: fake_omd
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def valid_payload():
    # Sintētiski dati
    return {
        "personalCode": "32000000101",
        "fullName": "Līga Testiņa-Izdomātā",
        "email": "liga@example.com",
        "preferredChannel": "EMAIL",
        "topic": "ROADS",
        "subject": "Bedre Ezera ielā",
        "body": "Pie Ezera ielas 12 ir liela bedre. Lūdzu, salabojiet to.",
    }
