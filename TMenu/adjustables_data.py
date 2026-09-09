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
