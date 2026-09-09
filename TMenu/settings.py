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
    # in-memory settings, loaded from / saved to settings.json
    def __init__(self, path=None):
        self.path = path or SETTINGS_FILE
        self.theme_path = DEFAULTS["theme_path"]
        self.last_ip = DEFAULTS["last_ip"]
        self.auto_connect = DEFAULTS["auto_connect"]
        self.load()

    def load(self):
        # read settings.json, falling back to defaults if missing or broken
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
        # write settings back to settings.json, returns True on success
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
