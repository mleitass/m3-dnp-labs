"""Rezerves serveris (warm standby): galvenā servera kopija, ko atjauno ik pēc 15 min.

Replikācija kopē visu, kas ir galvenajā serverī: arī kļūdainus vai bojātus datus.
"""

import shutil
from datetime import datetime, timedelta

from drill import clock, paths, seed, state, triage_versions

INTERVAL = timedelta(minutes=15)


class ReplicaError(Exception):
    pass


def last_scheduled_sync(moment: datetime) -> datetime:
    """Pēdējā plānotā sinhronizācija līdz brīdim moment (ik pēc 15 min)."""
    minutes = (moment.minute // 15) * 15
    return moment.replace(minute=minutes, second=0, microsecond=0)


def build_initial() -> datetime:
    """Sākuma stāvoklis: rezerves serveris sinhronizēts pēdējā plānotajā reizē."""
    synced_at = last_scheduled_sync(clock.NOW)
    seed.write_server(
        paths.server_dir("standby"),
        seed.records_until(synced_at),
        triage_versions.CURRENT,
        snapshot_at=synced_at,
    )
    return synced_at


def copy_primary_to_standby() -> None:
    target = paths.server_dir("standby")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(paths.server_dir("primary"), target)


def replicate() -> list[str]:
    current = state.load()
    servers = current["servers"]
    if current["active"] != "primary":
        raise ReplicaError(
            "Šobrīd aktīvs ir rezerves serveris. Sinhronizācija no galvenā servera "
            "ir apturēta, lai nepārrakstītu darbojošos servisu."
        )
    if servers.get("primary") != state.SERVER_UP:
        raise ReplicaError("Sinhronizācija neizdevās: galvenais serveris nedarbojas.")
    if servers.get("standby") != state.SERVER_UP:
        raise ReplicaError("Sinhronizācija neizdevās: rezerves serveris nedarbojas.")
    copy_primary_to_standby()
    current["standby_synced_at"] = clock.NOW.isoformat()
    state.save(current)
    state.log_action("replicate")
    return [
        f"Rezerves serveris sinhronizēts ar galveno serveri ({clock.fmt_dt(clock.NOW)}).",
        "Automātiski tas notiek ik pēc 15 minūtēm.",
    ]
