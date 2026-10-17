"""Komandrinda make komandām: python -m drill <komanda> [parametri]."""

import argparse
import logging
import sys
import warnings

from drill import clock, state, system


class CommandError(Exception):
    """Kļūda, ko parāda lietotājam vienā saprotamā teikumā."""


def _quiet_logs() -> None:
    # Komandu izvadē tikai rezultāts. Servisa žurnāli redzami make run logā.
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")


def cmd_reset(_args) -> list[str]:
    summary = system.reset()
    return [
        "Sākuma stāvoklis izveidots: "
        + clock.fmt_dt(summary["now"])
        + ", pirms katastrofas.",
        f"  Iesniegumi: {clock.fmt_int(summary['records'])}"
        f" · rezerves kopijas: {summary['backups']}",
        "Nākamais solis: make status",
    ]


def cmd_backup_list(_args) -> list[str]:
    from drill import backups

    _require_state()
    return backups.list_lines()


def cmd_status(_args) -> list[str]:
    from drill import status

    return status.run()


def cmd_katastrofa(args) -> list[str]:
    from drill import scenarios

    _require_state()
    try:
        return scenarios.start(args.group)
    except scenarios.ScenarioError as exc:
        raise CommandError(str(exc)) from exc


def cmd_replicate(_args) -> list[str]:
    from drill import replica

    _require_state()
    try:
        return replica.replicate()
    except replica.ReplicaError as exc:
        raise CommandError(str(exc)) from exc


def _recovery(action, *params) -> list[str]:
    from drill import recovery

    _require_state()
    try:
        return action(*params)
    except recovery.RecoveryError as exc:
        raise CommandError(str(exc)) from exc


def cmd_restore(args) -> list[str]:
    from drill import recovery

    return _recovery(recovery.restore, args.backup)


def cmd_failover(_args) -> list[str]:
    from drill import recovery

    return _recovery(recovery.failover)


def cmd_triage(args) -> list[str]:
    from drill import recovery

    return _recovery(recovery.set_triage_mode, args.mode)


def cmd_triage_config(_args) -> list[str]:
    from drill import recovery

    return _recovery(recovery.vendor_triage_config)


def cmd_verify(_args) -> list[str]:
    from drill import verify

    _require_state()
    return verify.run()


def cmd_llm(args) -> list[str]:
    import mock_llm

    if args.mode not in mock_llm.MODES:
        raise CommandError(
            "Norādiet režīmu: make llm MODE=normal, down, slow vai alias"
        )
    current = _require_state()
    current["llm_mode"] = args.mode
    state.save(current)
    state.log_action(f"llm {args.mode}")
    return [f"MI pakalpojuma imitācijas režīms: {args.mode}"]


def _require_state() -> dict:
    current = state.load()
    if not current:
        raise CommandError("Mācību sistēma vēl nav izveidota. Palaidiet: make reset")
    return current


COMMANDS = {
    "reset": cmd_reset,
    "status": cmd_status,
    "katastrofa": cmd_katastrofa,
    "backup-list": cmd_backup_list,
    "restore": cmd_restore,
    "failover": cmd_failover,
    "replicate": cmd_replicate,
    "verify": cmd_verify,
    "triage": cmd_triage,
    "triage-config": cmd_triage_config,
    "llm": cmd_llm,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m drill")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--group", default="")
    parser.add_argument("--backup", default="")
    parser.add_argument("--mode", default="")
    args = parser.parse_args(argv)
    _quiet_logs()
    try:
        lines = COMMANDS[args.command](args)
    except (CommandError, system.SetupError) as exc:
        print(str(exc))
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
