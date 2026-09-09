import json
import struct

from adjustables_data import ON_BOARD_FIELDS, OFF_BOARD_FIELDS
from visuals_data import (
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, SCREEN_FIELDS, WORLD_FIELDS, HUD_FIELDS,
    SCORE_X1_ADDRESS, SCORE_X2_ADDRESS, SCORE_X3_ADDRESS, SCORE_MULTIPLIER_DEFAULT,
    FOG_COLOR_ADDRESS, FOG_COLOR_DEFAULT, SKATER_COLOR_ADDRESS, SKATER_COLOR_DEFAULT,
)
from toggleables_data import (
    ONBOARD_TOGGLES, OFFBOARD_TOGGLES, ENVIRONMENT_TOGGLES, MISC_TOGGLES,
    VISUALS_TOGGLES, HUD_TOGGLES,
)
from park_tab import park_rgb_address, PARK_RGB_ROWS, PARK_RGB_COLS

CONFIG_VERSION = 1

TOGGLEABLES_GROUPS = {
    "On Board": ONBOARD_TOGGLES,
    "Off Board": OFFBOARD_TOGGLES,
    "Environment": ENVIRONMENT_TOGGLES,
    "Misc": MISC_TOGGLES,
}

ADJUSTABLES_GROUPS = {
    "On Board": ON_BOARD_FIELDS,
    "Off Board": OFF_BOARD_FIELDS,
}

VISUALS_FIELD_GROUPS = {
    "adjustables": ADJUSTABLES_FIELDS,
    "environment": ENVIRONMENT_FIELDS,
    "world": WORLD_FIELDS,
    "hud": HUD_FIELDS,
    "screen": SCREEN_FIELDS,
}

# VISUALS' two toggle groups: its own TOGGLEABLES subtab, and HUD's Glitchy Text
VISUALS_TOGGLE_GROUPS = {
    "toggleables": VISUALS_TOGGLES,
    "hud_toggleables": HUD_TOGGLES,
}

# the two fixed-address RGB colors, key -> (address, default (r,g,b) tuple or None)
VISUALS_RGB_GROUPS = {
    "fog_color": (FOG_COLOR_ADDRESS, FOG_COLOR_DEFAULT),
    "skater_color": (SKATER_COLOR_ADDRESS, SKATER_COLOR_DEFAULT),
}

# shared helpers
def _toggle_is_on(state, cfg) -> bool:
    first = cfg["writes"][0]
    current = bytes(state.ps3.Process.Memory.Get(state.pid, first["address"], len(first["on"])))
    return current == first["on"]


def _toggle_apply(state, cfg, turn_on: bool):
    for w in cfg["writes"]:
        state.ps3.Process.Memory.Set(state.pid, w["address"], w["on"] if turn_on else w["off"])


def _save_toggle_group(state, toggles: dict) -> dict:
    out = {}
    for name, cfg in toggles.items():
        try:
            out[name] = _toggle_is_on(state, cfg)
        except Exception:
            pass  # skip - leaves this one out of the snapshot rather than aborting the whole save
    return out


def _apply_toggle_group(state, toggles: dict, saved: dict) -> int:
    applied = 0
    if not isinstance(saved, dict):
        return applied
    for name, turn_on in saved.items():
        cfg = toggles.get(name)
        if cfg is None or not isinstance(turn_on, bool):
            continue
        try:
            _toggle_apply(state, cfg, turn_on)
            applied += 1
        except Exception:
            pass
    return applied


def _save_field_group(state, fields: list) -> dict:
    out = {}
    for field in fields:
        try:
            out[field["label"]] = field["get"](state)
        except Exception:
            pass
    return out


def _apply_field_group(state, fields: list, saved: dict) -> int:
    applied = 0
    if not isinstance(saved, dict):
        return applied
    by_label = {f["label"]: f for f in fields}
    for label, value in saved.items():
        field = by_label.get(label)
        if field is None or not isinstance(value, (int, float)):
            continue
        try:
            field["set"](state, value)
            applied += 1
        except Exception:
            pass
    return applied


def _save_rgb(state, address) -> list:
    raw = bytes(state.ps3.Process.Memory.Get(state.pid, address, 12))
    return list(struct.unpack(">fff", raw))


def _apply_rgb(state, address, values) -> bool:
    if not (isinstance(values, list) and len(values) == 3):
        return False
    buf = struct.pack(">fff", *(float(v) for v in values))
    state.ps3.Process.Memory.Set(state.pid, address, buf)
    return True


def _save_park_rgb(state) -> list:
    rows = []
    for r in range(PARK_RGB_ROWS):
        row = []
        for c in range(PARK_RGB_COLS):
            try:
                row.append(_save_rgb(state, park_rgb_address(r, c)))
            except Exception:
                row.append(None)
        rows.append(row)
    return rows


def _apply_park_rgb(state, saved) -> int:
    applied = 0
    if not isinstance(saved, list):
        return applied
    for r, row in enumerate(saved):
        if r >= PARK_RGB_ROWS or not isinstance(row, list):
            continue
        for c, cell in enumerate(row):
            if c >= PARK_RGB_COLS:
                continue
            try:
                if _apply_rgb(state, park_rgb_address(r, c), cell):
                    applied += 1
            except Exception:
                pass
    return applied


def _save_hud_score_multiplier(state) -> float:
    raw = bytes(state.ps3.Process.Memory.Get(state.pid, SCORE_X1_ADDRESS, 4))
    return struct.unpack(">f", raw)[0]


def _apply_hud_score_multiplier(state, value):
    for addr, mult in ((SCORE_X1_ADDRESS, 1), (SCORE_X2_ADDRESS, 2), (SCORE_X3_ADDRESS, 3)):
        state.ps3.Process.Memory.Set(state.pid, addr, struct.pack(">f", float(value) * mult))

def build_snapshot(state) -> dict:
    # reads every covered value from memory and returns it as a dict for json.dump
    data = {
        "version": CONFIG_VERSION,
        "toggleables": {name: _save_toggle_group(state, toggles)
                         for name, toggles in TOGGLEABLES_GROUPS.items()},
        "adjustables": {name: _save_field_group(state, fields)
                         for name, fields in ADJUSTABLES_GROUPS.items()},
        "visuals": {name: _save_field_group(state, fields)
                    for name, fields in VISUALS_FIELD_GROUPS.items()},
        "park_rgb": _save_park_rgb(state),
    }
    for name, toggles in VISUALS_TOGGLE_GROUPS.items():
        data["visuals"][name] = _save_toggle_group(state, toggles)
    for name, (address, _default) in VISUALS_RGB_GROUPS.items():
        try:
            data["visuals"][name] = _save_rgb(state, address)
        except Exception:
            pass
    try:
        data["visuals"]["hud_score_multiplier"] = _save_hud_score_multiplier(state)
    except Exception:
        pass
    return data


def apply_snapshot(state, data: dict) -> int:
    # writes every value data has back to memory, skips unknown/malformed
    # keys, returns how many values were actually applied
    applied = 0
    if not isinstance(data, dict):
        return applied

    toggleables = data.get("toggleables", {})
    if isinstance(toggleables, dict):
        for name, toggles in TOGGLEABLES_GROUPS.items():
            applied += _apply_toggle_group(state, toggles, toggleables.get(name))

    adjustables = data.get("adjustables", {})
    if isinstance(adjustables, dict):
        for name, fields in ADJUSTABLES_GROUPS.items():
            applied += _apply_field_group(state, fields, adjustables.get(name))

    visuals = data.get("visuals", {})
    if isinstance(visuals, dict):
        for name, fields in VISUALS_FIELD_GROUPS.items():
            applied += _apply_field_group(state, fields, visuals.get(name))
        for name, toggles in VISUALS_TOGGLE_GROUPS.items():
            applied += _apply_toggle_group(state, toggles, visuals.get(name))
        for name, (address, _default) in VISUALS_RGB_GROUPS.items():
            try:
                if _apply_rgb(state, address, visuals.get(name)):
                    applied += 1
            except Exception:
                pass
        hud_value = visuals.get("hud_score_multiplier")
        if isinstance(hud_value, (int, float)):
            try:
                _apply_hud_score_multiplier(state, hud_value)
                applied += 1
            except Exception:
                pass

    applied += _apply_park_rgb(state, data.get("park_rgb"))

    return applied


def save_config(state, path: str):
    # snapshots current memory values and writes them to path as JSON
    if not state.is_ready():
        return False, "Connect and attach first."
    try:
        data = build_snapshot(state)
    except Exception as e:
        return False, f"Couldn't read current values: {e}"
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except OSError as e:
        return False, f"Couldn't write config: {e}"
    return True, f"Config saved to {path}."


def load_config(state, path: str):
    # reads path and writes every value it contains back to memory
    if not state.is_ready():
        return False, "Connect and attach first."
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return False, f"Couldn't read config: {e}"
    try:
        applied = apply_snapshot(state, data)
    except Exception as e:
        return False, f"Couldn't apply config: {e}"
    return True, f"Config loaded ({applied} value{'s' if applied != 1 else ''} applied)."


def reset_all(state):
    # puts every toggle back to OFF and every field back to its default -
    # everything SAVE/LOAD CONFIG covers, except PARK RGB (no single default)
    if not state.is_ready():
        return False, "Connect and attach first."

    reset_count = 0

    def _reset_toggle_groups(groups):
        nonlocal reset_count
        for toggles in groups.values():
            for cfg in toggles.values():
                try:
                    _toggle_apply(state, cfg, False)
                    reset_count += 1
                except Exception:
                    pass

    def _reset_field_groups(groups):
        nonlocal reset_count
        for fields in groups.values():
            for field in fields:
                default = field.get("default")
                if default is None:
                    continue  # nothing known to reset this one to - leave it alone
                try:
                    field["set"](state, default)
                    reset_count += 1
                except Exception:
                    pass

    _reset_toggle_groups(TOGGLEABLES_GROUPS)
    _reset_toggle_groups(VISUALS_TOGGLE_GROUPS)
    _reset_field_groups(ADJUSTABLES_GROUPS)
    _reset_field_groups(VISUALS_FIELD_GROUPS)

    for address, default in VISUALS_RGB_GROUPS.values():
        if default is None:
            continue
        try:
            _apply_rgb(state, address, list(default))
            reset_count += 1
        except Exception:
            pass

    try:
        _apply_hud_score_multiplier(state, SCORE_MULTIPLIER_DEFAULT)
        reset_count += 1
    except Exception:
        pass

    return True, f"Reset {reset_count} value{'s' if reset_count != 1 else ''} to default."
