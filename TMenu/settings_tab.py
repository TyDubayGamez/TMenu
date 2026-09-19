"""
settings_tab.py
===============
Builds the SETTINGS tab, which edits the tool's own settings.json live while
the app is running. Controls:

  - Theme file: a path (typed or picked with BROWSE) to a theme.json the user
    wants to link to. APPLY THEME reloads that theme and saves the path.

  - New Default Theme.json: exports a theme.json - via a Save dialog
    defaulted into the theme/ folder next to the app, filename theme.json
    (rename it, or pick a different folder, before confirming) - containing
    the hardcoded defaults in the same schema APPLY THEME reads. A clean
    starting point to edit from, not something that changes the active theme
    by itself. Existing files at the chosen path are overwritten.

Changing the theme is written back to settings.json immediately, and applied
live via the `rebuild_tabs` callback (app.py builds a fresh window behind
the scenes and swaps it in) rather than restarting the whole tool -
restarting the OS process is only a fallback for if this tab somehow gets
built without that callback.

(There used to be a "compact subtabs" layout switch here too, which rebuilt
the whole window flattened out to show every subtab at once, and later a
VIEW ALL button on edit_skater_tab.py/toggleables_tab.py that opened a
separate popup gallery instead. Both are gone now - just the normal inline
subtab bar on those tabs.)

app.py owns the single AppSettings instance and passes it in here; a
`rebuild_tabs` callback is also passed so APPLY THEME can re-theme the
whole window live.
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog, QApplication,
)

import TsUI_qt
from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox
from app_paths import base_dir, export_dir, export_save_path
import menu_config


def _restart_app():
    """
    Fallback only - used if a live rebuild isn't available (rebuild_tabs
    wasn't passed in, e.g. if this tab is ever built standalone). Spawns the
    detached restart.py/restart.bat helper (see those files for why: an
    external process reliably outlives this one and waits for it to fully
    exit before launching the replacement, which re-exec'ing in-process via
    os.execl inside a live Qt event loop could not do reliably) and asks the
    app to quit; the helper handles bringing a fresh instance up once this
    process is gone.
    """
    here = base_dir()
    pid = str(os.getpid())
    frozen = getattr(sys, "frozen", False)

    def do_restart():
        try:
            if frozen:
                # Onefile build: there's no external restart.py/restart.bat
                # sitting next to the exe to spawn (they're bundled inside
                # it, not on disk) - relaunch the exe itself directly.
                flags = subprocess.DETACHED_PROCESS if sys.platform.startswith("win") else 0
                subprocess.Popen([sys.executable], cwd=here, creationflags=flags)
            elif sys.platform.startswith("win"):
                subprocess.Popen(
                    [os.path.join(here, "restart.bat"), pid],
                    cwd=here, creationflags=subprocess.DETACHED_PROCESS,
                )
            else:
                subprocess.Popen([sys.executable, os.path.join(here, "restart.py"), pid], cwd=here)
        except OSError:
            pass  # nothing more we can do - the window is closing either way
        QApplication.quit()

    QTimer.singleShot(150, do_restart)


def build(parent_tab, win, state, settings, rebuild_tabs=None):
    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 30, 0, 0)

    group = MetroGroupBox(parent_tab, title="Settings")
    group.setFixedWidth(360)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    # -- Theme file path -------------------------------------------------
    theme_lbl = MetroLabel(group, text="Theme file (theme.json)")
    group.add(theme_lbl)

    path_row = QWidget(group)
    path_row.setStyleSheet("background: transparent;")
    path_row_layout = QHBoxLayout(path_row)
    path_row_layout.setContentsMargins(0, 0, 0, 0)
    path_row_layout.setSpacing(8)
    path_box = MetroTextBox(path_row, width=230, height=26)
    path_box.setPlaceholderText("empty = default theme.json")
    path_box.setText(settings.theme_path)
    browse_btn = MetroButton(path_row, text="BROWSE", width=90, height=26)
    path_row_layout.addWidget(path_box)
    path_row_layout.addWidget(browse_btn)
    group.add(path_row)

    apply_theme_btn = MetroButton(group, text="APPLY THEME", width=328, height=32)
    group.add(apply_theme_btn)

    new_default_btn = MetroButton(group, text="NEW DEFAULT THEME.JSON", width=328, height=32)
    group.add(new_default_btn)

    group.add(status_lbl)

    # -- callbacks -------------------------------------------------------

    def on_browse():
        path, _ = QFileDialog.getOpenFileName(
            browse_btn, "Select theme.json", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            path_box.setText(path)

    def on_apply_theme():
        settings.theme_path = path_box.text().strip()
        # Reload TsUI_qt's active theme from the linked file (empty falls back
        # to the theme.json next to TsUI_qt.py, or the built-in defaults).
        applied = TsUI_qt.load_theme(settings.theme_path or None)
        saved = settings.save()
        if not saved:
            status_lbl.setText("Theme reloaded, but settings.json couldn't be written.")
            return

        note = "Theme applied." if applied else "Theme cleared (using defaults)."
        if rebuild_tabs is not None:
            status_lbl.setText(note)
            rebuild_tabs()
        else:
            status_lbl.setText(note + " Restart to fully re-skin existing widgets.")

    def on_new_default_theme():
        # Exporting a theme now always goes through a Save dialog aimed at
        # the theme/ folder (created next to the exe/app.py if it isn't
        # there yet) with "theme.json" filled in as the name - the user can
        # rename it, or pick somewhere else entirely, before confirming.
        target = export_save_path(
            new_default_btn, "theme", "theme.json",
            "Save Theme", "JSON Files (*.json)",
        )
        if not target:
            return  # user cancelled the save dialog
        ok = TsUI_qt.write_default_theme_json(target)
        if ok:
            status_lbl.setText(f"Wrote default theme to {target}.")
        else:
            status_lbl.setText(f"Couldn't write to {target}.")

    browse_btn.clicked.connect(on_browse)
    apply_theme_btn.clicked.connect(on_apply_theme)
    new_default_btn.clicked.connect(on_new_default_theme)

    # -- Config (save/load every TOGGLEABLES/ADJUSTABLES/VISUALS/PARK value) -
    config_group = MetroGroupBox(parent_tab, title="Config")
    config_group.setFixedWidth(360)
    layout.addWidget(config_group, alignment=Qt.AlignHCenter)

    save_config_btn = MetroButton(config_group, text="SAVE CONFIG", width=328, height=32)
    config_group.add(save_config_btn)

    load_config_btn = MetroButton(config_group, text="LOAD CUSTOM CONFIG", width=328, height=32)
    config_group.add(load_config_btn)

    config_status_lbl = MetroLabel(config_group, text="")
    config_status_lbl.setAlignment(Qt.AlignCenter)
    config_status_lbl.setWordWrap(True)
    config_group.add(config_status_lbl)

    def on_save_config():
        path = export_save_path(
            config_group, "config", "config.json",
            "Save Config", "Config Files (*.json)",
        )
        if not path:
            return  # user cancelled the save dialog
        ok, message = menu_config.save_config(state, path)
        config_status_lbl.setText(message)

    def on_load_config():
        # Opens in config/ by default, since that's where SAVE CONFIG puts
        # exports now - still a normal Open dialog, so the user can browse
        # anywhere else a config.json might be sitting.
        path, _ = QFileDialog.getOpenFileName(
            config_group, "Load Custom Config", export_dir("config"), "Config Files (*.json)"
        )
        if not path:
            return
        ok, message = menu_config.load_config(state, path)
        config_status_lbl.setText(message)

    save_config_btn.clicked.connect(on_save_config)
    load_config_btn.clicked.connect(on_load_config)

    # -- Reset Everything (every toggle -> OFF, every field -> its default) -
    reset_group = MetroGroupBox(parent_tab, title="Reset")
    reset_group.setFixedWidth(360)
    layout.addWidget(reset_group, alignment=Qt.AlignHCenter)

    reset_note = MetroLabel(reset_group, text="Resets all changed values.")
    reset_note.setAlignment(Qt.AlignCenter)
    reset_group.add(reset_note)

    reset_btn = MetroButton(reset_group, text="RESET EVERYTHING", width=328, height=32)
    reset_group.add(reset_btn)

    reset_status_lbl = MetroLabel(reset_group, text="")
    reset_status_lbl.setAlignment(Qt.AlignCenter)
    reset_status_lbl.setWordWrap(True)
    reset_group.add(reset_status_lbl)

    def on_reset_clicked():
        ok, message = menu_config.reset_all(state)
        reset_status_lbl.setText(message)

    reset_btn.clicked.connect(on_reset_clicked)

    return group
