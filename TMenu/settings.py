"""
settings.py
===========
Loads and saves the tool's own settings.json (next to app.py), separate from
TsUI_qt's theme.json. What lives here:

  - theme_path: an optional path to a theme.json the user wants to link to.
    Empty/missing means "use whatever theme.json (if any) sits next to
    TsUI_qt.py", i.e. the built-in default behaviour is untouched.

  - last_ip: the last IP address that was typed into the CONNECTION tab and
    successfully connected to. Saved automatically so the box can be
    pre-filled next launch.

  - auto_connect: when True, the tool tries to connect (and attach) to
    last_ip automatically on startup, so a returning user doesn't have to
    click CONNECT/ATTACH every time. Defaults to False.

Everything is defensive: a missing file, a broken file, or a file missing
some keys all fall back to the defaults below rather than crashing. save()
writes the current in-memory settings back out as pretty JSON.

The SETTINGS tab edits an AppSettings instance live; app.py owns the single
instance and passes it into the tab builders that care.
"""

import json
import os

from app_paths import base_dir

SETTINGS_FILE = os.path.join(base_dir(), "settings.json")

DEFAULTS = {
    "theme_path": "",
    "last_ip": "",
    "auto_connect": False,
}


class AppSettings:
    """In-memory settings, loaded from / saved to settings.json."""

    def __init__(self, path=None):
        self.path = path or SETTINGS_FILE
        self.theme_path = DEFAULTS["theme_path"]
        self.last_ip = DEFAULTS["last_ip"]
        self.auto_connect = DEFAULTS["auto_connect"]
        self.load()

    def load(self):
        """(Re)read settings.json. Missing/broken/partial files fall back to
        the defaults for whatever they don't provide - never raises."""
        self.theme_path = DEFAULTS["theme_path"]
        self.last_ip = DEFAULTS["last_ip"]
        self.auto_connect = DEFAULTS["auto_connect"]

        if not os.path.isfile(self.path):
            return False

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        if isinstance(data.get("theme_path"), str):
            self.theme_path = data["theme_path"]
        if isinstance(data.get("last_ip"), str):
            self.last_ip = data["last_ip"]
        if isinstance(data.get("auto_connect"), bool):
            self.auto_connect = data["auto_connect"]

        return True

    def save(self):
        """Write current settings back to settings.json. Returns True on
        success, False if the write failed (permissions/disk/etc)."""
        data = {
            "theme_path": self.theme_path,
            "last_ip": self.last_ip,
            "auto_connect": self.auto_connect,
        }
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except OSError:
            return False
