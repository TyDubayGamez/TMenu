"""
visuals_data.py
=================
Field specs for the VISUALS tab's ADJUSTABLES / ENVIRONMENT / SCREEN
subtabs (built with field_widgets.py, same as adjustables_data.py), plus the
raw addresses for the HUD subtab's score-multiplier feature, which needs its
own custom widget instead of a plain field grid (see visuals_tab.py).

Defaults, decoded from the raw bytes given:

    Transparency      43 7F 00 00  -> 255.0
    FoV               42 70 00 00  ->  60.0
    NPCSize           3F 80 00 00  ->   1.0
    SkyboxBrightness  3E B3 33 33  ->   0.35
    Brightness        40 20 00 00  ->   2.5
    ScreenWidth       BF F0 00 00  ->  -1.875

FoV is written to two addresses at once (0x302528F0 and 0x302A28F0) - unclear
which one the game actually reads back from moment to moment, so both get
written together every time and GET just reads the first.

WORLD (Fog) / Skater Color / HUD Exposure defaults are decoded straight from
the raw bytes given for each, the same way the ones above were, rather than
hand-typed decimal approximations - see the struct.unpack calls below.
"""

import struct

from field_widgets import simple_float_field, multi_address_float_field

ADJUSTABLES_FIELDS = [
    simple_float_field("Transparency", 0x183E3E0, default=255.0),
    multi_address_float_field("FoV", [0x302528F0, 0x302A28F0], default=60.0),
]

ENVIRONMENT_FIELDS = [
    simple_float_field("NPC Size", 0x185AB8C, default=1.0),
    simple_float_field("Skybox Brightness", 0x40E55CE4, default=0.35),
]

SCREEN_FIELDS = [
    simple_float_field("Brightness", 0x40E63070, default=2.5),
    simple_float_field("Screen Width", 0x018405E0, default=-1.875),
]

# HUD score multiplier - ScoreX2/X3 always sit at 2x/3x whatever ScoreX1 is
# set to (e.g. typing 30 makes ScoreX1/X2/X3 30/60/90). One field controls
# all three; see visuals_tab.py's _build_hud for the custom widget.
SCORE_X1_ADDRESS = 0x40E68240
SCORE_X2_ADDRESS = 0x40E68244
SCORE_X3_ADDRESS = 0x40E68248
SCORE_MULTIPLIER_DEFAULT = 1.0

# HUD Exposure - one plain float field, laid out in the HUD subtab
# alongside Score Multiplier and Glitchy Text (toggleables_data.HUD_TOGGLES).
HUD_EXPOSURE_ADDRESS = 0x0185BA2C
HUD_EXPOSURE_DEFAULT = struct.unpack(">f", bytes.fromhex("3B808081"))[0]
HUD_FIELDS = [
    simple_float_field("Exposure", HUD_EXPOSURE_ADDRESS, default=HUD_EXPOSURE_DEFAULT),
]

# WORLD (Fog) - VISUALS>WORLD subtab. Color is a 12-byte/3-float RGB value
# (field_widgets.build_rgb_field_group, not a plain field grid); Density and
# Distance are plain float fields.
FOG_COLOR_ADDRESS = 0x40E55210
FOG_COLOR_DEFAULT = struct.unpack(">fff", bytes.fromhex("3D30B0A73E0C8C8C3E88888A"))

FOG_DENSITY_ADDRESS = 0x40E55220
FOG_DISTANCE_ADDRESS = 0x40E55224
WORLD_FIELDS = [
    simple_float_field("Fog Density", FOG_DENSITY_ADDRESS, default=1.0),
    simple_float_field("Fog Distance", FOG_DISTANCE_ADDRESS, default=100.0),
]

# Skater Color - VISUALS>ADJUSTABLES subtab, alongside Transparency/FoV.
# Same 12-byte/3-float RGB shape as Fog Color above.
SKATER_COLOR_ADDRESS = 0x019A0160
SKATER_COLOR_DEFAULT = (1.0, 1.0, 1.0)
