import os
import shutil
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


def _link_or_copy(source, target):
    # Pielikumus sistēma nekad nepārraksta uz vietas, tāpēc tos var sasaistīt (ātrāk).
    if f"{os.sep}pielikumi{os.sep}" in str(source):
        os.link(source, target)
    else:
        shutil.copy2(source, target)


@pytest.fixture(scope="session")
def _sistema_template(tmp_path_factory):
    from drill import system

    root = tmp_path_factory.mktemp("template") / "sistema"
    previous = os.environ["EZERMALA_SISTEMA"]
    os.environ["EZERMALA_SISTEMA"] = str(root)
    try:
        system.reset()
    finally:
        os.environ["EZERMALA_SISTEMA"] = previous
    return root


@pytest.fixture
def sistema(_sistema_template, tmp_path, monkeypatch):
    """Svaiga mācību sistēma pagaidu mapē (tāpat kā pēc make reset)."""
    target = tmp_path / "sistema"
    shutil.copytree(_sistema_template, target, copy_function=_link_or_copy)
    monkeypatch.setenv("EZERMALA_SISTEMA", str(target))
    storage.use_system()
    return target


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
