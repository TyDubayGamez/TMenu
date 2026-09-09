import re
import struct

from toggleables_data import (
    ONBOARD_TOGGLES, OFFBOARD_TOGGLES, ENVIRONMENT_TOGGLES, MISC_TOGGLES,
    VISUALS_TOGGLES, DEBUG_CAM_WRITES, ANIMATION_DEBUG_TOGGLE,
)
from adjustables_data import ON_BOARD_FIELDS, OFF_BOARD_FIELDS
from visuals_data import (
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, SCREEN_FIELDS,
    SCORE_X1_ADDRESS, SCORE_X2_ADDRESS, SCORE_X3_ADDRESS, SCORE_MULTIPLIER_DEFAULT,
)
import online_data


def slug(label: str) -> str:
    # "Ollie Height" -> "ollie_height", used as a stable id within its group
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")

# "toggle" kind - fire() factories


def _flip_fire(label, writes):
    # reads writes[0]'s current bytes: if they match "on" write "off", else write "on"
    def fire(state):
        if not state.is_ready():
            return False, "Connect and attach first."
        try:
            pid = state.pid
            first = writes[0]
            current = bytes(state.ps3.Process.Memory.Get(pid, first["address"], len(first["on"])))
            turning_on = current != first["on"]
            for w in writes:
                state.ps3.Process.Memory.Set(pid, w["address"], w["on"] if turning_on else w["off"])
            return True, f"{label} {'ON' if turning_on else 'OFF'}."
        except Exception as e:
            return False, str(e)
    return fire


def _oneway_fire(label, writes):
    # one-way SET, no off state
    def fire(state):
        if not state.is_ready():
            return False, "Connect and attach first."
        try:
            pid = state.pid
            for w in writes:
                state.ps3.Process.Memory.Set(pid, w["address"], w["value"])
            return True, f"{label} SET."
        except Exception as e:
            return False, str(e)
    return fire


def _toggles_to_items(toggles: dict) -> dict:
    # converts a toggleables_data.py dict into BIND_GROUPS "toggle" items
    return {
        slug(name): {"label": name, "fire": _flip_fire(name, cfg["writes"])}
        for name, cfg in toggles.items()
    }


def _fields_to_items(fields: list) -> dict:
    # converts field_widgets.py field specs into BIND_GROUPS "value" items
    return {slug(f["label"]): f for f in fields}

# misc > debug
_DEBUG_ITEMS = {
    "debug_cam": {"label": "Debug Cam", "fire": _oneway_fire("Debug Cam", DEBUG_CAM_WRITES)},
    "animation_debug": {
        "label": "Animation Debug",
        "fire": _flip_fire("Animation Debug", [ANIMATION_DEBUG_TOGGLE]),
    },
}

# online > freeskate
_freeskate_on = online_data.pack_ascii(online_data.FREESKATE_TYPE_ON, online_data.CHALLENGE_TYPE_FIELD_WIDTH)
_freeskate_off = online_data.pack_ascii(online_data.FREESKATE_TYPE_OFF, online_data.CHALLENGE_TYPE_FIELD_WIDTH)
_FREESKATE_ITEMS = {
    "freeskate": {
        "label": "Freeskate",
        "fire": _flip_fire(
            "Freeskate",
            [{"address": online_data.ADDR_CHALLENGE_TYPE, "on": _freeskate_on, "off": _freeskate_off}],
        ),
    },
}

# visuals > HUD score multiplier - one input driving three addresses
def _score_get(state):
    raw = bytes(state.ps3.Process.Memory.Get(state.pid, SCORE_X1_ADDRESS, 4))
    return struct.unpack(">f", raw)[0]


def _score_set(state, value):
    for addr, mult in ((SCORE_X1_ADDRESS, 1), (SCORE_X2_ADDRESS, 2), (SCORE_X3_ADDRESS, 3)):
        state.ps3.Process.Memory.Set(state.pid, addr, struct.pack(">f", float(value) * mult))

_HUD_ITEMS = {
    "score_multiplier": {
        "label": "Score Multiplier (Base x1)",
        "kind": "float",
        "default": SCORE_MULTIPLIER_DEFAULT,
        "get": _score_get,
        "set": _score_set,
    },
}

# order here is display order in the BINDS tab's category dropdown
BIND_GROUPS = [
    {"key": "onboard_toggle", "label": "Toggleables - On Board", "kind": "toggle",
     "items": _toggles_to_items(ONBOARD_TOGGLES)},
    {"key": "offboard_toggle", "label": "Toggleables - Off Board", "kind": "toggle",
     "items": _toggles_to_items(OFFBOARD_TOGGLES)},
    {"key": "environment_toggle", "label": "Toggleables - Environment", "kind": "toggle",
     "items": _toggles_to_items(ENVIRONMENT_TOGGLES)},
    {"key": "misc_toggle", "label": "Toggleables - Misc", "kind": "toggle",
     "items": _toggles_to_items(MISC_TOGGLES)},
    {"key": "debug", "label": "Misc - Debug", "kind": "toggle", "items": _DEBUG_ITEMS},
    {"key": "freeskate", "label": "Online - Freeskate", "kind": "toggle", "items": _FREESKATE_ITEMS},
    {"key": "visuals_toggle", "label": "Visuals - Toggleables", "kind": "toggle",
     "items": _toggles_to_items(VISUALS_TOGGLES)},
    {"key": "visuals_adjustables", "label": "Visuals - Adjustables", "kind": "value",
     "items": _fields_to_items(ADJUSTABLES_FIELDS)},
    {"key": "visuals_environment", "label": "Visuals - Environment", "kind": "value",
     "items": _fields_to_items(ENVIRONMENT_FIELDS)},
    {"key": "visuals_hud", "label": "Visuals - HUD", "kind": "value", "items": _HUD_ITEMS},
    {"key": "visuals_screen", "label": "Visuals - Screen", "kind": "value",
     "items": _fields_to_items(SCREEN_FIELDS)},
    {"key": "adjustables_onboard", "label": "Adjustables - On Board", "kind": "value",
     "items": _fields_to_items(ON_BOARD_FIELDS)},
    {"key": "adjustables_offboard", "label": "Adjustables - Off Board", "kind": "value",
     "items": _fields_to_items(OFF_BOARD_FIELDS)},
]

# group_key -> group, for fast lookups instead of looping BIND_GROUPS
GROUPS_BY_KEY = {g["key"]: g for g in BIND_GROUPS}


def get_item(group_key: str, item_key: str):
    group = GROUPS_BY_KEY.get(group_key)
    if group is None:
        return None, None
    item = group["items"].get(item_key)
    return group, item
