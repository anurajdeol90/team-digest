@echo off
setlocal ENABLEDELAYEDEXPANSION

REM Resolve absolute repo path
set REPO=%~dp0
pushd "%REPO%"

REM Ensure config.json exists
if not exist "config.json" (
  echo {> config.json
  echo   "title": "Weekly Team Digest",>> config.json
  echo   "owner_map": { "AD": "Anuraj Deol" }>> config.json
  echo }>> config.json
  echo [info] created default config.json
)

REM Ensure logs/ exists
if not exist "logs" (
  mkdir logs
  echo [info] created logs\
)

REM Optional sample if logs is empty
dir /b logs\* >nul 2>&1
if errorlevel 1 (
  > logs\sample.log (
    echo --- RAW MODEL JSON for: Beta ---
    echo {
    echo   "summary": "Beta scope reduced to hit timeline.",
    echo   "decisions": ["Ship MVP without SSO"],
    echo   "actions": [{"title":"Revise roadmap","owner":"AD","due":"2025-10-15","priority":"medium"}]
    echo }
    echo Waiting on external team for API limits.
  )
  echo [info] wrote logs\sample.log
)

REM Run aggregator with absolute paths and verbose
python -m team_email_digest --config "%CD%\config.json" --input "%CD%\logs" --format json --verbose

popd
endlocal
