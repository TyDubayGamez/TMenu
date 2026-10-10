"""
recipe_type.py
===============
Works out what KIND of recipe a blob of recipe bytes is - Marquee (a pro /
AI skater), Living World (peds and props), Vehicle, or Create-a-Character
(the player's own `cas_db` skater) - straight from the recipe's header.

NOT USED ANYWHERE YET. It's here for later (e.g. a texture swapper that
needs to know which texture folder a recipe pulls from). Nothing imports it,
so it has no effect on the running app.

Where the type lives
--------------------
The start of every recipe looks like this:

    00 00 00 07          always the same
    00 00 00 NN          NN = length of the recipe name   (byte 7)
    <NN bytes>           the recipe name, e.g. "cas_db"
    00 00 00 TT          TT = the recipe type             (byte 0x0B + NN)

So the first 8 bytes only tell you how long the name is (byte 7); the type
byte sits right after the name, at offset 0x0B + name_length. Because the
name length varies, that offset isn't fixed - but it's always found by
reading byte 7 first.

    TT   type
    --   -------------------------------
    00   Marquee
    01   Living World
    02   Vehicle
    03   Create-a-Character (cas_db)
    04   Undefined
    05   Test

The names/values follow the S3RecipeHandler project's RecipeTypes enum
(https://github.com/l-S4M-l/S3RecipeHandler, credits there: S4M, Wispp). On
the 181 default recipes that ship with TMenu, Marquee/MarqueeDLC files are
all 00, LivingWorld files all 01, and Vehicle files all 02. This module
re-implements just that one header read - no code is copied from it.

    from tabs.edit_skater.recipe_type import read_recipe_type, recipe_type_label

    kind = read_recipe_type(raw)        # RecipeType.VEHICLE, or None
    print(recipe_type_label(raw))       # "Vehicle" / "Unknown" / ...
"""

from enum import IntEnum
from typing import Optional


class RecipeType(IntEnum):
    MARQUEE = 0
    LIVINGWORLD = 1
    VEHICLE = 2
    CREATEACHARACTER = 3
    UNDEFINED = 4
    TEST = 5


RECIPE_TYPE_LABELS = {
    RecipeType.MARQUEE: "Marquee",
    RecipeType.LIVINGWORLD: "Living World",
    RecipeType.VEHICLE: "Vehicle",
    RecipeType.CREATEACHARACTER: "Create-a-Character",
    RecipeType.UNDEFINED: "Undefined",
    RecipeType.TEST: "Test",
}

_MAGIC = b"\x00\x00\x00\x07"   # every recipe starts with this
_NAME_LEN_POS = 7              # last byte of the 4-byte name length
_NAME_POS = 8                  # the name starts right after those 8 bytes
_TYPE_POS_BASE = 0x0B          # type byte = this + name length


def read_recipe_name(raw: bytes) -> Optional[str]:
    """The recipe's name (e.g. "cas_db"), or None if `raw` isn't a recipe header."""
    if len(raw) < _NAME_POS or bytes(raw[:4]) != _MAGIC:
        return None
    end = _NAME_POS + raw[_NAME_LEN_POS]
    if raw[_NAME_LEN_POS] == 0 or len(raw) <= end:
        return None
    return bytes(raw[_NAME_POS:end]).decode("ascii", errors="replace")


def read_recipe_type(raw: bytes) -> Optional[RecipeType]:
    """The recipe's type, or None if `raw` doesn't look like a recipe or its
    type byte isn't one of the known values. Only reads the header, so it
    works on a partial buffer as long as it covers the name + 4 bytes."""
    if len(raw) < _NAME_POS or bytes(raw[:4]) != _MAGIC:
        return None
    pos = _TYPE_POS_BASE + raw[_NAME_LEN_POS]
    if raw[_NAME_LEN_POS] == 0 or pos >= len(raw):
        return None
    try:
        return RecipeType(raw[pos])
    except ValueError:
        return None


def recipe_type_label(raw: bytes) -> str:
    """Display name for the recipe's type ("Vehicle", ...), or "Unknown"."""
    kind = read_recipe_type(raw)
    return RECIPE_TYPE_LABELS[kind] if kind is not None else "Unknown"
