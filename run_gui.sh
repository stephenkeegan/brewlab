#!/usr/bin/env bash
# Launch the BrewLab Streamlit GUI with one command.
set -euo pipefail

cd "$(dirname "$0")"

VENV=".venv"
STREAMLIT=""
if [[ -x "$VENV/bin/streamlit" ]]; then
  STREAMLIT="$VENV/bin/streamlit"
elif command -v streamlit >/dev/null 2>&1; then
  STREAMLIT="streamlit"
else
  echo "Error: streamlit not found. Activate the venv or install it:" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  source .venv/bin/activate" >&2
  echo "  pip install -e .[gui]" >&2
  exit 1
fi

exec "$STREAMLIT" run src/brewlab/gui/app.py
