@echo off
REM ---------------------------------------------------------------------------
REM restart.bat
REM ===========
REM Relauncher for app.py, used by the SETTINGS tab when the compact/flat layout
REM mode is toggled. Spawning a .bat instead of re-exec'ing (or Popen'ing python
REM directly from inside the dying Qt process) is far more reliable on Windows -
REM the batch process outlives the parent app, waits for it to fully close, then
REM starts a clean new instance.
REM
REM Usage (spawned by settings_tab, not run by hand):
REM     restart.bat <parent_pid>
REM ---------------------------------------------------------------------------

setlocal

REM Work from the folder this .bat lives in, so app.py resolves regardless of
REM where it was launched from.
cd /d "%~dp0"

REM Wait for the old app.py (passed as the first argument) to exit so the two
REM windows never overlap. Poll tasklist up to ~5s, then give up and launch anyway.
if not "%~1"=="" (
    set "PARENT_PID=%~1"
    for /L %%i in (1,1,50) do (
        tasklist /FI "PID eq %~1" 2>nul | find "%~1" >nul
        if errorlevel 1 goto :launch
        REM ~100ms sleep without needing timeout.exe niceties
        ping -n 1 -w 100 127.0.0.1 >nul
    )
)

:launch
REM Prefer pythonw (no console window) if available, else fall back to python.
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0app.py"
) else (
    start "" python "%~dp0app.py"
)

endlocal
