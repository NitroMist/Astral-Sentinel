#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -c 'import swisseph' 2>/dev/null || pip install -r requirements.txt
python server.py
