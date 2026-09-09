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
    # fallback used if a live rebuild isn't available - spawns the detached
    # restart.py/restart.bat helper and quits, the helper relaunches a fresh instance
    here = base_dir()
    pid = str(os.getpid())
    frozen = getattr(sys, "frozen", False)

    def do_restart():
        try:
            if frozen:
                # onefile build has no external restart.py/restart.bat to spawn,
                # so relaunch the exe itself directly
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

    # Theme file path
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

    # callbacks

    def on_browse():
        path, _ = QFileDialog.getOpenFileName(
            browse_btn, "Select theme.json", "", "JSON Files (*.json);;All Files (*)"
        )
        if path:
            path_box.setText(path)

    def on_apply_theme():
        settings.theme_path = path_box.text().strip()
        # empty path falls back to the theme.json next to TsUI_qt.py, or the built-in defaults
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
        # opens a Save dialog aimed at the theme/ folder with theme.json filled in
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

    # config - save/load every TOGGLEABLES/ADJUSTABLES/VISUALS/PARK value
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
        # opens in config/ by default since that's where SAVE CONFIG puts exports
        path, _ = QFileDialog.getOpenFileName(
            config_group, "Load Custom Config", export_dir("config"), "Config Files (*.json)"
        )
        if not path:
            return
        ok, message = menu_config.load_config(state, path)
        config_status_lbl.setText(message)

    save_config_btn.clicked.connect(on_save_config)
    load_config_btn.clicked.connect(on_load_config)

    # reset everything - every toggle to OFF, every field to its default
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
