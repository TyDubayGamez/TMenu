"""
adjustables_data.py
====================
Field specs for the top-level ADJUSTABLES tab's ON BOARD / OFF BOARD
subtabs - built with field_widgets.py's factory functions instead of by
hand, since every one of these is just a single global float value.

Defaults below are only ever shown as a greyed-out placeholder in the box
(never pre-filled as real, settable text) - they're the vanilla/default
value found at each address, decoded from the raw bytes given:

    OllieHeight       C0 00 00 00  -> -2.0
    JumpHeight        41 9C CC CD  -> 19.6
    PlantHeight       40 40 00 00  ->  3.0
    PlantSpeed        3F F4 7A E1  ->  1.91
    HippyHeight       41 9C CC CD  -> 19.6
    TorpedoSpin       C0 80 00 00  -> -4.0
    GlideSpeed2       40 80 00 00  ->  4.0   (GlideSpeed's default, C0... no
                                              wait - see GLIDE_SPEED_OFFSET
                                              below for how GlideSpeed itself
                                              is derived from this)
    RagdollStiffness  3F 80 00 00  ->  1.0

GlideSpeed is two addresses that move together but aren't equal - GlideSpeed2
(0x40E5F568) is the real, user-facing value; GlideSpeed (0x40E5F564) always
sits GLIDE_SPEED_OFFSET above it (default 9.0 - default 4.0 = 5.0). Only one
field is shown for it - typing a number and hitting SET writes that number to
GlideSpeed2 and (number + offset) to GlideSpeed, keeping that same gap intact.
"""

from field_widgets import simple_float_field, linked_offset_float_field

GLIDE_SPEED_ADDRESS = 0x40E5F564
GLIDE_SPEED2_ADDRESS = 0x40E5F568
GLIDE_SPEED_OFFSET = 9.0 - 4.0  # 5.0 - the gap between GlideSpeed and GlideSpeed2's defaults

ON_BOARD_FIELDS = [
    simple_float_field("Ollie Height", 0x1857F1C, default=-2.0),
    simple_float_field("Plant Height", 0x40E5DEB0, default=3.0),
    simple_float_field("Plant Speed", 0x1856CD4, default=1.91),
    simple_float_field("Hippy Height", 0x1857678, default=19.6),
]

OFF_BOARD_FIELDS = [
    simple_float_field("Jump Height", 0x1858198, default=19.6),
    simple_float_field("Torpedo Spin", 0x40E5F618, default=-4.0),
    linked_offset_float_field(
        "Glide Speed", GLIDE_SPEED_ADDRESS, GLIDE_SPEED2_ADDRESS,
        GLIDE_SPEED_OFFSET, default=4.0,
    ),
    simple_float_field("Ragdoll Stiffness", 0x40DCFD04, default=1.0),
]
