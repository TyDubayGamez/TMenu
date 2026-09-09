from PySide6.QtWidgets import QVBoxLayout

import os

import TsUI_qt
from TsUI_qt import MetroForm, MetroTabControl
from app_paths import resource_path

from state import AppState
from settings import AppSettings
import connection_tab
import edit_skater_tab
import toggleables_tab
import visuals_tab
import adjustables_tab
import misc_tab
import settings_tab
import online_tab
import park_tab
import save_tab
import binds_tab
from binds_runtime import BindsRuntime

TAB_NAMES = ["CONNECTION", "ONLINE", "ADJUSTABLES", "TOGGLEABLES", "VISUALS", "MISC", "EDIT SKATER", "PARK", "SAVE", "BINDS", "SETTINGS"]

DEFAULT_SIZE = (750, 467)

# icon bundled into the exe via PyInstaller, used as the window icon
WINDOW_ICON_PATH = resource_path("icon.ico")


def _refit_on_switch(tab_control, win):
    # makes a MetroTabControl resize the window to fit whatever tab it switched to
    original_set = tab_control.set

    def wrapped(name):
        original_set(name)
        win.fit_to_content()

    tab_control.set = wrapped


def build_window(state, settings, binds_runtime, rebuild_tabs):
    # builds one complete window (tabs, subtabs, everything) and returns
    # (win, connection). called at startup, and again by rebuild_tabs
    # whenever a setting that needs a fresh build changes
    win = MetroForm("TMenu Skate 3 RTM", heading="TMenu Skate 3 RTM", size=DEFAULT_SIZE,
                     style=TsUI_qt.ACTIVE_STYLE, theme=TsUI_qt.ACTIVE_THEME,
                     resizable=False, maximizable=False,
                     icon=WINDOW_ICON_PATH if os.path.isfile(WINDOW_ICON_PATH) else None)

    def fit_to_content():
        # DEFAULT_SIZE is the floor - window never shrinks below it, only grows
        win.layout().activate()
        win.body.layout().activate()
        hint = win.sizeHint()
        width = max(DEFAULT_SIZE[0], hint.width())
        height = max(DEFAULT_SIZE[1], hint.height())
        win.resize(width, height)

    win.fit_to_content = fit_to_content

    body_layout = QVBoxLayout(win.body)
    body_layout.setContentsMargins(0, 0, 0, 0)

    tabs = MetroTabControl(win.body, width=750, height=380)
    body_layout.addWidget(tabs)

    for name in TAB_NAMES:
        tabs.add(name)

    connection = connection_tab.build(tabs.tab("CONNECTION"), win, state, settings)
    online_subtabs = online_tab.build(tabs.tab("ONLINE"), win, state)
    edit_skater_subtabs = edit_skater_tab.build(tabs.tab("EDIT SKATER"), win, state)
    toggleables_subtabs = toggleables_tab.build(tabs.tab("TOGGLEABLES"), win, state)
    visuals_subtabs = visuals_tab.build(tabs.tab("VISUALS"), win, state)
    misc_subtabs = misc_tab.build(tabs.tab("MISC"), win, state)
    park_subtabs = park_tab.build(tabs.tab("PARK"), win, state)
    save_subtabs = save_tab.build(tabs.tab("SAVE"), win, state)
    binds_tab.build(tabs.tab("BINDS"), win, state, binds_runtime)
    settings_tab.build(tabs.tab("SETTINGS"), win, state, settings, rebuild_tabs=rebuild_tabs)
    adjustables_subtabs = adjustables_tab.build(tabs.tab("ADJUSTABLES"), win, state)

    _refit_on_switch(tabs, win)
    _refit_on_switch(online_subtabs, win)
    _refit_on_switch(edit_skater_subtabs, win)
    _refit_on_switch(toggleables_subtabs, win)
    _refit_on_switch(visuals_subtabs, win)
    _refit_on_switch(misc_subtabs, win)
    _refit_on_switch(park_subtabs, win)
    _refit_on_switch(save_subtabs, win)
    _refit_on_switch(adjustables_subtabs, win)

    return win, connection


def main():
    app = MetroForm.app()

    # load settings first - theme has to be picked before any widget is built
    settings = AppSettings()
    if settings.theme_path:
        TsUI_qt.load_theme(settings.theme_path)

    # created once so a rebuild never touches the live connection
    state = AppState()

    # same idea for BINDS - its keyboard hotkeys must not be recreated on rebuild
    binds_runtime = BindsRuntime(state)

    # holds the current window so rebuild_tabs can close the old one after
    # the new one is up (dict so the nested function can update it)
    current = {}

    def rebuild_tabs():
        old_win = current.get("win")
        new_win, _connection = build_window(state, settings, binds_runtime, rebuild_tabs)
        current["win"] = new_win
        new_win.show()
        new_win.fit_to_content()
        if old_win is not None:
            # close old window only after the new one is shown, so Qt
            # never sees zero windows open and quits the app in between
            old_win.close()
            old_win.deleteLater()
        # not re-firing auto-connect here - that's a startup-only thing

    win, connection = build_window(state, settings, binds_runtime, rebuild_tabs)
    current["win"] = win
    win.fit_to_content()  # size correctly for the CONNECTION tab shown on launch
    win.show()
    connection["auto_connect"]()  # no-op unless settings.auto_connect + last_ip are set
    app.exec()

if __name__ == "__main__":
    main()