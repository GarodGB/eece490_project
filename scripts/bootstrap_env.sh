#!/usr/bin/env bash
# Create a project virtual environment and install requirements (fixes "No module named 'flask'").
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  echo "Created .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt

echo ""
echo "Environment ready. Run the app with:"
echo "  source .venv/bin/activate"
echo "  python app.py"
echo ""
echo "Or:  .venv/bin/python app.py"
