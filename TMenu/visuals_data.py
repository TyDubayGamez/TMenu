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

# score multiplier - one field controls ScoreX1/X2/X3 together (2x/3x of ScoreX1)
SCORE_X1_ADDRESS = 0x40E68240
SCORE_X2_ADDRESS = 0x40E68244
SCORE_X3_ADDRESS = 0x40E68248
SCORE_MULTIPLIER_DEFAULT = 1.0

# HUD exposure
HUD_EXPOSURE_ADDRESS = 0x0185BA2C
HUD_EXPOSURE_DEFAULT = struct.unpack(">f", bytes.fromhex("3B808081"))[0]
HUD_FIELDS = [
    simple_float_field("Exposure", HUD_EXPOSURE_ADDRESS, default=HUD_EXPOSURE_DEFAULT),
]

# fog - color is a 3-float RGB value, density/distance are plain floats
FOG_COLOR_ADDRESS = 0x40E55210
FOG_COLOR_DEFAULT = struct.unpack(">fff", bytes.fromhex("3D30B0A73E0C8C8C3E88888A"))

FOG_DENSITY_ADDRESS = 0x40E55220
FOG_DISTANCE_ADDRESS = 0x40E55224
WORLD_FIELDS = [
    simple_float_field("Fog Density", FOG_DENSITY_ADDRESS, default=1.0),
    simple_float_field("Fog Distance", FOG_DISTANCE_ADDRESS, default=100.0),
]

# skater color - same RGB shape as fog color above
SKATER_COLOR_ADDRESS = 0x019A0160
SKATER_COLOR_DEFAULT = (1.0, 1.0, 1.0)
