"""
gui_refresh.py
================
One small helper: run a callback on the GUI thread every time `state`
attaches (state.py's on_attach list) - immediately if already attached, and
again for every future attach.

state.on_attach callbacks fire on connection_tab's background connect
thread (see state.py's docstring), so touching Qt widgets directly from one
is not safe. binds_keyboard.py already solves this exact problem for
hotkey firing by only ever emitting a Qt Signal from the background thread
and doing the real work in a slot connected to it (Qt queues that dispatch
back onto the GUI thread automatically) - on_attach_refresh() is that same
pattern, generalized so every tab that wants an "instantly re-read
everything on attach" refresh (toggle bold-state, adjustable/visual field
prefill - see toggleables_tab.py / field_widgets.py) doesn't need to hand-rig
its own QObject/Signal pair.

    from gui_refresh import on_attach_refresh

    def refresh():
        ...read memory, update widgets...

    on_attach_refresh(state, group, refresh)  # group = any long-lived
                                               # widget to anchor the bridge
                                               # to, so it isn't garbage
                                               # collected out from under
                                               # the state.on_attach entry

`refresh` is also called once immediately (synchronously, on whatever
thread called on_attach_refresh - always the GUI thread, since tab build()
functions run there) if `state` is already attached, so a tab built AFTER
attach (e.g. a SETTINGS theme-change rebuild while already connected) still
shows correct values right away instead of only on the next attach.

Exceptions from `refresh` are swallowed the same way state.notify_attached()
already swallows exceptions from every other on_attach callback - a
destroyed widget from an old, torn-down window (see app.py's rebuild_tabs)
failing quietly here is expected and harmless, not a bug to surface.
"""

from PySide6.QtCore import QObject, Signal


class _RefreshBridge(QObject):
    fire = Signal()


def on_attach_refresh(state, anchor, refresh):
    """Wires `refresh` (no-arg callable) up to fire on the GUI thread
    every time `state` attaches, and calls it once immediately if already
    attached. `anchor` just needs to be a widget that outlives the need for
    this refresh (its parent tab/group is normal) - the bridge is stashed
    on it so it isn't garbage collected once this function returns."""
    bridge = _RefreshBridge(anchor)

    def _safe_refresh():
        try:
            refresh()
        except Exception:
            pass

    bridge.fire.connect(_safe_refresh)
    state.on_attach.append(bridge.fire.emit)

    # Keep the bridge alive for as long as `anchor` is (a plain Python
    # attribute reference is enough - anchor being a QObject with children
    # doesn't matter here, this is just GC bookkeeping).
    if not hasattr(anchor, "_gui_refresh_bridges"):
        anchor._gui_refresh_bridges = []
    anchor._gui_refresh_bridges.append(bridge)

    if state.is_ready():
        _safe_refresh()
