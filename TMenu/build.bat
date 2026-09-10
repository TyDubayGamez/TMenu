@echo off
REM ---------------------------------------------------------------------------
REM build.bat
REM =========
REM Run this ON WINDOWS, from inside this folder (double-click it, or open a
REM command prompt here and run `build.bat`). PyInstaller cannot cross-compile,
REM so the .exe has to be built on the OS it's meant to run on - hence this
REM being a .bat rather than something Claude could run for you.
REM
REM What it does:
REM   1. Asks what version number to stamp on this build (or keeps the last
REM      one used if you just hit Enter) and writes it into version_info.txt
REM      via build_version.py
REM   2. Installs PySide6 / requests / pyinstaller (skips anything already there)
REM   3. Compiles app.py into a single TMenu.exe, with TDG's author/description/
REM      version info baked into the exe's Properties (see version_info.txt),
REM      and icon.ico (if that file exists in this folder) compressed
REM      directly into the exe itself two ways: as the exe's own file icon
REM      (--icon, covers Explorer/shortcuts) and as bundled data the app
REM      reads at startup to set its taskbar/alt-tab icon (--add-data) -
REM      no loose .ico file is copied out afterward either way
REM   4. Copies the JSON files the app reads/writes at runtime out to dist\,
REM      next to the exe, so they're editable and persist across runs/updates
REM
REM Result: dist\TMenu.exe (icon compressed inside it) + the json files
REM sitting next to it - that whole dist\ folder is the thing to hand out /
REM move around.
REM ---------------------------------------------------------------------------

setlocal
cd /d "%~dp0"

echo.
echo === Version ===
set "VERSION_INPUT="
set /p VERSION_INPUT="Enter version number (e.g. 15.2.0), or press Enter to keep the current one: "
python build_version.py "%VERSION_INPUT%"
if errorlevel 1 (
    echo.
    echo Couldn't set the version number - see above. Aborting.
    exit /b 1
)

echo.
echo === Installing build dependencies ===
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo pip install failed - see above. Aborting.
    exit /b 1
)

echo.
echo === Cleaning previous build ===
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TMenu.spec del /q TMenu.spec

echo.
echo === Compiling TMenu.exe ===
set "ICON_FLAG="
set "ADDDATA_FLAG="
if exist icon.ico (
    set "ICON_FLAG=--icon icon.ico"
    REM Also bundles icon.ico as data inside the exe itself (separate from
    REM --icon above, which only sets the exe's own file icon) so app.py can
    REM load it at runtime and set it as the window icon - needed for it to
    REM show up in the taskbar/alt-tab, since a frameless window has no
    REM native title bar for Windows to otherwise pull an icon from.
    set "ADDDATA_FLAG=--add-data icon.ico;."
) else (
    echo No icon.ico found in this folder - building without a custom exe icon.
)
pyinstaller --onefile --windowed --name TMenu --version-file version_info.txt %ICON_FLAG% %ADDDATA_FLAG% app.py
if errorlevel 1 (
    echo.
    echo PyInstaller build failed - see above. Aborting.
    exit /b 1
)

echo.
echo === Copying runtime JSON files next to the exe ===
copy /y settings.json dist\ >nul
copy /y theme.json dist\ >nul
copy /y challenge_keys.json dist\ >nul
copy /y challenge_types.json dist\ >nul
REM challenge.json isn't copied anymore - CHALLENGES export/import now go
REM through a Save/Open dialog into a challenge\ folder instead of one fixed
REM file, so there's no single root-level challenge.json for the app to read.

echo.
echo === Done ===
echo dist\TMenu.exe is ready (icon.ico compressed into the exe itself, not
echo a loose file), with settings.json / theme.json / challenge*.json
echo sitting next to it. Hand out the whole dist\ folder together.
endlocal

