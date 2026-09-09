import json
import os

from app_paths import base_dir
from binds_data import get_item

BINDS_FILE = os.path.join(base_dir(), "binds.json")


def _valid_toggle_action(action_id: str) -> bool:
    group_key, _, item_key = action_id.partition(":")
    group, item = get_item(group_key, item_key)
    return group is not None and item is not None and group["kind"] == "toggle"


def _valid_value_action(action_id: str) -> bool:
    group_key, _, item_key = action_id.partition(":")
    group, item = get_item(group_key, item_key)
    return group is not None and item is not None and group["kind"] == "value"


def _clean_value_rows(rows) -> list:
    # drops malformed rows instead of rejecting the whole entry
    cleaned = []
    if not isinstance(rows, list):
        return cleaned
    for row in rows:
        if not isinstance(row, dict):
            continue
        hotkey = row.get("hotkey")
        value = row.get("value")
        if isinstance(hotkey, str) and hotkey and isinstance(value, (int, float)):
            cleaned.append({"hotkey": hotkey, "value": float(value)})
    return cleaned


class BindsConfig:
    # in-memory binds, loaded from / saved to binds.json
    def __init__(self, path=None):
        self.path = path or BINDS_FILE
        self.toggle_binds = {}   # action_id -> hotkey string
        self.value_binds = {}    # action_id -> [{"hotkey": str, "value": float}, ...]

    @classmethod
    def load(cls, path=None):
        cfg = cls(path)
        cfg.reload()
        return cfg

    def reload(self) -> bool:
        # reads self.path into memory, returns False if missing/broken
        self.toggle_binds = {}
        self.value_binds = {}

        if not os.path.isfile(self.path):
            return False

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False

        toggle_binds = data.get("toggle_binds", {})
        if isinstance(toggle_binds, dict):
            self.toggle_binds = {
                k: v for k, v in toggle_binds.items()
                if _valid_toggle_action(k) and isinstance(v, str) and v
            }

        value_binds = data.get("value_binds", {})
        if isinstance(value_binds, dict):
            self.value_binds = {
                k: _clean_value_rows(v) for k, v in value_binds.items() if _valid_value_action(k)
            }

        return True

    def save(self, path=None) -> bool:
        # writes the in-memory binds back out as pretty JSON
        target = path or self.path
        data = {
            "toggle_binds": self.toggle_binds,
            "value_binds": self.value_binds,
        }
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            return True
        except OSError:
            return False

    def export_to(self, path) -> bool:
        return self.save(path)

    def import_from(self, path) -> bool:
        # loads path, and on success saves it to the real binds.json too
        old_path = self.path
        self.path = path
        ok = self.reload()
        self.path = old_path
        if ok:
            self.save()
        return ok
