"""
binds_keyboard.py
==================
Thin wrapper around the third-party `keyboard` package for BINDS' KEYBOARD
subtab. Requires `keyboard` (added to requirements.txt) - it's what gives
this system-wide hotkeys instead of ones that only work while TMenu's own
window has focus, which matters here since the whole point is a bind that
still fires while attention (and window focus) is on the game/TV, not on
TMenu.

Two things live here:

  - KeyboardBindRouter - keeps at most one system-wide hotkey registered per
    action id, so re-binding an action cleanly replaces its old hotkey
    instead of stacking a second one underneath it. `keyboard`'s hook fires
    its callback on its own internal thread; that callback only ever emits
    a Qt signal (never touches widgets directly), so the actual action runs
    back on the GUI thread where it's safe to update labels/status text.

    This is meant to be created ONCE (see binds_runtime.py) and reused
    across tab rebuilds - the hotkeys it registers are a process-wide OS
    hook, not a Qt object, so a rebuilt BINDS tab must reuse the same
    router rather than creating a second one (which would leave the old
    hotkeys still firing into now-destroyed widgets).

  - capture_next_key() - the "click Set Bind, then press a key" flow.
    Blocks (on a background thread) until a key/chord is pressed, then
    reports the hotkey string back on the GUI thread.

On Windows this does not need TMenu to run elevated for a normal game/app -
but if TMenu is ever run as administrator while the game window isn't (or
the reverse), Windows won't deliver key events across that privilege
boundary and a bind will silently stop firing. Worth knowing if one ever
"stops working" for no visible reason.
"""

import threading

from PySide6.QtCore import QObject, Signal

import keyboard


class _Signals(QObject):
    captured = Signal(str)
    fired = Signal(str)  # action_id


class KeyboardBindRouter:
    def __init__(self):
        self.signals = _Signals()
        self._registered = {}  # action_id -> hotkey string
        self._callbacks = {}  # action_id -> callable() -> None, run on the GUI thread
        self._capture_cb = None  # set while a capture_next_key() call is pending

        self.signals.fired.connect(self._dispatch)
        self.signals.captured.connect(self._on_captured)

    # -- firing ------------------------------------------------------------

    def _dispatch(self, action_id):
        cb = self._callbacks.get(action_id)
        if cb:
            cb()

    def set_bind(self, action_id: str, hotkey: str, on_fire):
        """Registers (or replaces) action_id's hotkey. on_fire is called
        with no args, on the GUI thread, every time it fires."""
        self.clear_bind(action_id)
        if not hotkey:
            return

        def _handler():
            # Runs on keyboard's own thread - only ever touch Qt via the
            # signal, never call on_fire() directly from here.
            self.signals.fired.emit(action_id)

        try:
            keyboard.add_hotkey(hotkey, _handler, suppress=False)
        except Exception:
            return  # bad/unsupported hotkey string - nothing gets registered

        self._registered[action_id] = hotkey
        self._callbacks[action_id] = on_fire

    def clear_bind(self, action_id: str):
        hotkey = self._registered.pop(action_id, None)
        self._callbacks.pop(action_id, None)
        if hotkey:
            try:
                keyboard.remove_hotkey(hotkey)
            except (KeyError, ValueError):
                pass

    def clear_all(self):
        for action_id in list(self._registered):
            self.clear_bind(action_id)

    # -- capturing a new bind -----------------------------------------------

    def _on_captured(self, hotkey):
        cb = self._capture_cb
        self._capture_cb = None
        if cb:
            cb(hotkey)

    def capture_next_key(self, on_captured):
        """Blocks on a background thread until the user presses a key/chord,
        then calls on_captured(hotkey_string) back on the GUI thread. Only
        one capture can be pending at a time - starting a new one replaces
        whatever callback an earlier still-pending one would have used."""
        self._capture_cb = on_captured

        def worker():
            try:
                hotkey = keyboard.read_hotkey(suppress=False)
            except Exception:
                hotkey = ""
            self.signals.captured.emit(hotkey)

        threading.Thread(target=worker, daemon=True).start()
