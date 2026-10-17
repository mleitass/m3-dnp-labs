"""Palīgfunkcijas mācību sistēmas testiem."""

from drill.__main__ import main


def run(capsys, *argv) -> tuple[int, str]:
    """Palaiž make komandas ekvivalentu un atgriež (izejas kods, izvade)."""
    code = main(list(argv))
    return code, capsys.readouterr().out
