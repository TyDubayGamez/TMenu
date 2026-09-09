from PySide6.QtCore import QObject, Signal


class _RefreshBridge(QObject):
    fire = Signal()


def on_attach_refresh(state, anchor, refresh):
    # runs refresh() on the GUI thread every time state attaches,
    # and once immediately if already attached. anchor keeps the
    # bridge object alive (usually the widget refresh belongs to)
    bridge = _RefreshBridge(anchor)

    def _safe_refresh():
        try:
            refresh()
        except Exception:
            pass

    bridge.fire.connect(_safe_refresh)
    state.on_attach.append(bridge.fire.emit)

    # keep the bridge alive for as long as anchor is
    if not hasattr(anchor, "_gui_refresh_bridges"):
        anchor._gui_refresh_bridges = []
    anchor._gui_refresh_bridges.append(bridge)

    if state.is_ready():
        _safe_refresh()
