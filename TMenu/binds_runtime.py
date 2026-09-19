"""
binds_runtime.py
=================
Everything about BINDS that must survive a tab rebuild. SETTINGS > changing
the theme calls app.py's rebuild_tabs(), which tears the whole window down
and builds a fresh one - `state` and `settings` are already threaded through
that (see app.py's docstring); BindsRuntime is created the same way, once in
main(), and passed into every build_window() call so BINDS doesn't lose its
binds (or briefly stop firing them) every time an unrelated setting changes.

Why this can't just live on the BINDS tab widgets like most tab state does:
hotkeys registered via the `keyboard` package are a process-wide OS hook,
not a Qt object - closing the old window doesn't unregister them. A fresh
KeyboardBindRouter built on every rebuild would leave the old one's hotkeys
still firing, now pointing at destroyed widgets.

Holds:
  - `config`          - BindsConfig (keyboard_binds), loaded from
                         binds.json at construction.
  - `keyboard_router`  - KeyboardBindRouter (binds_keyboard.py).

(An earlier version also held a CONTROLLER-subtab poller and a live
AOB-scanned button-address map. That subtab was removed - KEYBOARD is the
only bind source now - so there's nothing here anymore that needs an
on-attach hook.)
"""

from binds_config import BindsConfig
from binds_keyboard import KeyboardBindRouter


class BindsRuntime:
    def __init__(self, state):
        self.config = BindsConfig.load()
        self.keyboard_router = KeyboardBindRouter()
