"""
binds_config.py
================
Load/save for BINDS' own binds.json (lives next to app.py / settings.json -
see app_paths.base_dir()). Same defensive style as settings.py: a missing,
broken, or partial file just falls back to "nothing bound" rather than
crashing, and unknown/renamed action ids are silently dropped instead of
carried forward as dead entries.

Every action lives under an id of the form "<group_key>:<item_key>" -
see binds_data.BIND_GROUPS/get_item() for what those mean and how the UI
(binds_tab.py) builds one.

Shape on disk:
    {
        "toggle_binds": {
            "onboard_toggle:no_fall_damage": "ctrl+f9",
            "debug:debug_cam": "f9"
        },
        "value_binds": {
            "adjustables_onboard:ollie_height": [
                {"hotkey": "1", "value": 5.0},
                {"hotkey": "2", "value": 12.0}
            ]
        }
    }

toggle_binds is one hotkey per action - re-binding replaces the old one,
same as before. value_binds is different: an adjustable/visual field can
have several hotkeys at once, each jumping straight to its own stored
value - there's no separate "reset" bind; pressing a value hotkey again
while that field is already sitting at that exact value puts it back to
its own vanilla default instead (see binds_tab.py's make_value_fire_handler
for that toggle-back logic - this module only stores the value each hotkey
jumps to, not any "currently applied" state, which is re-derived from
memory every time the hotkey fires). Nothing here actually fires these -
see binds_runtime.py's KeyboardBindRouter for that; this module is purely
the on-disk representation plus validation against binds_data's registry (a
saved id that no longer exists, or whose group changed kind, is dropped
rather than kept around as a dead entry that can never fire).

EXPORT/IMPORT (the BINDS tab's own buttons, not auto-save) share this same
class: export_to() just calls save() at a different path, import_from()
loads that path's content into memory (validating the same way normal load
does) and then writes it back out to the real binds.json so the import
sticks around on the next launch too.
"""

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
    """Validates one value_binds[action_id] list, dropping anything
    malformed rather than rejecting the whole entry over one bad row."""
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
    """In-memory binds, loaded from / saved to binds.json."""

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
        """(Re)reads self.path into memory. Returns False (leaving
        everything empty) if the file is missing/broken - never raises."""
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
        """Writes the in-memory binds back out as pretty JSON. Returns True
        on success, False if the write failed (permissions/disk/etc)."""
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
        """Loads `path` (validated the same way normal load is), and on
        success both replaces the in-memory binds AND persists them to the
        real binds.json so the import survives past this session."""
        old_path = self.path
        self.path = path
        ok = self.reload()
        self.path = old_path
        if ok:
            self.save()
        return ok
