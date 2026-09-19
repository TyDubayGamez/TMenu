"""
session_changes.py
====================
Session-only "what did the user actually change" log for menu_config.py's
SAVE CONFIG / LOAD CUSTOM CONFIG.

Why this exists: a huge amount of TMenu's covered memory already holds
non-default values the moment you attach that have nothing to do with
anything ever touched in this tool - just whatever state that particular
game/session happens to be in (this is also why a field can show up
"pre-filled" on attach - see field_widgets.py's do_prefill_if_nondefault,
which is just showing you the real live value of something you never
set). SAVE CONFIG used to snapshot ALL of that indiscriminately (a plain
memory read of every toggle/field, regardless of whether it was ever
touched this session), and LOAD wrote every single one of those values
back unconditionally - hundreds of memory writes per load, most of them
for things nobody ever actually changed. That's what was causing the
freezing.

The fix: every SET-style action anywhere in the tool - a field's own SET
button, SET ALL, a toggle button, an RGB SET, the HUD Score Multiplier,
and BINDS hotkeys firing any of the above - reports itself here via one
of the mark_*() functions the moment it actually happens. Only entries
logged this way ever make it into a saved config; a value that's merely
sitting in memory unmodified this session is never included, no matter
what build_snapshot would otherwise read there.

Setting something back to its own default un-marks it (every mark_*()
checks this itself, via the same close-enough-to-count-as-default
comparison field_widgets.py's own _is_default uses) - a value that's
back at vanilla has nothing worth persisting, so it drops out of the log
entirely rather than being saved as "default". This also means RESET
EVERYTHING (menu_config.reset_all) naturally empties the log on its own,
just by virtue of setting everything to its own default through these
same mark_*()-wrapped paths - see field_widgets.py's set-wrapping below.

The log is pure in-memory session state - never itself persisted, and
starts empty every time TMenu launches (clear(), called once from
app.py's main()).

How fields get tracked without touching every call site: install() (run
once, automatically, at import time - see the bottom of this file) wraps
each field spec's own "set" callable *in place*, inside the exact same
dict object adjustables_data.py/visuals_data.py already hand out to
field_widgets.py, binds_data.py, and menu_config.py alike. Since all of
those modules share that one dict by reference (not a copy), wrapping
"set" once here means a field's own SET button, SET ALL, and its BINDS
hotkey all report to this log automatically - nothing in field_widgets.py
or binds_data.py needs to know this module exists. Toggles don't have a
single stored "set" callable to wrap this way (see toggleables_data.py's
plain address/on/off "writes" shape), so those call mark_toggle()
directly from their own handful of call sites instead (toggleables_tab.py,
binds_data.py, menu_config.py) - same for the two RGB colors and the HUD
Score Multiplier, which aren't plain field-spec grids either.
"""

import math

from adjustables_data import ON_BOARD_FIELDS, OFF_BOARD_FIELDS
from visuals_data import (
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, SCREEN_FIELDS, WORLD_FIELDS, HUD_FIELDS,
)
from toggleables_data import (
    ONBOARD_TOGGLES, OFFBOARD_TOGGLES, ENVIRONMENT_TOGGLES, MISC_TOGGLES,
    VISUALS_TOGGLES, HUD_TOGGLES,
)

# id(fields-list) -> (top, group) matching menu_config.py's snapshot shape.
# If a group is ever renamed/added/removed in menu_config.py, mirror the
# change here too - this module intentionally doesn't import menu_config.py
# itself (menu_config imports this one) to avoid a circular import.
_FIELD_GROUP_OF = {
    id(ON_BOARD_FIELDS): ("adjustables", "On Board"),
    id(OFF_BOARD_FIELDS): ("adjustables", "Off Board"),
    id(ADJUSTABLES_FIELDS): ("visuals", "adjustables"),
    id(ENVIRONMENT_FIELDS): ("visuals", "environment"),
    id(WORLD_FIELDS): ("visuals", "world"),
    id(HUD_FIELDS): ("visuals", "hud"),
    id(SCREEN_FIELDS): ("visuals", "screen"),
}

_TOGGLE_GROUP_OF = {
    id(ONBOARD_TOGGLES): ("toggleables", "On Board"),
    id(OFFBOARD_TOGGLES): ("toggleables", "Off Board"),
    id(ENVIRONMENT_TOGGLES): ("toggleables", "Environment"),
    id(MISC_TOGGLES): ("toggleables", "Misc"),
    id(VISUALS_TOGGLES): ("visuals", "toggleables"),
    id(HUD_TOGGLES): ("visuals", "hud_toggleables"),
}

_changed_fields = {}    # (top, group, label) -> value
_changed_toggles = {}   # (top, group, name)  -> True (only ON is ever logged)
_changed_rgb = {}       # key ("fog_color"/"skater_color") -> [r, g, b]
_changed_hud_mult = {"value": None}


def clear():
    """Wipes the whole session log. Call once on app startup (app.py's
    main())."""
    _changed_fields.clear()
    _changed_toggles.clear()
    _changed_rgb.clear()
    _changed_hud_mult["value"] = None


def _is_close(kind, value, default):
    if default is None:
        return False
    if kind == "int":
        return int(round(value)) == int(round(default))
    return math.isclose(value, default, rel_tol=1e-4, abs_tol=1e-4)


# ---------------------------------------------------------------------------
# Writers - called the moment something actually gets set.
# ---------------------------------------------------------------------------

def mark_field(fields_obj, label, value, kind="float", default=None):
    """`fields_obj` is the exact ON_BOARD_FIELDS/ADJUSTABLES_FIELDS/...
    list this field came from - used to look up which config group it
    belongs to. A list this module doesn't recognize is just ignored
    (nothing to log against, e.g. SAVE>STATS' own fields aren't part of
    the whole-menu config)."""
    group = _FIELD_GROUP_OF.get(id(fields_obj))
    if group is None:
        return
    key = group + (label,)
    if _is_close(kind, value, default):
        _changed_fields.pop(key, None)
    else:
        _changed_fields[key] = value


def mark_toggle(toggles_obj, name, turn_on):
    """A toggle's own default is always OFF, so only ON is ever worth
    logging - flipping back to OFF un-marks it. `toggles_obj` not being a
    recognized TOGGLEABLES/VISUALS group (e.g. MISC>DEBUG or ONLINE's
    Freeskate, fired via BINDS) is just ignored."""
    group = _TOGGLE_GROUP_OF.get(id(toggles_obj))
    if group is None:
        return
    key = group + (name,)
    if turn_on:
        _changed_toggles[key] = True
    else:
        _changed_toggles.pop(key, None)


def mark_rgb(key: str, values, default=None):
    if default is not None and len(values) == 3 and all(
        math.isclose(v, d, rel_tol=1e-4, abs_tol=1e-4) for v, d in zip(values, default)
    ):
        _changed_rgb.pop(key, None)
    else:
        _changed_rgb[key] = list(values)


def mark_hud_score_multiplier(value, default):
    if default is not None and math.isclose(value, default, rel_tol=1e-4, abs_tol=1e-4):
        _changed_hud_mult["value"] = None
    else:
        _changed_hud_mult["value"] = value


# ---------------------------------------------------------------------------
# Readers - menu_config.py's build_snapshot calls these instead of doing a
# blanket memory read of everything.
# ---------------------------------------------------------------------------

def changed_fields(top: str, group: str) -> dict:
    """label -> value, for whatever's actually been changed (and is still
    away from default) in this exact (top, group) - e.g.
    ("adjustables", "On Board")."""
    return {k[2]: v for k, v in _changed_fields.items() if k[0] == top and k[1] == group}


def changed_toggles(top: str, group: str) -> dict:
    """name -> True, same (top, group) shape as changed_fields()."""
    return {k[2]: True for k in _changed_toggles if k[0] == top and k[1] == group}


def changed_fields_for(fields_obj) -> dict:
    """Same as changed_fields(), but keyed straight off the list object
    itself (e.g. ON_BOARD_FIELDS) - saves menu_config.py from needing to
    know/repeat the (top, group) strings _FIELD_GROUP_OF already has."""
    group = _FIELD_GROUP_OF.get(id(fields_obj))
    if group is None:
        return {}
    return changed_fields(*group)


def changed_toggles_for(toggles_obj) -> dict:
    """Same idea as changed_fields_for(), for a toggles dict."""
    group = _TOGGLE_GROUP_OF.get(id(toggles_obj))
    if group is None:
        return {}
    return changed_toggles(*group)


def changed_rgb(key: str):
    """Returns the logged [r, g, b] for `key`, or None if untouched/back
    at default."""
    return _changed_rgb.get(key)


def changed_hud_score_multiplier():
    return _changed_hud_mult["value"]


# ---------------------------------------------------------------------------
# One-time install: wrap every plain field-spec's own "set" in place so
# SET/SET ALL (field_widgets.py) and BINDS value-hotkeys (binds_data.py) -
# every caller that already holds a reference to that same shared dict -
# report here automatically, with no changes needed on their end.
# ---------------------------------------------------------------------------

def _install_field_tracking():
    for fields_obj in _FIELD_GROUP_OF_KEYS_TO_LISTS:
        for field in fields_obj:
            if field.get("_session_tracked"):
                continue  # already wrapped (install() only ever needs to run once)
            original_set = field["set"]
            kind = field.get("kind", "float")
            default = field.get("default")
            label = field["label"]

            def wrapped_set(state, value, _orig=original_set, _fields=fields_obj,
                             _label=label, _kind=kind, _default=default):
                _orig(state, value)
                mark_field(_fields, _label, value, _kind, _default)

            field["set"] = wrapped_set
            field["_session_tracked"] = True


_FIELD_GROUP_OF_KEYS_TO_LISTS = (
    ON_BOARD_FIELDS, OFF_BOARD_FIELDS,
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, WORLD_FIELDS, HUD_FIELDS, SCREEN_FIELDS,
)

_install_field_tracking()
