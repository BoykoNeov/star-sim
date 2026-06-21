@echo off
REM ============================================================================
REM  Star Simulator -- one-click launcher (Windows)
REM
REM  Just DOUBLE-CLICK this file. On the very first run it creates a Python
REM  virtual environment, installs the dependencies, and downloads the MIST
REM  stellar grids (~180 MB). Every run after that starts instantly.
REM
REM  It opens http://127.0.0.1:8000 in your browser automatically.
REM  Close this window (or press Ctrl+C) to stop the server.
REM ============================================================================

setlocal
title Star Simulator
cd /d "%~dp0backend"

set "PY=.venv\Scripts\python.exe"

REM --- If a server is already running on :8000, just open the browser. ---------
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 http://127.0.0.1:8000/health | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 (
  echo A Star Simulator server is already running -- opening your browser.
  start "" "http://127.0.0.1:8000"
  goto :eof
)

REM --- First run: create the virtual environment + install the package. --------
if not exist "%PY%" (
  echo [setup] Creating Python virtual environment ^(first run only^)...
  python -m venv .venv || goto :nopython
  echo [setup] Installing dependencies ^(this can take a minute^)...
  "%PY%" -m pip install --upgrade pip >nul
  "%PY%" -m pip install -e ".[dev]" || goto :pipfail
)

REM --- First run: fetch the MIST grids if none are present (~180 MB). -----------
set "HAVE_DATA="
for /d %%G in ("..\data\feh_*") do set "HAVE_DATA=1"
if not defined HAVE_DATA (
  echo [setup] Downloading MIST stellar grids ^(~180 MB, first run only^)...
  "%PY%" -m star_sim.fetch_mist || echo [warn] Grid download failed -- the app still starts, but shows a data error until you run it again.
)

REM --- Open the browser shortly after the server has had time to bind. ----------
start "" /b powershell -NoProfile -Command "Start-Sleep 3; Start-Process 'http://127.0.0.1:8000'"

echo.
echo [run] Star Simulator is running at http://127.0.0.1:8000
echo       Close this window or press Ctrl+C to stop it.
echo.
"%PY%" -m uvicorn star_sim.api:app --host 127.0.0.1 --port 8000
goto :eof

:nopython
echo.
echo [error] Could not run "python". Install Python 3.11+ from
echo         https://www.python.org/downloads/ -- tick "Add Python to PATH" in
echo         the installer -- then double-click this file again.
pause
goto :eof

:pipfail
echo.
echo [error] Installing dependencies failed. Check your internet connection,
echo         then double-click this file again.
pause
goto :eof
