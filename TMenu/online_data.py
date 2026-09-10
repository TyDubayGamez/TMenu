"""
online_data.py
================
Address/data constants for the ONLINE tab's four subtabs (CHALLENGES /
SERVER / TOGGLEABLES / TELEPORTER). Mirrors the toggleables_tab /
toggleables_data split - this file has no UI code, just addresses, presets,
JSON paths, and the small pack/unpack helpers the ONLINE tab's subtabs
share.
"""

import os
import struct

from app_paths import base_dir

HERE = base_dir()

# -- Challenges --------------------------------------------------------------
CHALLENGE_TYPES_PATH = os.path.join(HERE, "challenge_types.json")
CHALLENGE_KEYS_PATH = os.path.join(HERE, "challenge_keys.json")
# Export/Import no longer read/write a single fixed challenge.json - see
# online_tab.py's CHALLENGES export/import, which now go through a Save/Open
# dialog defaulted into the challenge/ folder (app_paths.export_dir) instead.

ADDR_CHALLENGE_TYPE = 0x3019AB0C0
ADDR_CHALLENGE_KEY = 0x3019AB120
ADDR_IS_PRIVATE = 0x3019AB1E0
ADDR_IS_TEAM = 0x3019AB3C0
ADDR_DIFFICULTY = 0x3019AB5A0

DIFFICULTY_OPTIONS = [("Easy", "0"), ("Normal", "1"), ("Hardcore", "2")]
BOOL_OPTIONS = ["False", "True"]

# Field width the challenge type is packed to at ADDR_CHALLENGE_TYPE (matches
# the 32 used for it in online_tab.py's do_apply).
CHALLENGE_TYPE_FIELD_WIDTH = 32

# Freeskate toggle (ONLINE > TOGGLEABLES) - just writes the challenge type
# straight to ADDR_CHALLENGE_TYPE as ascii, same address/mechanism as the
# CHALLENGES subtab's own "Set Challenge". "22" is the Freeskate challenge
# type, "53" (Spot Battle) is what it's set back to for off.
FREESKATE_TYPE_ON = "22"
FREESKATE_TYPE_OFF = "53"

# -- Server --------------------------------------------------------------------
IP_FIELD_ADDRESS = 0x01537528
IP_FIELD_WIDTH = 64  # generous fixed field so a shorter IP fully clears a longer one

BLAZE_TOKEN_ADDRESS = 0x300711E0
BLAZE_TOKEN_MAX_LEN = 256  # sanity cap on the null-terminator scan

SERVER_PRESETS = [
    ("Wispp's Server", "172.237.109.212"),
    ("Default (gosredirector.ea.com)", "gosredirector.ea.com"),
    ("Custom", None),
]

# -- Toggleables (Challenge Boundary) ------------------------------------------
ADDR_BORDER_FLAG_1 = 0x30205EB3
ADDR_BORDER_FLAG_2 = 0x30205ECB
ADDR_BORDER_OPCODE = 0x0155BB6E

DISABLE_OPCODE_BYTES = b"asd"
ORIGINAL_OPCODE_BYTES = bytes([0x25, 0x79, 0x2E])

# -- Teleporter ------------------------------------------------------------------
# Skater 1's X coordinate. Skaters 2-6 sit at the same offset apart.
SKATER_BASE_ADDR = 0x30192A530
SKATER_STRIDE = 0xD0
NUM_SKATERS = 6

# Where the game reads the position to snap the local player to, plus the
# two trigger bytes that tell it "apply that position now".
TELEPORT_ADDR = 0x47C98D20
TELEPORT_FLAG_1 = 0x47C98DD0
TELEPORT_FLAG_2 = 0x47C68157

# Nudge the target up a bit so the skater doesn't land clipped into the
# ground/geometry at the exact recorded height.
TELEPORT_Y_OFFSET = 0.5

VEC3_BE = struct.Struct(">fff")  # X, Y, Z packed as big-endian floats


# -- Shared pack/unpack helpers --------------------------------------------------
def pack_ascii(value: str, field_width: int) -> bytes:
    """ASCII string + null terminator, padded with extra zero bytes out to a
    fixed field width so leftover bytes from a longer previous value can't
    survive a shorter write."""
    data = value.encode("ascii") + b"\x00"
    if len(data) < field_width:
        data += b"\x00" * (field_width - len(data))
    return data[:field_width]


def read_null_terminated_string(state, address: int, max_len: int) -> str:
    """Reads bytes at `address` up to `max_len`, stopping at the first 0x00."""
    raw = bytes(state.ps3.Process.Memory.Get(state.pid, address, max_len))
    end = raw.find(b"\x00")
    if end != -1:
        raw = raw[:end]
    return raw.decode("ascii", errors="replace")


def skater_addr(index: int) -> int:
    """index is 0-based (0 = Player 1 ... 5 = Player 6)."""
    return SKATER_BASE_ADDR + index * SKATER_STRIDE
