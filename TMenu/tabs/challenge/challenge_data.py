"""
challenge_data.py
==================
Address/value data for the top-level CHALLENGE tab (PARTY PLAY and TIMERS
subtabs - see challenge_tab.py).

All addresses are plain 8-digit PS3 addresses. The ones that came from a
Cheat Engine table as 9 digits (3xxxxxxxx) have had their leading "3"
dropped, e.g. 3309848F8 -> 309848F8.

PARTY PLAY
    PARTY_PLAY_TOGGLES      "Better Party Play" - a normal on/off toggle
                            (same shape as toggleables_data's toggles, so
                            BINDS / SAVE CONFIG / RESET handle it as before).
    ONE_PLAYER_PARTY_PLAY   one-way write of 01 to 3004A487. NOT a normal
                            toggle: it has no "off", and it only works if
                            it's pressed in the Party Play player-amount
                            select screen, WITHOUT changing the selection,
                            and then X is pressed in-game.

TIMERS
    TIMER_FIELDS            big-endian float fields (field_widgets specs).
                            Each one's default is the game's vanilla value,
                            which is what SET writes if the box is left
                            empty - so an empty SET (or SET ALL) puts the
                            timer back to normal.
"""

from ui.field_widgets import simple_float_field


def _op(hex_str: str) -> bytes:
    """Raw 4-byte opcode/int from a hex string."""
    return bytes.fromhex(hex_str)


# ---------------------------------------------------------------------------
# Party Play
# ---------------------------------------------------------------------------
PARTY_PLAY_TOGGLES = {
    "Better Party Play": {
        "writes": [
            {"address": 0x0108C4A0, "off": _op("91630014"), "on": _op("60000000")},
            {"address": 0x00590604, "off": _op("F8A30030"), "on": _op("38000001")},
            {"address": 0x001D4838, "off": _op("99460068"), "on": _op("38000000")},
        ],
    },
}

ONE_PLAYER_PARTY_PLAY = {
    "address": 0x3004A487,
    "value": bytes([0x01]),
}

# ---------------------------------------------------------------------------
# Timers - (label, address, vanilla default seconds)
# ---------------------------------------------------------------------------
TIMER_FIELDS = [
    simple_float_field("Ragdoll Settled Timer", 0x40E5F398, default=3.5),
    simple_float_field("Hall Of Meat Timer", 0x40E5F3A4, default=20.0),
    simple_float_field("Ragdoll Settle Time", 0x40E5F2D0, default=0.5),
    simple_float_field("S.K.A.T.E. Timer", 0x309626A8, default=15.0),
    simple_float_field("1up Timer", 0x3098B858, default=20.0),
    simple_float_field("Hall Of Meat Challenge Timer", 0x309848F8, default=15.0),
    simple_float_field("15 Second Spot Battle Timer", 0x30A134B8, default=15.0),
]
