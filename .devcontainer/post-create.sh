#!/usr/bin/env bash
# Codespace sagatavošana. Katrs solis ir neatkarīgs: ja viens neizdodas,
# pārējie tomēr izpildās, un Codespace atveras.
cd "$(dirname "$0")/.." || exit 1

echo "1/4 Python pakotnes"
python -m pip install -q --disable-pip-version-check -r requirements-dev.txt \
  || echo "BRĪDINĀJUMS: Python pakotnes neizdevās uzstādīt"

echo "2/4 Claude Code"
curl -fsSL https://claude.ai/install.sh | bash \
  || echo "BRĪDINĀJUMS: Claude Code neizdevās uzstādīt"

echo "3/4 Sistēmas sākuma stāvoklis"
make --no-print-directory reset \
  || echo "BRĪDINĀJUMS: make reset neizdevās"

echo "4/4 sqlite3 un make"
{ sudo apt-get update -qq && sudo apt-get install -y -qq --no-install-recommends sqlite3 make; } >/dev/null 2>&1 \
  || echo "BRĪDINĀJUMS: sqlite3 neizdevās uzstādīt (mācībām tas nav obligāts)"

echo "Gatavs. Terminālī: make status"
