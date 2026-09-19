"""
toggleables_data.py
====================
Address/value data for the TOGGLEABLES tab's subtabs (ON BOARD / OFF BOARD /
ENVIRONMENT / MISC) plus VISUALS_TOGGLES, used by the top-level VISUALS
tab's TOGGLEABLES subtab (see visuals_tab.py). Each toggle is a simple
back-and-forth flip - same idea as the Extra subtab's Invisible mods: read
the current bytes at its address, if they match "on" write "off", otherwise
write "on".

A toggle can touch more than one address at once (e.g. "Better Party Play"
writes three separate opcodes together) - that's what `writes` is for, a
list of {address, off, on} dicts that all get read/written as one unit. The
FIRST entry in that list is what decides whether the toggle currently reads
as on or off; the rest just follow along.

Byte width isn't stored separately - it's just len(off) / len(on) (which
always match each other), so a toggle can mix single bytes, 4-byte
floats/ints, and 8-byte doubles without anything extra to configure. The
small helpers below (_f/_d/_i/_b) just make each value's type obvious at a
glance instead of every entry being an opaque bytes.fromhex(...) call.

These are plain 8-digit PS3 addresses (not the 9-digit 0x3XXXXXXXX style the
recipe/RGB regions use), so there's nothing to strip here - they're used
exactly as given in the SPRX source.
"""

import struct


def _f(value: float) -> bytes:
    """Big-endian 4-byte float - most of these toggles are this."""
    return struct.pack(">f", value)


def _d(value: float) -> bytes:
    """Big-endian 8-byte double - only No Peds & Traffic uses this."""
    return struct.pack(">d", value)


def _i(hex_str: str) -> bytes:
    """Raw 4-byte value from a hex string - opcodes/ints, not floats."""
    return bytes.fromhex(hex_str)


def _b(value: int) -> bytes:
    """Single raw byte - only Unlock All uses this."""
    return bytes([value])


# ---------------------------------------------------------------------------
# On Board - toggles that apply while actively skating
# ---------------------------------------------------------------------------
ONBOARD_TOGGLES = {
    "No Fall Damage": {
        "writes": [
            {"address": 0x40E5F37C, "off": _f(11.19999981), "on": _f(9999999.0)},
        ],
    },
    "Footplant Forever": {
        "writes": [
            {"address": 0x40E5BA7C, "off": _f(2.0), "on": _f(2.6)},
        ],
    },
    "No Footplant Damage": {
        "writes": [
            {"address": 0x40E5BA74, "off": _f(10.0), "on": _f(99999999.0)},
        ],
    },
    "No Air Timer": {
        "writes": [
            {"address": 0x00D52B80, "off": _i("801F002C"), "on": _i("60000000")},
        ],
    },
}

# ---------------------------------------------------------------------------
# Off Board - toggles that apply while off the board / on foot
# ---------------------------------------------------------------------------
OFFBOARD_TOGGLES = {
    "Walk In Air": {
        "writes": [
            {"address": 0x00CEC77C, "off": _i("980B0148"), "on": _i("60000000")},
        ],
    },
    "No HoM Timer": {
        "writes": [
            {"address": 0x40E5F3A4, "off": _f(20.0), "on": _f(99999999.0)},
        ],
    },
}

# ---------------------------------------------------------------------------
# Visuals - the toggle-style (on/off) visual mods, not the sliders/dropdowns
# that already live under Edit Skater. Shown under the top-level VISUALS
# tab's TOGGLEABLES subtab (visuals_tab.py), not here.
# ---------------------------------------------------------------------------
VISUALS_TOGGLES = {
    "Clean Replays": {
        "writes": [
            {"address": 0x4065549B, "off": _i("53686F77"), "on": _i("00000000")},
            {"address": 0x018FE520, "off": _f(1.0), "on": _f(0.0)},
            {"address": 0x018FE530, "off": _f(1.0), "on": _f(0.0)},
            {"address": 0x30935548, "off": _f(0.72), "on": _f(0.0)},
            {"address": 0x30935568, "off": _f(1.0), "on": _f(0.0)},
        ],
    },
    "Further Replay Zoom": {
        "writes": [
            {"address": 0x01851FB0, "off": _f(75.0), "on": _f(999.0)},
            {"address": 0x01830268, "off": _f(24.0), "on": _f(-999.0)},
        ],
    },
    "No Black Screen": {
        "writes": [
            {"address": 0x005BC15C, "off": _i("987F4B65"), "on": _i("60000000")},
        ],
    },
    "No Body Shadow": {
        "writes": [
            {"address": 0x40E62F9C, "off": _f(12.0), "on": _f(0.0)},
        ],
    },
}

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENVIRONMENT_TOGGLES = {
    "No Peds & Traffic": {
        "writes": [
            {"address": 0x018393D8, "off": _d(1.0), "on": _d(0.0)},  # double, not float
        ],
    },
    "Mute Environment": {
        "writes": [
            {"address": 0x30B90AFC, "off": _f(1.0), "on": _f(0.0)},
        ],
    },
}

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
MISC_TOGGLES = {
    "Better Party Play": {
        "writes": [
            {"address": 0x0108C4A0, "off": _i("91630014"), "on": _i("60000000")},
            {"address": 0x00590604, "off": _i("F8A30030"), "on": _i("38000001")},
            {"address": 0x001D4838, "off": _i("99460068"), "on": _i("38000000")},
        ],
    },
    "Unlock All": {
        "writes": [
            {"address": 0x427E3288, "off": _b(0x00), "on": _b(0x01)},  # single byte, not 4
        ],
    },
    "Walk / Skate Out Of Bounds": {
        "writes": [
            {"address": 0x00D96484, "off": _i("98030045"), "on": _i("60000000")},
            {"address": 0x00D964A4, "off": _i("98030041"), "on": _i("60000000")},
        ],
    },
}

# ---------------------------------------------------------------------------
# Debug - not plain on/off flips like the rest, so kept separate from the
# toggle dicts above and handled by its own subtab builder.
#
# Debug Cam is a ONE-WAY write: clicking it always pokes the same two bytes
# (02 / 02), there's no "off" state to flip back to - see toggleables_tab's
# DEBUG subtab. Animation Debug is a normal on/off flip (00 = on, 01 = off).
# ---------------------------------------------------------------------------
DEBUG_CAM_WRITES = [
    {"address": 0x47C98DD0, "value": _b(0x02)},
    {"address": 0x47C68157, "value": _b(0x02)},
]

ANIMATION_DEBUG_TOGGLE = {
    "address": 0x47C98DD2,
    "on": _b(0x00),
    "off": _b(0x01),
}

# ---------------------------------------------------------------------------
# HUD - just Glitchy Text right now, used by visuals_tab.py's HUD subtab
# (alongside Score Multiplier and Exposure, which aren't toggles).
# ---------------------------------------------------------------------------
HUD_TOGGLES = {
    "Glitchy Text": {
        "writes": [
            {"address": 0x30064360, "off": _b(0x0F), "on": _b(0x00)},
        ],
    },
}
