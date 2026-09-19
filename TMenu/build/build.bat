@echo off
REM ---------------------------------------------------------------------------
REM build.bat
REM =========
REM Run this ON WINDOWS, from inside this folder (build\ - double-click it, or
REM open a command prompt here and run `build.bat`). PyInstaller cannot
REM cross-compile, so the .exe has to be built on the OS it's meant to run on
REM - hence this being a .bat rather than something Claude could run for you.
REM
REM Repo layout this expects (see this repo's README for the full picture):
REM   <repo root>\app.py, ...all the other .py files...
REM   <repo root>\data\settings.json, theme.json, challenge_types.json, ...
REM   <repo root>\build\  <- this file, TMenu.spec, build_version.py,
REM                          version.txt, version_info.txt, requirements.txt,
REM                          icon.ico
REM
REM What it does:
REM   1. Asks what version number to stamp on this build (or keeps the last
REM      one used if you just hit Enter) and writes it into version_info.txt
REM      via build_version.py (both stay right here in build\)
REM   2. Installs PySide6 / requests / pyinstaller (skips anything already there)
REM   3. Compiles ..\app.py into a single TMenu.exe, with TDG's author/
REM      description/version info baked into the exe's Properties (see
REM      version_info.txt), and icon.ico (if that file exists in this folder)
REM      compressed directly into the exe itself two ways: as the exe's own
REM      file icon (--icon, covers Explorer/shortcuts) and as bundled data the
REM      app reads at startup - into a build\ subfolder inside the bundle, to
REM      match app_paths.resource_path("build", "icon.ico") - to set its
REM      taskbar/alt-tab icon (--add-data). No loose .ico file is copied out
REM      afterward either way.
REM   4. Copies the JSON files the app reads/writes at runtime into a data\
REM      subfolder next to the exe (mirroring this repo's own data\ folder),
REM      so they're editable and persist across runs/updates
REM
REM PyInstaller's own intermediate work folder and the final output both land
REM OUTSIDE build\ (one level up, at the repo root, via --workpath/--distpath
REM below) rather than inside it - build\ here is this repo's checked-in
REM build *tooling*, not a throwaway PyInstaller work directory, and PyInstaller
REM defaults to a folder literally named "build" for its own scratch space,
REM which would otherwise collide with this one.
REM
REM Result: ..\dist\TMenu.exe (icon compressed inside it) + ..\dist\data\ next
REM to it - that whole dist\ folder (created next to build\, not inside it) is
REM the thing to hand out / move around.
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
if exist ..\_pyinstaller_work rmdir /s /q ..\_pyinstaller_work
if exist ..\dist rmdir /s /q ..\dist
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
    REM native title bar for Windows to otherwise pull an icon from. Landed at
    REM "build\icon.ico" inside the bundle to match app_paths.resource_path's
    REM lookup ("build", "icon.ico") - see app.py's WINDOW_ICON_PATH.
    set "ADDDATA_FLAG=--add-data icon.ico;build"
) else (
    echo No icon.ico found in this folder - building without a custom exe icon.
)
pyinstaller --onefile --windowed --name TMenu --version-file version_info.txt ^
    --workpath ..\_pyinstaller_work --distpath ..\dist ^
    %ICON_FLAG% %ADDDATA_FLAG% ..\app.py
if errorlevel 1 (
    echo.
    echo PyInstaller build failed - see above. Aborting.
    exit /b 1
)

echo.
echo === Copying runtime JSON files next to the exe ===
if not exist ..\dist\data mkdir ..\dist\data
copy /y ..\data\settings.json ..\dist\data\ >nul
copy /y ..\data\theme.json ..\dist\data\ >nul
copy /y ..\data\challenge_keys.json ..\dist\data\ >nul
copy /y ..\data\challenge_types.json ..\dist\data\ >nul
REM challenge.json isn't copied anymore - CHALLENGES export/import now go
REM through a Save/Open dialog into a challenge\ folder instead of one fixed
REM file, so there's no single fixed challenge.json for the app to read.

echo.
echo === Done ===
echo ..\dist\TMenu.exe is ready (icon.ico compressed into the exe itself, not
echo a loose file), with a data\ folder (settings.json / theme.json /
echo challenge*.json) sitting next to it. Hand out the whole dist\ folder
echo together - it's created next to build\, not inside it.
endlocal
