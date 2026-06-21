#!/usr/bin/env bash
# ============================================================================
#  Star Simulator -- one-click launcher (macOS / Linux)
#
#  Run it:   ./start.sh      (first run sets everything up; later runs are instant)
#
#  On the first run it creates a Python virtual environment, installs the
#  dependencies, and downloads the MIST stellar grids (~180 MB). It opens
#  http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop the server.
# ============================================================================
set -e
cd "$(dirname "$0")/backend"

PY=".venv/bin/python"

open_browser() {
  { command -v open  >/dev/null 2>&1 && open  http://127.0.0.1:8000; } ||
  { command -v xdg-open >/dev/null 2>&1 && xdg-open http://127.0.0.1:8000; } || true
}

# If a server is already running on :8000, just open the browser.
if curl -fs -m 1 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "A Star Simulator server is already running -- opening your browser."
  open_browser
  exit 0
fi

# First run: create the virtual environment + install the package.
if [ ! -x "$PY" ]; then
  echo "[setup] Creating Python virtual environment (first run only)..."
  python3 -m venv .venv
  echo "[setup] Installing dependencies (this can take a minute)..."
  "$PY" -m pip install --upgrade pip >/dev/null
  "$PY" -m pip install -e ".[dev]"
fi

# First run: fetch the MIST grids if none are present (~180 MB).
if ! ls -d ../data/feh_* >/dev/null 2>&1; then
  echo "[setup] Downloading MIST stellar grids (~180 MB, first run only)..."
  "$PY" -m star_sim.fetch_mist ||
    echo "[warn] Grid download failed -- the app still starts, but shows a data error until you run it again."
fi

# Open the browser shortly after the server has had time to bind.
( sleep 3; open_browser ) &

echo
echo "[run] Star Simulator is running at http://127.0.0.1:8000"
echo "      Press Ctrl+C to stop it."
echo
exec "$PY" -m uvicorn star_sim.api:app --host 127.0.0.1 --port 8000
