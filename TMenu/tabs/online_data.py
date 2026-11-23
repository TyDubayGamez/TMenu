"""
online_data.py
================
Address/data constants for the ONLINE tab's four subtabs (CHALLENGES /
SERVER / TOGGLEABLES / PLAYERS). Mirrors the toggleables_tab /
toggleables_data split - this file has no UI code, just addresses, presets,
JSON paths, and the small pack/unpack helpers the ONLINE tab's subtabs
share.
"""

import os
import struct

from core.app_paths import data_dir

HERE = data_dir()

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

# Allow Proposals (ONLINE > TOGGLEABLES) - not a real toggle, every click just
# writes "true" + a 00 terminator (5 bytes) so it fully overwrites the 5-char
# word "false" that's normally there. Address is exactly as given (9 hex digits).
ADDR_ALLOW_PROPOSALS = 0x3019AB600
ALLOW_PROPOSALS_BYTES = b"true\x00"

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
ADDR_BORDER_FLAG_2_END = 0x30205FA0  # exclusive - zero-fill range for Reset
ADDR_BORDER_OPCODE = 0x0155BB6E

DISABLE_OPCODE_BYTES = b"asd"
ORIGINAL_OPCODE_BYTES = bytes([0x25, 0x73, 0x2E])

# Reset now zeroes the whole FLAG_2 region (30205ECB - 30205FA0) instead of
# just the single leading byte.
BORDER_FLAG_2_RESET_BYTES = bytes(ADDR_BORDER_FLAG_2_END - ADDR_BORDER_FLAG_2)

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

# -- Reset Player (RTM) -----------------------------------------------------------
# Patches the function at RESET_FUNC_ADDR from `lwz r9,4(r3)` to `li r9,N`
# (N = the player's slot, 0-5), pokes the two trigger bytes (the same two as
# TELEPORT_FLAG_1/2) to 0x02, waits, then puts the original bytes back.
RESET_FUNC_ADDR = 0x00698244
RESET_FUNC_ORIG = bytes.fromhex("81230004")
# TELEPORT_FLAG_1 (...DD0) is the debug cam write - the reset does NOT touch it
# (the teleport that runs just before the reset already did). Only the other
# trigger byte is poked here.
RESET_EXTRA_ADDRS = (TELEPORT_FLAG_2,)
RESET_EXTRA_VALUE = 0x02
RESET_RESTORE_DELAY = 2.0     # seconds after the last write, before restoring
# 1 byte, 0-5: which player slot is the local player ("YOU")
LOCAL_PLAYER_INDEX_ADDR = 0x301DE927


def li_r9(n: int) -> bytes:
    return (0x39200000 | n).to_bytes(4, "big")   # 39 20 00 0N


# -- Player list (names of everyone in the online lobby) ------------------------
# Player 1's name; each following slot sits PLAYER_NAME_STRIDE bytes apart.
# Read in one go: 5 strides + one name field covers all 6 slots. A name that
# starts with 0x00 is an empty slot; if player 1's first byte is 0xAB the game
# isn't in an online lobby yet and the names aren't populated.
PLAYER_NAME_BASE = 0x300853B8
PLAYER_NAME_STRIDE = 0xA8
PLAYER_NAME_MAX = 0x20
PLAYER_LIST_READ_LEN = PLAYER_NAME_STRIDE * (NUM_SKATERS - 1) + PLAYER_NAME_MAX
PLAYER_OFFLINE_MARKER = 0xAB


def parse_player_names(raw: bytes):
    """Returns (names, in_online_game). `names` has NUM_SKATERS entries, each
    the ASCII name or None for an empty slot."""
    raw = bytes(raw)
    if raw and raw[0] == PLAYER_OFFLINE_MARKER:
        return [None] * NUM_SKATERS, False
    names = []
    for i in range(NUM_SKATERS):
        chunk = raw[i * PLAYER_NAME_STRIDE:i * PLAYER_NAME_STRIDE + PLAYER_NAME_MAX]
        if not chunk or chunk[0] == 0:
            names.append(None)
            continue
        end = chunk.find(b"\x00")
        names.append(chunk[: end if end != -1 else len(chunk)].decode("ascii", errors="replace"))
    return names, True


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
