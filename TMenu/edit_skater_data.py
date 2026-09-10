"""
edit_skater_data.py
====================
Per-skater (1-5) memory offsets for the EDIT SKATER tab, parsed straight out of
the "Skate_3_Skaters.CT" Cheat Engine table so the addresses match it exactly.

SKATERS[n] holds three sections per skater:
  - rgb_colors: body part -> {red, green, blue} addresses (Float Big Endian)
  - body_mods:  body/face slider name -> single float address
  - settings:   Stance / Style / Posture (Byte + dropdown options) and
                Trucks Tightness / Wheels Hardness (float, unused by the UI today)

GESTURES holds the 4 gesture slot addresses. These are NOT per-skater in the CT -
there is only one set, and in-game it always applies to whichever skater is
currently being edited. GESTURE_OPTIONS is the shared dropdown list for all 4.
"""

SKATERS = {
    1: {
        "rgb_colors": {
            "hat": {"red": 0x330070030, "green": 0x330070034, "blue": 0x330070038},
            "hair": {"red": 0x330070070, "green": 0x330070074, "blue": 0x330070078},
            "head": {"red": 0x3300700b0, "green": 0x3300700b4, "blue": 0x3300700b8},
            "arms": {"red": 0x3300700f0, "green": 0x3300700f4, "blue": 0x3300700f8},
            "legs": {"red": 0x330070130, "green": 0x330070134, "blue": 0x330070138},
            "shirt": {"red": 0x330070270, "green": 0x330070274, "blue": 0x330070278},
            "socks": {"red": 0x3300702b0, "green": 0x3300702b4, "blue": 0x3300702b8},
            "pants": {"red": 0x330070330, "green": 0x330070334, "blue": 0x330070338},
            "hidden rgb 1": {"red": 0x3300701b0, "green": 0x3300701b4, "blue": 0x3300701b8},
            "hidden rgb 2": {"red": 0x3300701f0, "green": 0x3300701f4, "blue": 0x3300701f8},
            "hidden rgb 3": {"red": 0x330070230, "green": 0x330070234, "blue": 0x330070238},
        },
        "body_mods": {
            "Fatness": 0x330060070,
            "Skinniness": 0x330060074,
            "Eye Width": 0x330060030,
            "Eye Height": 0x3300600b4,
            "Brow Height": 0x33006007c,
            "Brow Rotation": 0x330060078,
            "Brow Profile": 0x330060080,
            "Nose Length": 0x33006008c,
            "Nose Width": 0x330060088,
            "Nose Height": 0x330060090,
            "Nose Curve": 0x330060084,
            "Jaw Definition": 0x3300600a8,
            "Jaw Roundness": 0x3300600ac,
            "Mouth Width": 0x330060094,
            "Mouth Smile": 0x330060098,
            "Mouth Fullness": 0x33006009c,
            "Mouth Height": 0x3300600a0,
            "Chin Length": 0x3300600a4,
        },
        "settings": {
            "Stance": {"address": 0x3018e0813, "options": [(0, "Goofy"), (1, "Regular")]},
            "Style": {"address": 0x3018e0817, "options": [(0, "Standard"), (1, "Loose"), (2, "OG"), (3, "Aggressive")]},
            "Posture": {"address": 0x3018e081b, "options": [(0, "Default"), (1, "Straight"), (2, "Hunched"), (3, "Macho")]},
            "Trucks Tightness": {"address": 0x3018e0804, "options": None},
            "Wheels Hardness": {"address": 0x3018e0808, "options": None},
            "Gender": {"address": 0x3018e0830, "options": [(0, "Female"), (1, "Male")]},
        },
    },
    2: {
        "rgb_colors": {
            "hat": {"red": 0x3300703b0, "green": 0x3300703b4, "blue": 0x3300703b8},
            "hair": {"red": 0x3300703f0, "green": 0x3300703f4, "blue": 0x3300703f8},
            "head": {"red": 0x330070430, "green": 0x330070434, "blue": 0x330070438},
            "arms": {"red": 0x330070470, "green": 0x330070474, "blue": 0x330070478},
            "legs": {"red": 0x3300704b0, "green": 0x3300704b4, "blue": 0x3300704b8},
            "shirt": {"red": 0x3300705f0, "green": 0x3300705f4, "blue": 0x3300705f8},
            "socks": {"red": 0x330070630, "green": 0x330070634, "blue": 0x330070638},
            "pants": {"red": 0x3300706b0, "green": 0x3300706b4, "blue": 0x3300706b8},
            "hidden rgb 1": {"red": 0x330070530, "green": 0x330070534, "blue": 0x330070538},
            "hidden rgb 2": {"red": 0x330070570, "green": 0x330070574, "blue": 0x330070578},
            "hidden rgb 3": {"red": 0x3300705b0, "green": 0x3300705b4, "blue": 0x3300705b8},
        },
        "body_mods": {
            "Fatness": 0x3300600c0,
            "Skinniness": 0x3300600c4,
            "Eye Width": 0x330060080,
            "Eye Height": 0x330060104,
            "Brow Height": 0x3300600cc,
            "Brow Rotation": 0x3300600c8,
            "Brow Profile": 0x3300600d0,
            "Nose Length": 0x3300600dc,
            "Nose Width": 0x3300600d8,
            "Nose Height": 0x3300600e0,
            "Nose Curve": 0x3300600d4,
            "Jaw Definition": 0x3300600f8,
            "Jaw Roundness": 0x3300600fc,
            "Mouth Width": 0x3300600e4,
            "Mouth Smile": 0x3300600e8,
            "Mouth Fullness": 0x3300600ec,
            "Mouth Height": 0x3300600f0,
            "Chin Length": 0x3300600f4,
        },
        "settings": {
            "Stance": {"address": 0x3018e6573, "options": [(0, "Goofy"), (1, "Regular")]},
            "Style": {"address": 0x3018e6577, "options": [(0, "Standard"), (1, "Loose"), (2, "OG"), (3, "Aggressive")]},
            "Posture": {"address": 0x3018e657b, "options": [(0, "Default"), (1, "Straight"), (2, "Hunched"), (3, "Macho")]},
            "Trucks Tightness": {"address": 0x3018e6564, "options": None},
            "Wheels Hardness": {"address": 0x3018e6568, "options": None},
            "Gender": {"address": 0x3018e6590, "options": [(0, "Female"), (1, "Male")]},
        },
    },
    3: {
        "rgb_colors": {
            "hat": {"red": 0x330070730, "green": 0x330070734, "blue": 0x330070738},
            "hair": {"red": 0x330070770, "green": 0x330070774, "blue": 0x330070778},
            "head": {"red": 0x3300707b0, "green": 0x3300707b4, "blue": 0x3300707b8},
            "arms": {"red": 0x3300707f0, "green": 0x3300707f4, "blue": 0x3300707f8},
            "legs": {"red": 0x330070830, "green": 0x330070834, "blue": 0x330070838},
            "shirt": {"red": 0x330070970, "green": 0x330070974, "blue": 0x330070978},
            "socks": {"red": 0x3300709b0, "green": 0x3300709b4, "blue": 0x3300709b8},
            "pants": {"red": 0x330070a30, "green": 0x330070a34, "blue": 0x330070a38},
            "hidden rgb 1": {"red": 0x3300708b0, "green": 0x3300708b4, "blue": 0x3300708b8},
            "hidden rgb 2": {"red": 0x3300708f0, "green": 0x3300708f4, "blue": 0x3300708f8},
            "hidden rgb 3": {"red": 0x330070930, "green": 0x330070934, "blue": 0x330070938},
        },
        "body_mods": {
            "Fatness": 0x330060110,
            "Skinniness": 0x330060114,
            "Eye Width": 0x3300600d0,
            "Eye Height": 0x330060154,
            "Brow Height": 0x33006011c,
            "Brow Rotation": 0x330060118,
            "Brow Profile": 0x330060120,
            "Nose Length": 0x33006012c,
            "Nose Width": 0x330060128,
            "Nose Height": 0x330060130,
            "Nose Curve": 0x330060124,
            "Jaw Definition": 0x330060148,
            "Jaw Roundness": 0x33006014c,
            "Mouth Width": 0x330060134,
            "Mouth Smile": 0x330060138,
            "Mouth Fullness": 0x33006013c,
            "Mouth Height": 0x330060140,
            "Chin Length": 0x330060144,
        },
        "settings": {
            "Stance": {"address": 0x3018ec2d3, "options": [(0, "Goofy"), (1, "Regular")]},
            "Style": {"address": 0x3018ec2d7, "options": [(0, "Standard"), (1, "Loose"), (2, "OG"), (3, "Aggressive")]},
            "Posture": {"address": 0x3018ec2db, "options": [(0, "Default"), (1, "Straight"), (2, "Hunched"), (3, "Macho")]},
            "Trucks Tightness": {"address": 0x3018ec2c4, "options": None},
            "Wheels Hardness": {"address": 0x3018ec2c8, "options": None},
            "Gender": {"address": 0x3018ec2f0, "options": [(0, "Female"), (1, "Male")]},
        },
    },
    4: {
        "rgb_colors": {
            "hat": {"red": 0x330070ab0, "green": 0x330070ab4, "blue": 0x330070ab8},
            "hair": {"red": 0x330070af0, "green": 0x330070af4, "blue": 0x330070af8},
            "head": {"red": 0x330070b30, "green": 0x330070b34, "blue": 0x330070b38},
            "arms": {"red": 0x330070b70, "green": 0x330070b74, "blue": 0x330070b78},
            "legs": {"red": 0x330070bb0, "green": 0x330070bb4, "blue": 0x330070bb8},
            "shirt": {"red": 0x330070cf0, "green": 0x330070cf4, "blue": 0x330070cf8},
            "socks": {"red": 0x330070d30, "green": 0x330070d34, "blue": 0x330070d38},
            "pants": {"red": 0x330070db0, "green": 0x330070db4, "blue": 0x330070db8},
            "hidden rgb 1": {"red": 0x330070c30, "green": 0x330070c34, "blue": 0x330070c38},
            "hidden rgb 2": {"red": 0x330070c70, "green": 0x330070c74, "blue": 0x330070c78},
            "hidden rgb 3": {"red": 0x330070cb0, "green": 0x330070cb4, "blue": 0x330070cb8},
        },
        "body_mods": {
            "Fatness": 0x330060160,
            "Skinniness": 0x330060164,
            "Eye Width": 0x330060120,
            "Eye Height": 0x3300601a4,
            "Brow Height": 0x33006016c,
            "Brow Rotation": 0x330060168,
            "Brow Profile": 0x330060170,
            "Nose Length": 0x33006017c,
            "Nose Width": 0x330060178,
            "Nose Height": 0x330060180,
            "Nose Curve": 0x330060174,
            "Jaw Definition": 0x330060198,
            "Jaw Roundness": 0x33006019c,
            "Mouth Width": 0x330060184,
            "Mouth Smile": 0x330060188,
            "Mouth Fullness": 0x33006018c,
            "Mouth Height": 0x330060190,
            "Chin Length": 0x330060194,
        },
        "settings": {
            "Stance": {"address": 0x3018f2033, "options": [(0, "Goofy"), (1, "Regular")]},
            "Style": {"address": 0x3018f2037, "options": [(0, "Standard"), (1, "Loose"), (2, "OG"), (3, "Aggressive")]},
            "Posture": {"address": 0x3018f203b, "options": [(0, "Default"), (1, "Straight"), (2, "Hunched"), (3, "Macho")]},
            "Trucks Tightness": {"address": 0x3018f2024, "options": None},
            "Wheels Hardness": {"address": 0x3018f2028, "options": None},
            "Gender": {"address": 0x3018f2050, "options": [(0, "Female"), (1, "Male")]},
        },
    },
    5: {
        "rgb_colors": {
            "hat": {"red": 0x330070e30, "green": 0x330070e34, "blue": 0x330070e38},
            "hair": {"red": 0x330070e70, "green": 0x330070e74, "blue": 0x330070e78},
            "head": {"red": 0x330070eb0, "green": 0x330070eb4, "blue": 0x330070eb8},
            "arms": {"red": 0x330070ef0, "green": 0x330070ef4, "blue": 0x330070ef8},
            "legs": {"red": 0x330070f30, "green": 0x330070f34, "blue": 0x330070f38},
            "shirt": {"red": 0x330071070, "green": 0x330071074, "blue": 0x330071078},
            "socks": {"red": 0x3300710b0, "green": 0x3300710b4, "blue": 0x3300710b8},
            "pants": {"red": 0x330071130, "green": 0x330071134, "blue": 0x330071138},
            "hidden rgb 1": {"red": 0x330070fb0, "green": 0x330070fb4, "blue": 0x330070fb8},
            "hidden rgb 2": {"red": 0x330070ff0, "green": 0x330070ff4, "blue": 0x330070ff8},
            "hidden rgb 3": {"red": 0x330071030, "green": 0x330071034, "blue": 0x330071038},
        },
        "body_mods": {
            "Fatness": 0x3300601b0,
            "Skinniness": 0x3300601b4,
            "Eye Width": 0x330060170,
            "Eye Height": 0x3300601f4,
            "Brow Height": 0x3300601bc,
            "Brow Rotation": 0x3300601b8,
            "Brow Profile": 0x3300601c0,
            "Nose Length": 0x3300601cc,
            "Nose Width": 0x3300601c8,
            "Nose Height": 0x3300601d0,
            "Nose Curve": 0x3300601c4,
            "Jaw Definition": 0x3300601e8,
            "Jaw Roundness": 0x3300601ec,
            "Mouth Width": 0x3300601d4,
            "Mouth Smile": 0x3300601d8,
            "Mouth Fullness": 0x3300601dc,
            "Mouth Height": 0x3300601e0,
            "Chin Length": 0x3300601e4,
        },
        "settings": {
            "Stance": {"address": 0x3018f7d93, "options": [(0, "Goofy"), (1, "Regular")]},
            "Style": {"address": 0x3018f7d97, "options": [(0, "Standard"), (1, "Loose"), (2, "OG"), (3, "Aggressive")]},
            "Posture": {"address": 0x3018f7d9b, "options": [(0, "Default"), (1, "Straight"), (2, "Hunched"), (3, "Macho")]},
            "Trucks Tightness": {"address": 0x3018f7d84, "options": None},
            "Wheels Hardness": {"address": 0x3018f7d88, "options": None},
            "Gender": {"address": 0x3018f7db0, "options": [(0, "Female"), (1, "Male")]},
        },
    },
}

GESTURES = {
    "Gesture 1": 0x3463ef15f,
    "Gesture 2": 0x3463ef16b,
    "Gesture 3": 0x3463ef167,
    "Gesture 4": 0x3463ef163,
}

GESTURE_OPTIONS = [
    (0, "Air Guitar"),
    (1, "Airplane"),
    (2, "Boxing"),
    (3, "Bruce"),
    (4, "Got the Time"),
    (5, "Horns"),
    (6, "Double Guns"),
    (7, "Dunno"),
    (8, "Finger Wag"),
    (9, "Fists"),
    (10, "Flex"),
    (11, "Flip Table"),
    (12, "Aaayyy!"),
    (13, "Freedom"),
    (14, "Why I Oughta"),
    (15, "Get Away!"),
    (16, "Get Outta Here"),
    (17, "Handcuffs"),
    (18, "High Pump"),
    (19, "Low Pump"),
    (20, "Prewind"),
    (21, "Peace"),
    (22, "Fingerpoint"),
    (23, "Raise the Roof"),
    (24, "Shaka"),
    (25, "Shrug"),
    (26, "Sky"),
    (27, "Snap!"),
    (28, "Soul Arch"),
    (29, "Nerd Alert"),
    (30, "Surf's Up"),
    (31, "Swing High"),
    (32, "Swing Low"),
    (33, "Throw Arms"),
    (34, "Thumbs Down"),
    (35, "Wings"),
    (36, "Yard Sale"),
    (37, "Invalid"),
]

# Recipe (full skater data blob) start address per skater, used by the
# RECIPES subtab to export/import a skater's whole loadout as a .recipe file.
RECIPE_LENGTH = 8048

RECIPE_ADDRESSES = {
    1: 0x018DE800,
    2: 0x018E4560,
    3: 0x018EA2C0,
    4: 0x018F0020,
    5: 0x018F5D80,
}

# Dropdown-ready view of just the color part names, capitalized for display
RGB_PARTS = list(SKATERS[1]["rgb_colors"].keys())

# Dropdown-ready view of the body-mod slider names, in CT order
BODY_MOD_FIELDS = list(SKATERS[1]["body_mods"].keys())

# ---------------------------------------------------------------------------
# RGB Swapping
# ---------------------------------------------------------------------------
# The RPCS3 tool's "swap" mechanic doesn't touch the R/G/B floats above at
# all - it writes a 16-byte swatch/material reference into a *second* slot
# that sits exactly 0x20 past each part's "red" float address. Whatever
# swatch that reference points to is what the part renders as, which is how
# e.g. socks can be made to render as the black custom board's color without
# ever touching a float. Every part in rgb_colors (including the hidden
# slots above) has one of these, so the target address is derived instead of
# hardcoded a second time.
#
# Only Hat / Shirt / Pants / Socks / Hidden RGB 1-3 exposed this swap slot in
# the original tool - hair/head/arms/legs never did, so they're left out of
# SWAP_TARGET_PARTS on purpose even though the +0x20 math would "work" for
# them too (untested territory in the original tool).
SWAP_TARGET_PARTS = ["hat", "shirt", "socks", "pants", "hidden rgb 1", "hidden rgb 2", "hidden rgb 3"]


def rgb_swap_target_address(skater: int, part: str) -> int:
    """Address to write a 16-byte swatch reference into for `part` (lowercase, e.g. 'socks')."""
    return SKATERS[skater]["rgb_colors"][part]["red"] + 0x20


# Fixed swatch reference for the black custom board (constant across skaters -
# it doesn't come from the recipe, it's just always this value in the tool).
BOARD_SWATCH_BYTES = bytes.fromhex("A8 41 A6 5D 5C 4D D5 93 00 00 44 E2 03 E3 88 17".replace(" ", ""))

# Everything else you can swap FROM is a live 16-byte swatch reference
# already sitting in that skater's clothing recipe data (same 8048-byte
# region RECIPE_ADDRESSES points at), so it has to be read from memory at
# swap time rather than hardcoded. Offsets are relative to RECIPE_ADDRESSES.
RGB_SWAP_SOURCE_OFFSETS = {
    "Current Necklace": 0x5CB0,
    "Current Glasses": 0x5C60,
    "Current Watch": 0x5C70,
    "Current Shoes": 0x5B70,
}

# "Current Shoes" gets its last byte bumped by 1 before being written to the
# target slot - carried over as-is from the RPCS3 tool, which does the same
# adjustment only for the shoes source.
RGB_SWAP_SHOES_BYTE_BUMP = 1

RGB_SWAP_SOURCES = ["Board"] + list(RGB_SWAP_SOURCE_OFFSETS.keys())


def rgb_swap_source_address(skater: int, source: str) -> int:
    """Address to read the 16-byte swatch reference from for a non-Board source."""
    return RECIPE_ADDRESSES[skater] + RGB_SWAP_SOURCE_OFFSETS[source]


# ---------------------------------------------------------------------------
# Clothing Lock
# ---------------------------------------------------------------------------
# Same recipe region as the RGB swap sources above - each of these is a
# 16-byte clothing-item reference that the game keeps re-reading from, so
# "locking" one just means continuously re-writing a snapshot of its bytes
# over whatever the game (or the player, in-game) tries to change it to.
# "Wrist Item" and "Current Watch" above are the same underlying slot -
# that's not a bug, the recipe only has one address for it.
CLOTHING_LOCK_OFFSETS = {
    "Hat": 0x5C40,
    "Shirt": 0x5C90,
    "Pants": 0x5C10,
    "Shoes": 0x5B70,
    "Wrist Item": 0x5C70,
}

CLOTHING_LOCK_ITEMS = list(CLOTHING_LOCK_OFFSETS.keys())

CLOTHING_LOCK_INTERVAL_MS = 500  # how often the lock re-writes its snapshot


def clothing_lock_address(skater: int, item: str) -> int:
    return RECIPE_ADDRESSES[skater] + CLOTHING_LOCK_OFFSETS[item]


# ---------------------------------------------------------------------------
# Missing Texture
# ---------------------------------------------------------------------------
# Every clothing/cosmetic slot in the recipe is a 16-byte reference: an 8-byte
# asset ID followed by an 8-byte material ID (parsed straight out of
# "Edit_Skater_Asset_Data.CT" - each entry there is "<Part> Asset Data" at
# RECIPE_ADDRESSES[skater] + this offset, with the leading "3" stripped same
# as everywhere else in this file, e.g. 3018EA1A0 -> 018EA1A0). Forcing an
# invalid material (by zeroing the first 4 bytes of the material half, while
# leaving the asset ID and the material's last 4 bytes alone) makes the game
# render that slot as a missing texture. Some players want that on purpose.
#
# ASSET_DATA_OFFSETS lists every slot found in the CT (kept here as the
# single source of truth for the whole recipe, not just the missing-texture
# subset below - Hat/Shirt reuse it for OTHER_CLOTHING_SLOT_ADDRESSES).
ASSET_DATA_OFFSETS = {
    "Arms": 0x5B20,
    "Legs": 0x5B30,
    "Hair": 0x5B40,
    "Rostral": 0x5B50,
    "Shoes": 0x5B70,
    "Ring": 0x5B80,
    "Eyes": 0x5BB0,
    "Board": 0x5BD0,
    "Trucks": 0x5BE0,
    "Wheels": 0x5BF0,
    "Pants": 0x5C10,
    "Socks": 0x5C30,
    "Hat": 0x5C40,
    "Glasses": 0x5C60,
    "Wrist Item": 0x5C70,
    "Inner Torso": 0x5C80,
    "Shirt": 0x5C90,
    "Necklace": 0x5CB0,
}


def asset_data_address(skater: int, part: str) -> int:
    return RECIPE_ADDRESSES[skater] + ASSET_DATA_OFFSETS[part]


# Excluded per instructions: doesn't work correctly on these slots. "outer
# and inner torso" = Shirt + Inner Torso (the two torso layers in the CT).
MISSING_TEXTURE_EXCLUDED = {"Arms", "Legs", "Hat", "Hair", "Inner Torso", "Shirt"}

# Dropdown-ready list: every asset-data slot except the excluded ones above.
MISSING_TEXTURE_ITEMS = [p for p in ASSET_DATA_OFFSETS if p not in MISSING_TEXTURE_EXCLUDED]

# In-game default flag for "this slot has nothing equipped" - both the asset
# ID half and material half are this same 8 bytes repeated. Used as a
# safety check before writing: if a slot reads as this, the skater isn't
# wearing anything there, so we skip the write instead of corrupting it.
MISSING_TEXTURE_UNEQUIPPED_FLAG = bytes([0x01, 0x67, 0x8C, 0x48, 0x62, 0x13, 0x90, 0x59] * 2)


def missing_texture_bytes(current_16_bytes: bytes) -> bytes:
    """Given the current 16-byte asset+material reference, return the bytes
    to write to force a missing texture: asset ID (first 8 bytes) and the
    material's last 4 bytes are kept, the material's first 4 bytes are
    zeroed."""
    return current_16_bytes[:8] + bytes(4) + current_16_bytes[12:16]


# ---------------------------------------------------------------------------
# Extra - Invisible parts + low poly / crash-fix recipe mods
# ---------------------------------------------------------------------------
# Flips between an "off" value and an "on" value at a fixed address. Most of
# these are a single byte (off is always 0x00), but Invisible Feet needs two
# bytes, so every entry stores explicit off/on byte strings instead of a bare
# on_byte - keeps the format uniform regardless of width. Not per-skater -
# the RPCS3 tool only ever had one set of these addresses, applying to
# whichever skater is currently being edited in-game.
# Kept in alphabetical order.
INVISIBLE_TOGGLES = {
    "Invisible Arms":   {"address": 0x401565AB0, "off": bytes([0x00]),       "on": bytes([0x41])},
    "Invisible Deck":   {"address": 0x401565B20, "off": bytes([0x00]),       "on": bytes([0x53])},
    "Invisible Eyes":   {"address": 0x401565B10, "off": bytes([0x00]),       "on": bytes([0x4F])},
    "Invisible Feet":   {"address": 0x3018E4376, "off": bytes([0x00, 0x00]), "on": bytes([0xC9, 0xCE])},
    "Invisible Head":   {"address": 0x401565AC8, "off": bytes([0x00]),       "on": bytes([0x52])},
    "Invisible Legs":   {"address": 0x401565AB8, "off": bytes([0x00]),       "on": bytes([0x4C])},
    "Invisible Torso":  {"address": 0x401565BB0, "off": bytes([0x00]),       "on": bytes([0x4F])},
    "Invisible Trucks": {"address": 0x401565B30, "off": bytes([0x00]),       "on": bytes([0x53])},
    "Invisible Wheels": {"address": 0x401565B40, "off": bytes([0x00]),       "on": bytes([0x53])},
}

# Invisible Pants doesn't follow the simple single-byte pattern above - it's
# the last byte of a 16-byte clothing reference, so "off" is a single 0x00
# byte but "on" is a full 16-byte replacement value.
INVISIBLE_PANTS_ADDRESS = 0x4018E4417
INVISIBLE_PANTS_ON_BYTES = bytes([
    0x85, 0x2C, 0x7F, 0x38, 0x17, 0x00, 0x17, 0x19,
    0xCD, 0x01, 0x67, 0x8C, 0x48, 0x62, 0x13, 0x90,
])

# Gender is stored per-skater (see each skater's settings["Gender"]) but the
# option list itself (code -> label) is identical for all 5, so it's pulled
# out once here for anything that needs to build a dropdown without caring
# which skater is selected yet.
GENDER_OPTIONS = SKATERS[1]["settings"]["Gender"]["options"]

# Dropdown-ready list of invisible-part mods, alphabetical. Gender used to
# live in here too (as an entry that swapped in a second dropdown), but now
# has its own always-visible dropdown in the UI instead, so it's not part of
# this list anymore.
EXTRA_MOD_NAMES = sorted(list(INVISIBLE_TOGGLES.keys()) + ["Invisible Pants"])

# ---------------------------------------------------------------------------
# Other Clothing - branded items (Dr Pepper promo set). Same 16-byte
# clothing-item-reference mechanism as Invisible Pants above, but unlike
# that one this IS per-skater - each of the 5 skaters has its own Hat/Shirt
# asset-data address. Two of the three items share the "Shirt" slot because
# they're both worn there - selecting one just overwrites whatever the
# other last wrote. Male/Female give different reference bytes for the same
# visual item (the game keeps separate gendered meshes).
#
# Addresses kept exactly as provided (PS3/ps3mapi addresses, i.e. the
# leading "3" from the RPCS3/Cheat Engine address already stripped - e.g.
# 3018EA1A0 -> 018EA1A0). Not derived/computed, so if a skater's item ends
# up wrong, recheck these first.
# ---------------------------------------------------------------------------
OTHER_CLOTHING_SLOT_ADDRESSES = {
    1: {"Hat": 0x018E4440, "Shirt": 0x018E4490},
    2: {"Hat": 0x018EA1A0, "Shirt": 0x018EA1F0},
    3: {"Hat": 0x018EFF00, "Shirt": 0x018EFF50},
    4: {"Hat": 0x018F5C60, "Shirt": 0x018F5CB0},
    5: {"Hat": 0x018FB9C0, "Shirt": 0x018FBA10},
}

OTHER_CLOTHING_ITEMS = {
    "Dr. Pepper Modern Shirt": {
        "slot": "Shirt",
        "Male":   bytes([0xB8, 0xA2, 0xA7, 0xB2, 0xBD, 0x70, 0x09, 0x07,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x17, 0x37, 0x54]),
        "Female": bytes([0xC5, 0x33, 0x89, 0x3D, 0xC2, 0xE8, 0xDB, 0x16,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x17, 0x37, 0x57]),
    },
    "Dr. Pepper Classic Shirt": {
        "slot": "Shirt",
        "Male":   bytes([0xB8, 0xA2, 0xA7, 0xB2, 0xBD, 0x70, 0x09, 0x07,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x17, 0x37, 0x52]),
        "Female": bytes([0xC5, 0x33, 0x89, 0x3D, 0xC2, 0xE8, 0xDB, 0x16,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x17, 0x37, 0x56]),
    },
    "Dr. Pepper Hat": {
        "slot": "Hat",
        "Male":   bytes([0xFB, 0x7C, 0xF1, 0xAE, 0x12, 0x3F, 0x35, 0x36,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x09, 0x2E, 0x2C]),
        "Female": bytes([0xD7, 0xD8, 0xBA, 0x03, 0x1C, 0xD0, 0x97, 0xCD,
                          0x2C, 0x7F, 0x38, 0x17, 0x00, 0x09, 0x2E, 0x2C]),
    },
}


def other_clothing_address(skater: int, item_name: str) -> int:
    slot = OTHER_CLOTHING_ITEMS[item_name]["slot"]
    return OTHER_CLOTHING_SLOT_ADDRESSES[skater][slot]

# Dropdown-ready list, in the same order the items are defined above.
OTHER_CLOTHING_NAMES = list(OTHER_CLOTHING_ITEMS.keys())

# ---------------------------------------------------------------------------
# Team / Player Names
# ---------------------------------------------------------------------------
# Fixed-length, zero-terminated ASCII strings, one buffer each - not
# per-skater, these are team-roster slots. `length` is the full buffer size
# in memory (including the zero terminator), taken straight from the CT
# table, so the max usable characters is `length - 1`.
NAME_FIELDS = {
    "Team Name":     {"address": 0x300DC3AC, "length": 16},
    "Player 1 Name": {"address": 0x30074650, "length": 6},
    "Player 2 Name": {"address": 0x300DC031, "length": 8},
    "Player 3 Name": {"address": 0x300DC05D, "length": 8},
    "Player 4 Name": {"address": 0x300DC089, "length": 8},
    "Player 5 Name": {"address": 0x300DC0B5, "length": 8},
}

# Skate 3's font maps these two characters to its "skate" and "bolt" icons -
# handy for team names, not typeable normally, so the UI offers a one-click
# copy for each.
NAME_ICON_SKATE = "\u00AB"  # «
NAME_ICON_BOLT = "\u00BB"   # »

# ---------------------------------------------------------------------------
# Graphics Spoofer
# ---------------------------------------------------------------------------
# Ported from the standalone "Graphics Spoofer PS3" tool (Form1.cs): a single
# "User ID" field written as a null-terminated ASCII string. That tool wrote
# it to a plain literal address (21828720 decimal), not per-skater and not
# length-bounded on the C# side - same here, address used exactly as given.
GRAPHICS_SPOOFER_USER_ID_ADDRESS = 0x14D1470

# ---------------------------------------------------------------------------
# Graphic Editor - rotation / scale / x / y for each of a skater's 5 custom
# graphic slots, from Skate_3_Skaters.CT. Every slot is 16 bytes: four
# consecutive big-endian floats in memory in this exact order - Rotation,
# Scale, X, Y - so a single 16-byte read/write covers all four fields at
# once instead of doing it one float at a time.
#
# CT addresses are the RPCS3-tool style 9-digit 0x3XXXXXXXX values; PS3
# addresses are 8 digits, so (per usual) the fix is just dropping that
# leading "3" - e.g. the CT's 0x33005C4C0 becomes 0x3005C4C0 below.
GRAPHICS_BASE_ADDRESSES = {
    1: 0x3005C4C0,
    2: 0x3005C540,
    3: 0x3005C5C0,
    4: 0x3005C640,
    5: 0x3005C6C0,
}

# Offset of each graphic slot's 16-byte block, relative to that skater's
# GRAPHICS_BASE_ADDRESSES entry above. Order here is also the dropdown order.
GRAPHICS_SLOT_OFFSETS = {
    "Shirts": 0x00,
    "Upper Body Tattoo": 0x10,
    "Lower Body Tattoo": 0x20,
    "Skateboard": 0x30,
    "Hats": 0x40,
}

GRAPHICS_SLOTS = list(GRAPHICS_SLOT_OFFSETS.keys())

# Byte offset of each field within a slot's 16-byte block - this is also the
# on-disk float order (Rotation, Scale, X, Y), used for packing/unpacking
# the whole 16 bytes in one read/write.
GRAPHICS_FIELD_OFFSETS = {
    "Rotation": 0x0,
    "Scale": 0x4,
    "X": 0x8,
    "Y": 0xC,
}


def graphics_slot_address(skater: int, slot_name: str) -> int:
    return GRAPHICS_BASE_ADDRESSES[skater] + GRAPHICS_SLOT_OFFSETS[slot_name]

# ---------------------------------------------------------------------------
# Custom Graphic Injector - ported from the standalone "DDS Graphic Injector"
# test tool. Not per-skater: this is the game's account-wide bank of 4
# custom-photo graphic slots (the ones used for boards/shirts/tattoos/etc
# once assigned in-game), addressed the same "drop the leading 3" way as
# every other CT-derived address in this file.
#
# NOTE: BASE_ADDRESS below is still the test tool's *guess* at the real
# hardware address (RPCS3 base with the leading "3" dropped) - confirm it
# against real hardware before relying on it.
# ---------------------------------------------------------------------------
GRAPHIC_INJECTOR_BASE_ADDRESS = 0x427B6EF0
GRAPHIC_INJECTOR_SLOT_STRIDE = 0xB114
GRAPHIC_INJECTOR_HEADER_OFFSET = -0x102   # relative to slot base
GRAPHIC_INJECTOR_PIXEL_OFFSET = 0x238     # relative to slot base

# Built DDS files (128-byte header + full mip chain) are always exactly this
# size for the fixed 256x128 DXT5 slot format - dds_builder.build_dds()
# always produces this many bytes.
GRAPHIC_INJECTOR_DDS_HEADER_SKIP = 0x80     # 128-byte DDS header, stripped before writing pixel data
GRAPHIC_INJECTOR_EXPECTED_DDS_SIZE = 0xAB50  # 43856 bytes

GRAPHIC_INJECTOR_SLOTS = ["Slot 1", "Slot 2", "Slot 3", "Slot 4"]

# Fixed header blob written alongside the pixel data for each slot, always
# on in the background (not user-toggleable - see edit_skater_tab.py). Same
# bytes every time regardless of which DDS is injected - this is what tells
# the game the resource is still a valid texture (format/dimensions/etc)
# after the pixel data underneath it changes. Pulled directly from the
# original tool's Helpers.cs (GraphicHeaders list). A slot left as None has
# its header write skipped rather than failing the whole injection.
#
# NOTE: every slot should be 826 bytes (PIXEL_OFFSET - HEADER_OFFSET =
# 0x238 - (-0x102) = 0x33A = 826), matching slots 2-4 below. Slot 1 here is
# only 814 bytes (12 short) - carried over exactly as given; worth
# double-checking against the source before relying on it.
GRAPHIC_INJECTOR_HEADERS_HEX = [
    "AD 08 68 74 74 70 3A 2F 2F 64 6F 77 6E 6C 6F 61 64 73 2E 73 6B 61 74 65 2E 6F 6E 6C 69 6E 65 2E 65 61 2E 63 6F 6D 2F 73 6B 61 74 65 33 2F 63 6F 6E 74 65 6E 74 2F 50 53 33 2F 4C 4F 47 4F 2F 30 31 34 38 2F 31 37 34 30 39 34 38 2F 38 39 32 30 34 34 30 35 2E 70 73 67 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 89 52 57 34 70 73 33 00 0D 0A 1A 0A 01 20 04 00 34 35 34 00 30 30 30 00 00 00 00 00 08 AC 21 BD 00 00 00 04 00 00 00 04 00 00 00 10 00 00 00 00 00 00 01 D8 00 00 00 C0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 00 10 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 AA D0 00 00 00 80 00 00 03 90 00 00 00 04 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 04 00 00 00 04 00 00 00 0C 00 00 00 1C 00 00 00 50 00 00 00 74 00 00 00 90 00 01 00 05 00 00 00 0A 00 00 00 0C 00 00 00 00 00 01 00 30 00 01 00 31 00 01 00 32 00 01 00 33 00 01 00 34 00 01 00 35 00 02 00 E8 00 EB 00 08 00 EB 00 0B 00 01 00 06 00 00 00 03 00 00 00 18 08 AC 21 BD FF B0 00 00 08 AC 21 BD 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 02 38 00 00 00 00 00 01 00 08 00 00 00 00 00 00 00 00 88 09 02 00 00 00 AA E4 01 00 00 80 00 01 00 00 00 00 04 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 55 72 00 88 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 14 00 00 00 2C 00 00 00 00 00 00 00 40 00 00 00 2C 9B 0F 16 78 CD A8 D2 A6 C2 97 3D 90 AC 46 2E 4A 00 00 00 01 38 39 32 30 34 34 30 35 2E 54 65 78 74 75 72 65 00 00 00 00 00 00 00 19 00 00 00 04 00 00 00 00 00 00 00 00 00 00 AA D0 00 00 00 80 00 00 00 05 00 01 00 34 00 00 01 5C 00 00 00 00 00 00 00 28 00 00 00 04 00 00 00 07 00 02 00 E8 00 00 01 90 00 00 00 00 00 00 00 40 00 00 00 10 00 00 00 09 00 EB 00 0B 00 00 01 D0 00 00 00 00 00 00 00 08",  # Slot 1
    "AD 08 68 74 74 70 3A 2F 2F 64 6F 77 6E 6C 6F 61 64 73 2E 73 6B 61 74 65 2E 6F 6E 6C 69 6E 65 2E 65 61 2E 63 6F 6D 2F 73 6B 61 74 65 33 2F 63 6F 6E 74 65 6E 74 2F 50 53 33 2F 4C 4F 47 4F 2F 30 31 34 38 2F 31 37 34 30 39 34 38 2F 38 39 34 31 33 33 37 31 2E 70 73 67 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 89 52 57 34 70 73 33 00 0D 0A 1A 0A 01 20 04 00 34 35 34 00 30 30 30 00 00 00 00 00 CD FC F3 91 00 00 00 04 00 00 00 04 00 00 00 10 00 00 00 00 00 00 01 D8 00 00 00 C0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 00 10 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 AA D0 00 00 00 80 00 00 03 90 00 00 00 04 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 04 00 00 00 04 00 00 00 0C 00 00 00 1C 00 00 00 50 00 00 00 74 00 00 00 90 00 01 00 05 00 00 00 0A 00 00 00 0C 00 00 00 00 00 01 00 30 00 01 00 31 00 01 00 32 00 01 00 33 00 01 00 34 00 01 00 35 00 02 00 E8 00 EB 00 08 00 EB 00 0B 00 01 00 06 00 00 00 03 00 00 00 18 CD FC F3 91 FF B0 00 00 CD FC F3 91 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 02 38 00 00 00 00 00 01 00 08 00 00 00 00 00 00 00 00 88 09 02 00 00 00 AA E4 01 00 00 80 00 01 00 00 00 00 04 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 55 72 00 88 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 14 00 00 00 2C 00 00 00 00 00 00 00 40 00 00 00 2C 9B 0F 16 78 07 72 A2 B5 E0 11 95 04 AC 46 2E 4A 00 00 00 01 38 39 34 31 33 33 37 31 2E 54 65 78 74 75 72 65 00 00 00 00 00 00 00 19 00 00 00 04 00 00 00 00 00 00 00 00 00 00 AA D0 00 00 00 80 00 00 00 05 00 01 00 34 00 00 01 5C 00 00 00 00 00 00 00 28 00 00 00 04 00 00 00 07 00 02 00 E8 00 00 01 90 00 00 00 00 00 00 00 40 00 00 00 10 00 00 00 09 00 EB 00 0B 00 00 01 D0 00 00 00 00 00 00 00 08 00 00 00 00 00 00 00 00 00 00 00 00",  # Slot 2
    "AD 08 68 74 74 70 3A 2F 2F 64 6F 77 6E 6C 6F 61 64 73 2E 73 6B 61 74 65 2E 6F 6E 6C 69 6E 65 2E 65 61 2E 63 6F 6D 2F 73 6B 61 74 65 33 2F 63 6F 6E 74 65 6E 74 2F 50 53 33 2F 4C 4F 47 4F 2F 30 31 34 38 2F 31 37 34 30 39 34 38 2F 38 39 34 33 32 35 30 38 2E 70 73 67 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 89 52 57 34 70 73 33 00 0D 0A 1A 0A 01 20 04 00 34 35 34 00 30 30 30 00 00 00 00 00 56 4D 7D BE 00 00 00 04 00 00 00 04 00 00 00 10 00 00 00 00 00 00 01 D8 00 00 00 C0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 00 10 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 AA D0 00 00 00 80 00 00 03 90 00 00 00 04 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 04 00 00 00 04 00 00 00 0C 00 00 00 1C 00 00 00 50 00 00 00 74 00 00 00 90 00 01 00 05 00 00 00 0A 00 00 00 0C 00 00 00 00 00 01 00 30 00 01 00 31 00 01 00 32 00 01 00 33 00 01 00 34 00 01 00 35 00 02 00 E8 00 EB 00 08 00 EB 00 0B 00 01 00 06 00 00 00 03 00 00 00 18 56 4D 7D BE FF B0 00 00 56 4D 7D BE 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 02 38 00 00 00 00 00 01 00 08 00 00 00 00 00 00 00 00 88 09 02 00 00 00 AA E4 01 00 00 80 00 01 00 00 00 00 04 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 55 72 00 88 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 14 00 00 00 2C 00 00 00 00 00 00 00 40 00 00 00 2C 9B 0F 16 78 CB 14 20 53 EF 17 E5 8B AC 46 2E 4A 00 00 00 01 38 39 34 33 32 35 30 38 2E 54 65 78 74 75 72 65 00 00 00 00 00 00 00 19 00 00 00 04 00 00 00 00 00 00 00 00 00 00 AA D0 00 00 00 80 00 00 00 05 00 01 00 34 00 00 01 5C 00 00 00 00 00 00 00 28 00 00 00 04 00 00 00 07 00 02 00 E8 00 00 01 90 00 00 00 00 00 00 00 40 00 00 00 10 00 00 00 09 00 EB 00 0B 00 00 01 D0 00 00 00 00 00 00 00 08 00 00 00 10 00 00 00 08 00 EB 00 08",  # Slot 3
    "AD 08 68 74 74 70 3A 2F 2F 64 6F 77 6E 6C 6F 61 64 73 2E 73 6B 61 74 65 2E 6F 6E 6C 69 6E 65 2E 65 61 2E 63 6F 6D 2F 73 6B 61 74 65 33 2F 63 6F 6E 74 65 6E 74 2F 50 53 33 2F 4C 4F 47 4F 2F 30 31 34 38 2F 31 37 34 30 39 34 38 2F 38 39 35 38 39 39 35 35 2E 70 73 67 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 89 52 57 34 70 73 33 00 0D 0A 1A 0A 01 20 04 00 34 35 34 00 30 30 30 00 00 00 00 00 42 36 0F 51 00 00 00 04 00 00 00 04 00 00 00 10 00 00 00 00 00 00 01 D8 00 00 00 C0 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 00 10 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 AA D0 00 00 00 80 00 00 03 90 00 00 00 04 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 04 00 00 00 04 00 00 00 0C 00 00 00 1C 00 00 00 50 00 00 00 74 00 00 00 90 00 01 00 05 00 00 00 0A 00 00 00 0C 00 00 00 00 00 01 00 30 00 01 00 31 00 01 00 32 00 01 00 33 00 01 00 34 00 01 00 35 00 02 00 E8 00 EB 00 08 00 EB 00 0B 00 01 00 06 00 00 00 03 00 00 00 18 42 36 0F 51 FF B0 00 00 42 36 0F 51 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 07 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 38 00 00 02 38 00 00 00 00 00 01 00 08 00 00 00 00 00 00 00 00 88 09 02 00 00 00 AA E4 01 00 00 80 00 01 00 00 00 00 04 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 55 72 00 88 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 14 00 00 00 2C 00 00 00 00 00 00 00 40 00 00 00 2C 9B 0F 16 78 50 61 97 ED D7 9A 6F 60 AC 46 2E 4A 00 00 00 01 38 39 35 38 39 39 35 35 2E 54 65 78 74 75 72 65 00 00 00 00 00 00 00 19 00 00 00 04 00 00 00 00 00 00 00 00 00 00 AA D0 00 00 00 80 00 00 00 05 00 01 00 34 00 00 01 5C 00 00 00 00 00 00 00 28 00 00 00 04 00 00 00 07 00 02 00 E8 00 00 01 90 00 00 00 00 00 00 00 40 00 00 00 10 00 00 00 09 00 EB 00 0B 00 00 01 D0 00 00 00 00 00 00 00 08 00 00 00 00 00 00 00 00 00 00 00 00",  # Slot 4
]


def graphic_injector_pixel_address(slot_index: int) -> int:
    return GRAPHIC_INJECTOR_BASE_ADDRESS + slot_index * GRAPHIC_INJECTOR_SLOT_STRIDE + GRAPHIC_INJECTOR_PIXEL_OFFSET


def graphic_injector_header_address(slot_index: int) -> int:
    return GRAPHIC_INJECTOR_BASE_ADDRESS + slot_index * GRAPHIC_INJECTOR_SLOT_STRIDE + GRAPHIC_INJECTOR_HEADER_OFFSET
