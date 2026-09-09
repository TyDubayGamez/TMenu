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

    # firing

    def _dispatch(self, action_id):
        cb = self._callbacks.get(action_id)
        if cb:
            cb()

    def set_bind(self, action_id: str, hotkey: str, on_fire):
        # registers (or replaces) action_id's hotkey, on_fire runs on the GUI thread
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

    # capturing a new bind

    def _on_captured(self, hotkey):
        cb = self._capture_cb
        self._capture_cb = None
        if cb:
            cb(hotkey)

    def capture_next_key(self, on_captured):
        # waits on a background thread for a keypress, then calls
        # on_captured(hotkey_string) back on the GUI thread
        self._capture_cb = on_captured

        def worker():
            try:
                hotkey = keyboard.read_hotkey(suppress=False)
            except Exception:
                hotkey = ""
            self.signals.captured.emit(hotkey)

        threading.Thread(target=worker, daemon=True).start()
