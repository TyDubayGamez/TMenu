"""
app.py
======
Entry point. Builds the window and tab strip (TsUI_qt), then hands each tab
frame off to its own module to fill in - the UI framework and the PS3MAPI
logic never live in the same file. Run this file directly.

    python app.py

The window is not user-resizable (no size grip, no maximize button at all)
- instead it auto-fits itself to whatever tab or subtab is currently on
screen, so it never clips content and never has to be dragged bigger by
hand. Tabs with a
lot of subtabs (EDIT SKATER, TOGGLEABLES) have their own VIEW ALL button
that opens a separate, fixed-size popup window showing every one of that
tab's subtabs at once (see TsUI_qt.show_subtab_gallery) - that popup is its
own bounded rectangle with a scrollbar, so it never has to grow the main
window to cover most of the screen just to show everything.

Colors/fonts come from TsUI_qt's hardcoded defaults unless a theme.json
sits next to TsUI_qt.py, in which case it overrides them - see theme.json
in this folder for the format (or SETTINGS' "New Default Theme.json" button,
which (re)writes one matching the hardcoded defaults exactly, as a starting
point to edit from), or delete it to fall back to the defaults. settings.json
can also point at a different theme.json to load instead (the 'theme_path'
key), applied at startup and re-applied live from SETTINGS.

LIVE-APPLYING SETTINGS: applying a different theme changes things that are
baked into widgets at construction time (QSS), so it can't just be
re-styled on the existing widgets - it needs a rebuild. Rather than restart
the whole process for that (fragile - re-exec'ing inside a live Qt event
loop, or spawning a whole new OS process, both have more ways to go wrong),
`main()` keeps the actual "build everything" step in its own function and
hands SETTINGS a `rebuild_tabs` callback that builds a brand new window,
shows it, and only then closes the old one. `state` (the PS3MAPI connection)
and `settings` are created once in `main()` and threaded through every
rebuild, so a rebuild never drops the current connection or asks the user to
reconnect. Qt's parent/child ownership takes care of the rest - anything
parented to the old window (its QTimers included, e.g. Clothing Lock's lock
timer) gets torn down along with it once it's closed, so nothing from the
old window keeps running in the background after a rebuild.
"""

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

# icon.ico is bundled into the exe as PyInstaller data (see build.bat's
# --add-data) specifically so it's available here at runtime to set as the
# window icon - --icon alone (also in build.bat) only bakes it in as the
# exe's file icon (Explorer/shortcuts), it doesn't make a frameless window
# show it in the taskbar/alt-tab on its own.
WINDOW_ICON_PATH = resource_path("icon.ico")


def _refit_on_switch(tab_control, win):
    """
    Make a MetroTabControl resize the window to fit whatever tab it just
    switched to. Wraps .set() instead of editing TsUI_qt.py, since tab
    switching is generic UI behavior but "resize the app window" is specific
    to this tool.
    """
    original_set = tab_control.set

    def wrapped(name):
        original_set(name)
        win.fit_to_content()

    tab_control.set = wrapped


def build_window(state, settings, binds_runtime, rebuild_tabs):
    """
    Builds one complete window (tabs, subtabs, everything) against the given
    (already-created, persistent) `state`/`settings`/`binds_runtime`, and
    returns (win, connection). Called once at startup, and again by
    `rebuild_tabs` below whenever a setting that needs a fresh build changes.

    `connection` is connection_tab's returned handle dict - only used by
    main() right after the very first build, to fire auto-connect once.
    """
    win = MetroForm("TMenu Skate 3 RTM", heading="TMenu Skate 3 RTM", size=DEFAULT_SIZE,
                     style=TsUI_qt.ACTIVE_STYLE, theme=TsUI_qt.ACTIVE_THEME,
                     resizable=False, maximizable=False,
                     icon=WINDOW_ICON_PATH if os.path.isfile(WINDOW_ICON_PATH) else None)

    def fit_to_content():
        # DEFAULT_SIZE is the floor - the window never shrinks below it, it
        # only grows past it when the active tab/subtab needs more room.
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

    # Load the tool's own settings first - a theme_path here overrides the
    # theme.json sitting next to TsUI_qt.py before any widget is built (QSS is
    # baked in at construction time, so the theme must be picked before then).
    settings = AppSettings()
    if settings.theme_path:
        TsUI_qt.load_theme(settings.theme_path)

    # Created once, outside build_window, so a rebuild never touches the
    # live PS3MAPI connection or asks the user to reconnect.
    state = AppState()

    # Same idea for BINDS: its keyboard hotkeys are a process-wide OS hook
    # that must not be recreated on every rebuild - see binds_runtime.py's
    # docstring for why.
    binds_runtime = BindsRuntime(state)

    # Holds the current window so rebuild_tabs (below) can close the old one
    # only after the new one is already up. A plain mutable dict instead of
    # a bare variable so the nested functions can update it via closure.
    current = {}

    def rebuild_tabs():
        old_win = current.get("win")
        new_win, _connection = build_window(state, settings, binds_runtime, rebuild_tabs)
        current["win"] = new_win
        new_win.show()
        new_win.fit_to_content()
        if old_win is not None:
            # Closing (then deleting) the old window takes everything
            # parented to it down with it - including any QTimers it owns
            # (e.g. the Clothing Lock timer) - so nothing from the old
            # window keeps running once this returns. Close before delete,
            # and only after the new window is already shown, so Qt never
            # sees "zero windows open" and quits the whole app in between.
            old_win.close()
            old_win.deleteLater()
        # Deliberately not re-firing auto-connect here - a rebuild only
        # happens from a setting change, by which point the user is either
        # already connected (state carries over, nothing to redo) or chose
        # not to be. Auto-connect is a startup-only thing, fired once below.

    win, connection = build_window(state, settings, binds_runtime, rebuild_tabs)
    current["win"] = win
    win.fit_to_content()  # size correctly for the CONNECTION tab shown on launch
    win.show()
    connection["auto_connect"]()  # no-op unless settings.auto_connect + last_ip are set
    app.exec()


if __name__ == "__main__":
    main()