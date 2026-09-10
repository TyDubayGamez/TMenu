"""
binds_data.py
=============
Static data + pure logic for the BINDS tab. Nothing in here touches Qt -
binds_tab.py (UI) and binds_keyboard.py (keyboard hook) both import from
this module instead of each rolling their own copy.

BIND_GROUPS is the full registry of everything a keyboard hotkey can be
attached to, grouped the same way their own tabs already group them. Two
kinds of group:

  - "toggle" groups: each item is a plain on/off (or one-way) action - a
    single hotkey fires it, same as a click on its own tab's button. Item
    shape: {"label": display name, "fire": callable(state) -> (ok, message)}.

  - "value" groups: each item is one of the adjustable/visual float fields
    (same field-spec dicts field_widgets.py's factories already build for
    adjustables_data.py/visuals_data.py - label/kind/default/get/set), which
    BINDS lets you attach MULTIPLE hotkeys to at once (e.g. "1" -> Ollie
    Height 5.0, "2" -> Ollie Height 12.0). There's no separate "reset"
    bind - pressing a value hotkey again while the field is already sitting
    at that exact value puts it back to the field's own vanilla default
    instead (binds_tab.py's make_value_fire_handler re-reads the field from
    memory every time the hotkey fires to decide which of the two it's
    doing). This module just supplies the field specs themselves; the
    toggle-back-to-default logic lives in binds_tab.py, not here.

Scope (what's covered, and what deliberately isn't):
  - All four TOGGLEABLES subtabs (On Board / Off Board / Environment / Misc).
  - MISC > DEBUG's two actions (Debug Cam, Animation Debug).
  - ONLINE's Freeskate toggle specifically - the one exception carved out of
    an otherwise online-tab-free registry, since it's just as useful to
    hotkey as anything on TOGGLEABLES.
  - All of VISUALS (its own TOGGLEABLES subtab, ADJUSTABLES, ENVIRONMENT,
    HUD's Score Multiplier, and SCREEN).
  - Both ADJUSTABLES subtabs (On Board / Off Board).
  - NOT included: the rest of ONLINE (server-side / session state, not a
    local hotkey-able setting), EDIT SKATER / PARK / SAVE (per-skater or
    per-cell selection makes "one hotkey = one action" ambiguous for these -
    a future BIND_GROUPS entry could target one specific skater/cell if
    that's ever wanted, but nothing today assumes that can't be added).

(An earlier version of BINDS also had a CONTROLLER subtab - assign an
in-game controller button, read live from PS3 memory via a polling engine
and an AOB scan for its addresses. That didn't pan out and was removed;
KEYBOARD (binds_keyboard.py, using the third-party `keyboard` package for
system-wide PC hotkeys) is the only way to trigger a bindable action now.)
"""

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
    """'Ollie Height' -> 'ollie_height' - used as this action's stable id
    within its group (see BIND_GROUPS), so a renamed display label doesn't
    silently orphan a saved bind as long as the underlying field/toggle
    itself doesn't move groups."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


# ---------------------------------------------------------------------------
# "toggle" kind - fire() factories
# ---------------------------------------------------------------------------

def _flip_fire(label, writes):
    """Same flip mechanic as toggleables_tab.py's build_toggle_group and
    online_tab.py's Freeskate button: read writes[0]'s current bytes, if
    they already match "on" write "off" instead, otherwise write "on"."""
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
    """One-way SET, no off state - same as Debug Cam's own button."""
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
    """{name: {"writes": [...]}} (toggleables_data.py's shape) -> BIND_GROUPS
    "toggle"-kind items."""
    return {
        slug(name): {"label": name, "fire": _flip_fire(name, cfg["writes"])}
        for name, cfg in toggles.items()
    }


def _fields_to_items(fields: list) -> dict:
    """field_widgets.py-style field specs -> BIND_GROUPS "value"-kind items -
    the field spec dict (label/kind/default/get/set) is exactly what's
    needed already, this just keys them by slug for the registry."""
    return {slug(f["label"]): f for f in fields}


# ---------------------------------------------------------------------------
# Misc > Debug (not a toggleables_data.py dict - see misc_tab.py)
# ---------------------------------------------------------------------------

_DEBUG_ITEMS = {
    "debug_cam": {"label": "Debug Cam", "fire": _oneway_fire("Debug Cam", DEBUG_CAM_WRITES)},
    "animation_debug": {
        "label": "Animation Debug",
        "fire": _flip_fire("Animation Debug", [ANIMATION_DEBUG_TOGGLE]),
    },
}

# ---------------------------------------------------------------------------
# Online > Freeskate (the one online_tab.py action BINDS reaches into)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Visuals > HUD (Score Multiplier - one input driving three addresses, same
# as visuals_tab.py's _build_hud - not a plain field_widgets grid field)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# The registry - order here is display order in the BINDS tab's category
# dropdown.
# ---------------------------------------------------------------------------

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

# group_key -> group, and (group_key, item_key) -> item, for fast lookups
# elsewhere (binds_config.py's validation, binds_tab.py's UI) instead of
# every caller looping BIND_GROUPS by hand.
GROUPS_BY_KEY = {g["key"]: g for g in BIND_GROUPS}


def get_item(group_key: str, item_key: str):
    group = GROUPS_BY_KEY.get(group_key)
    if group is None:
        return None, None
    item = group["items"].get(item_key)
    return group, item
