"""
state.py
========
One shared PS3MAPI instance plus connection/attach status, created once in
app.py and passed into every tab's build() function. Keeps the tabs from
each needing their own connection and lets any tab check "are we ready to
read/write memory yet" the same way.

`on_attach` is a list of no-arg callables that connection_core.py's
do_connect_and_attach runs (via notify_attached()) right after a successful
attach - both a manual CONNECT click and startup auto-connect go through
that same code path, so either one fires these. It runs on connection_tab's
background connect thread, not the GUI thread, so a callback that does its
own blocking I/O never freezes the UI. A callback that touches Qt widgets
directly would NOT be safe here - see gui_refresh.py's on_attach_refresh(),
which every tab that needs to instantly re-read memory the moment attach
succeeds (toggleables_tab.py's bold-if-on buttons, field_widgets.py's
prefill-if-nondefault boxes, visuals_tab.py's HUD box) registers through
instead of appending to this list directly, since it bridges back onto the
GUI thread the same way binds_keyboard.py already does for hotkey firing.
"""

import ps3mapi


class AppState:
    def __init__(self):
        self.ps3 = ps3mapi.PS3MAPI()
        self.ip = ""
        self.connected = False
        self.attached = False
        self.attached_name = ""
        self.on_attach = []

    @property
    def pid(self) -> int:
        return self.ps3.Process.Process_Pid

    def is_ready(self) -> bool:
        """True once connected AND attached - safe to read/write memory."""
        return self.connected and self.attached

    def notify_attached(self):
        """Runs every registered on_attach callback. Never lets one
        callback's exception stop the rest, or bubble up into the connect
        worker thread that called this."""
        for cb in list(self.on_attach):
            try:
                cb()
            except Exception:
                pass
