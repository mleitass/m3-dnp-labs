"""Mācību sistēmas izveide: sākuma stāvoklis pirms katastrofas."""

import json
import shutil

from drill import backups, paths, replica, seed, state, triage_versions
from drill.clock import NOW

SIZES_GB = {"db": 30, "attachments": 170}  # simulētie izmēri (faili ir mazi)


class SetupError(Exception):
    pass


def _clear_root() -> None:
    root = paths.root()
    if root.exists():
        if not paths.state_file().exists() and any(root.iterdir()):
            raise SetupError(f"Mape {root} nav mācību sistēma. Nekas nav dzēsts.")
        shutil.rmtree(root)
    root.mkdir(parents=True)


def reset() -> dict:
    """Izveido sākuma stāvokli no nulles. Atgriež kopsavilkumu izvadei."""
    _clear_root()
    operative, _year_ago = seed.dataset()
    seed.write_server(paths.server_dir("primary"), operative, triage_versions.CURRENT)
    sim = paths.sim_dir()
    sim.mkdir(parents=True)
    (sim / "README.txt").write_text(
        "Simulācijas tehniskie dati: gaidītais stāvoklis pārbaudei (make verify).\n"
        "Šeit nav iesniegumu satura, un šī mape nav atjaunošanas avots.\n",
        encoding="utf-8",
    )
    (sim / "gaidits.json").write_text(
        json.dumps(seed.expected_state(operative), ensure_ascii=False), encoding="utf-8"
    )
    current = state.initial()
    current["servers"]["standby"] = state.SERVER_UP
    current["standby_synced_at"] = replica.build_initial().isoformat()
    backups.build_history(backups.SCOPE_FULL)
    state.save(current)
    (paths.root() / "darbibu-zurnals.txt").write_text(
        "Darbību žurnāls (bez laika zīmogiem)\nreset\n", encoding="utf-8"
    )
    return {
        "records": len(operative),
        "attachments": sum(len(r.attachments) for r in operative),
        "backups": len(backups.catalog()),
        "now": NOW,
    }
