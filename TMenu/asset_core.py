"""
asset_core.py
=============
Pure-Python (no Qt, no tkinter) byte-level logic behind TMenu's ASSETS subtab.

Everything here works on the raw recipe bytes by *splicing*, never by
re-serialising the whole recipe. Anything the parser doesn't understand
(body mods, graphic vectors, unknown filler bytes, the odd "female Rostral"
extra texture loops) is therefore carried through untouched. This is the same
approach as the standalone recipe editor's recipe_core.py / apply_patches(),
trimmed down to what the asset editor needs and with the tkinter parts removed.

Layout facts this relies on (all taken from the recipe editor's walker):
  header .. recipe name .. type .. flag(0x02 = texture folder unlocked)
  [asset list count byte]
  asset list   = 4B name len + name + 3 zero bytes + 1B asset count
    asset      = 8B AssetID + 4B model count
      model    = 0x25B block (lod, arena 8, model name 8, filler 8, material 8,
                 4B texture count) + textures (4B chan len + chan + 8B name)
  tail (only if flag == 2): gender, RGB blocks (0x2C each), graphic links,
                 body mods (76B), graphic vectors (80B)
  footer: zero pad to a 4-byte boundary + 4B big-endian (file length - 4)

Public API (all functions take/return `bytes`; nothing mutates in place):
  list_assets(raw)                      -> [AssetInfo]
  find_asset(raw, label)                -> AssetInfo | None
  remove_asset(raw, label)              -> new_raw
  fix_crash(raw)                        -> (new_raw, changed_count)
  apply_low_poly(raw, label_or_None)    -> (new_raw, changed_count)
  add_saved_asset(raw, saved)           -> (new_raw, message)
  export_saved_asset(raw, label)        -> dict  (JSON-ready)
  get_asset_rgb(raw, label)             -> (r, g, b) | None
  set_asset_rgb(raw, labels, rgb)       -> new_raw
Every function that edits raises AssetEditError with a readable message if
the edit can't be done safely; the input is never modified.
"""

import struct
from dataclasses import dataclass, field

SAVED_FORMAT = "TMenuAsset"
SAVED_VERSION = 1
MAX_RECIPE_LENGTH = 8048   # same as edit_skater_data.RECIPE_LENGTH
TAIL_SIGNATURE = b"\x01\x00\x00\x00\x06"   # opens the gender/colors/graphics tail


class AssetEditError(Exception):
    """Raised when an edit is refused or would produce an unreadable recipe."""


# =============================================================================
# Small helpers
# =============================================================================

def hex_id(raw: bytes) -> str:
    return "0x" + bytes(raw).hex().upper()


def psg_name(raw: bytes) -> str:
    """Same 8 bytes as the on-disk file name the game resolves them to."""
    return "0x" + bytes(raw).hex().upper() + ".psg"


def _u32(v: int) -> bytes:
    return struct.pack(">I", v)


def looks_like_recipe(raw: bytes) -> bool:
    """Cheap sanity check before touching a memory buffer: every recipe starts
    00 00 00 07 <4B name length> and has a plausible name length."""
    return len(raw) > 0x20 and raw[:4] == b"\x00\x00\x00\x07" and raw[4:7] == b"\x00\x00\x00" and 0 < raw[7] < 0x40


# =============================================================================
# Offset walker
# =============================================================================

def _force_flag(raw: bytes) -> bytes:
    """Scratch copy with the texture-unlock flag forced to 0x02, so the tail is
    read whenever it is really there (the flag is an in-game toggle, not a
    promise about the file). Real bytes are never touched."""
    scratch = bytearray(raw)
    if len(raw) > 7:
        off = 0x13 + raw[7]
        if off < len(raw):
            scratch[off] = 2
    return bytes(scratch)


def compute_offsets(raw: bytes) -> dict:
    """Walk `raw` and record (start, end) spans for everything we might edit.
    Mirrors recipe_core.compute_offsets, plus whole-asset / whole-model spans."""
    data = _force_flag(raw)
    name_length = data[7]
    offsets = {
        "flag": (0x13 + name_length, 0x13 + name_length + 1),
        "recipe_name": data[8:8 + name_length].decode("ascii", errors="replace"),
    }

    index = 0x18 + name_length
    offsets["asset_list_count_pos"] = index - 1

    asset_lists = []
    for _ in range(data[index - 1]):
        al_start = index
        name_len = data[index + 3]
        index += 8 + name_len
        al = {
            "header": (al_start, index),
            "count_pos": index - 1,
            "folder_name": data[al_start + 4:al_start + 4 + name_len].decode("ascii", errors="replace"),
            "assets": [],
        }
        for _ in range(data[index - 1]):
            a_start = index
            index += 0x0C
            asset = {
                "asset_id": (a_start, a_start + 8),
                "model_count": (a_start + 8, a_start + 0x0C),
                "models": [],
            }
            for _ in range(data[index - 1]):
                m_start = index
                index += 0x25
                model = {
                    "lod": (m_start, m_start + 1),
                    "arena_id": (m_start + 1, m_start + 9),
                    "model_name": (m_start + 9, m_start + 17),
                    "material_id": (m_start + 0x19, m_start + 0x21),
                    "textures": [],
                }
                texture_loops = data[index - 0x11]   # "female Rostral" oddity
                for _ in range(data[index - 1]):
                    t_start = index
                    chan_len = data[index + 3]
                    name_start = index + 4 + chan_len
                    index += 12 + chan_len
                    model["textures"].append({
                        "channel": (t_start + 4, name_start),
                        "name": (name_start, name_start + 8),
                    })
                for _ in range(texture_loops - 1):
                    index += 0x10
                    for _ in range(data[index - 1]):
                        index += 12 + data[index + 3]
                model["span"] = (m_start, index)
                asset["models"].append(model)
            asset["span"] = (a_start, index)
            al["assets"].append(asset)
        al["span"] = (al_start, index)
        asset_lists.append(al)

    offsets["asset_lists"] = asset_lists
    offsets["asset_lists_end"] = index
    offsets["has_tail"] = False
    offsets["rgb_blocks"] = []
    offsets["rgb_count_spans"] = None
    offsets["rgb_blocks_end"] = None
    offsets["tail_parse_error"] = None

    tail_index = index
    try:
        # A real tail always opens with 01 00 00 00 06. Without it, whatever
        # follows the asset lists is just the footer / zero padding of a live
        # memory buffer - reading that as a tail is what put new colors in the
        # wrong place.
        if data[index:index + 5] != TAIL_SIGNATURE:
            raise ValueError("no color/graphics tail")
        tail_index += 5
        gender_idx = tail_index
        _ = data[gender_idx]
        rgb_count_spans = ((gender_idx + 1, gender_idx + 5), (gender_idx + 5, gender_idx + 9))
        tail_index += 9
        rgb_blocks = []
        for _ in range(data[tail_index - 1]):
            s = tail_index
            tail_index += 0x2C
            if tail_index > len(data):
                raise IndexError("index out of range")
            rgb_blocks.append({
                "block": (s, tail_index),
                "index": (s, s + 4),
                "r": (s + 4, s + 8), "g": (s + 8, s + 12), "b": (s + 12, s + 16),
                "r2": (s + 16, s + 20), "g2": (s + 20, s + 24), "b2": (s + 24, s + 28),
                "asset_id": (s + 0x1C, s + 0x24),
                "material_id": (s + 0x24, s + 0x2C),
            })
        rgb_blocks_end = tail_index
        tail_index += 8
        for _ in range(data[tail_index - 1]):
            url_len = data[tail_index + 3]
            tail_index += 5 + 24 + url_len + 1
            if tail_index > len(data):
                raise IndexError("index out of range")
        bm_start = tail_index + 4
        gv_start = bm_start + 76 + 20
        if gv_start + 80 <= len(data):
            tail_index = gv_start + 80
    except Exception as e:
        offsets["tail_parse_error"] = f"{type(e).__name__}: {e}"
    else:
        index = tail_index
        offsets["has_tail"] = True
        offsets["rgb_count_spans"] = rgb_count_spans
        offsets["rgb_blocks_end"] = rgb_blocks_end
        offsets["rgb_blocks"] = rgb_blocks

    offsets["end_index"] = index
    return offsets


def _footer(end_index: int):
    pad = 4 - (end_index % 4) if end_index % 4 != 0 else 4
    field_start = end_index + pad
    return field_start, struct.pack(">I", field_start)   # length - 4 == field_start


def fix_footer(raw: bytes, end_index: int) -> bytes:
    """Rebuild the trailing zero-pad + length footer after `end_index`."""
    field_start, field_bytes = _footer(end_index)
    return raw[:end_index] + b"\x00" * (field_start - end_index) + field_bytes


def recipe_length(raw: bytes) -> int:
    """Real length of the recipe inside a (possibly zero-padded) buffer."""
    field_start, _ = _footer(compute_offsets(raw)["end_index"])
    return field_start + 4


# =============================================================================
# Reading: a friendly view over the offsets
# =============================================================================

@dataclass
class ModelInfo:
    lod: int
    arena_id: bytes
    model_name: bytes
    material_id: bytes
    textures: list = field(default_factory=list)   # [(channel, name_bytes)]


@dataclass
class AssetInfo:
    label: str              # "Hat", "Hat 2", ... (what the dropdown shows)
    folder: str
    number: int             # 1-based position inside its folder
    asset_id: bytes
    models: list            # [ModelInfo]
    list_index: int
    asset_index: int


def _label(folder: str, number: int) -> str:
    return folder if number == 1 else f"{folder} {number}"


def list_assets(raw: bytes) -> list:
    offs = compute_offsets(raw)
    out = []
    for li, al in enumerate(offs["asset_lists"]):
        for ai, a in enumerate(al["assets"]):
            models = []
            for m in a["models"]:
                models.append(ModelInfo(
                    lod=raw[m["lod"][0]],
                    arena_id=bytes(raw[slice(*m["arena_id"])]),
                    model_name=bytes(raw[slice(*m["model_name"])]),
                    material_id=bytes(raw[slice(*m["material_id"])]),
                    textures=[(bytes(raw[slice(*t["channel"])]).decode("ascii", errors="replace"),
                               bytes(raw[slice(*t["name"])])) for t in m["textures"]],
                ))
            out.append(AssetInfo(_label(al["folder_name"], ai + 1), al["folder_name"], ai + 1,
                                 bytes(raw[slice(*a["asset_id"])]), models, li, ai))
    return out


def find_asset(raw: bytes, label: str):
    return next((a for a in list_assets(raw) if a.label == label), None)


def describe(info: AssetInfo) -> str:
    tex = sum(len(m.textures) for m in info.models)
    return (f"AssetID {hex_id(info.asset_id)}  |  {len(info.models)} model(s)  |  "
            f"{tex} texture(s)")


# =============================================================================
# Writing: patch, validate, re-footer
# =============================================================================

def _apply(raw: bytes, patches: list, original_offsets: dict = None) -> bytes:
    """patches: [(start, end, new_bytes)] against `raw`. Applied right-to-left
    so a length change never shifts an offset a later patch still needs.
    The result is re-walked (must parse), given a fresh length footer, and
    checked against the maximum recipe size. Raises AssetEditError otherwise."""
    if not patches:
        return raw
    ordered = sorted(patches, key=lambda p: (p[0], p[1]), reverse=True)
    for (s1, e1, _), (s2, e2, _) in zip(ordered, ordered[1:]):
        if s1 < e2:      # ordered[1] starts before ordered[0]; overlap if it ends after ordered[0] starts
            raise AssetEditError("Internal error: overlapping edits.")
    buf = bytearray(raw)
    for s, e, new in ordered:
        buf[s:e] = bytes(new)
    try:
        offs = compute_offsets(bytes(buf))
        new_raw = fix_footer(bytes(buf), offs["end_index"])
        compute_offsets(new_raw)
    except Exception as e:
        raise AssetEditError(f"That change produced a recipe that can't be read back ({e}). Nothing was changed.")
    if len(new_raw) > MAX_RECIPE_LENGTH:
        raise AssetEditError(
            f"Recipe would be {len(new_raw)} bytes, over the {MAX_RECIPE_LENGTH}-byte limit. Nothing was changed.")
    return new_raw


def _total_assets(offs: dict) -> int:
    return sum(len(al["assets"]) for al in offs["asset_lists"])


def _locate(offs: dict, label: str):
    for al in offs["asset_lists"]:
        for ai, a in enumerate(al["assets"]):
            if _label(al["folder_name"], ai + 1) == label:
                return al, a, ai
    raise AssetEditError(f"'{label}' isn't in this recipe (try REFRESH).")


def remove_asset(raw: bytes, label: str) -> bytes:
    offs = compute_offsets(raw)
    if _total_assets(offs) <= 1:
        raise AssetEditError("Your skater must have at least 1 asset!")
    al, a, _ = _locate(offs, label)
    if len(al["assets"]) > 1:
        cp = al["count_pos"]
        patches = [(cp, cp + 1, bytes([raw[cp] - 1])), (*a["span"], b"")]
    else:      # last asset in its folder -> drop the whole folder entry
        cp = offs["asset_list_count_pos"]
        patches = [(cp, cp + 1, bytes([raw[cp] - 1])), (*al["span"], b"")]
    return _apply(raw, patches)


def fix_crash(raw: bytes):
    """Remove the low-LOD model (Models[1]) from every asset that has one."""
    offs = compute_offsets(raw)
    patches, changed = [], 0
    for al in offs["asset_lists"]:
        for a in al["assets"]:
            if len(a["models"]) > 1:
                patches.append((*a["model_count"], _u32(len(a["models"]) - 1)))
                patches.append((*a["models"][1]["span"], b""))
                changed += 1
    return _apply(raw, patches), changed


def apply_low_poly(raw: bytes, label: str = None):
    """Copy ArenaID + ModelName of Models[1] onto Models[0] (label=None -> every
    asset). MaterialID / textures on Models[0] are left alone."""
    offs = compute_offsets(raw)
    if label is None:
        targets = [a for al in offs["asset_lists"] for a in al["assets"]]
    else:
        targets = [_locate(offs, label)[1]]
    patches, changed = [], 0
    for a in targets:
        if len(a["models"]) > 1:
            m0, m1 = a["models"][0], a["models"][1]
            patches.append((m0["arena_id"][0], m0["model_name"][1],
                            bytes(raw[m1["arena_id"][0]:m1["model_name"][1]])))
            changed += 1
    return _apply(raw, patches), changed


# ---- saved assets (JSON) ----------------------------------------------------

def export_saved_asset(raw: bytes, label: str) -> dict:
    """JSON-ready dict for one asset. Stores the asset's exact bytes (so nothing
    is lost) plus human-readable fields for people who open the file."""
    offs = compute_offsets(raw)
    al, a, _ = _locate(offs, label)
    info = find_asset(raw, label)
    return {
        "format": SAVED_FORMAT,
        "version": SAVED_VERSION,
        "folder": al["folder_name"],
        "asset_id": info.asset_id.hex().upper(),
        "models": [{
            "lod": m.lod,
            "arena_id": m.arena_id.hex().upper(),
            "model_file": psg_name(m.model_name),
            "material_id": m.material_id.hex().upper(),
            "textures": [{"channel": c, "file": psg_name(n)} for c, n in m.textures],
        } for m in info.models],
        "data": bytes(raw[slice(*a["span"])]).hex().upper(),
    }


def _validate_saved(saved: dict) -> tuple:
    try:
        if saved.get("format") != SAVED_FORMAT:
            raise ValueError("not a TMenu saved-asset file")
        folder = str(saved["folder"])
        data = bytes.fromhex(saved["data"])
        folder.encode("ascii")
        # the blob must be exactly one well-formed asset: walk it as a mini recipe
        probe = _wrap_asset_as_recipe(folder, data)
        offs = compute_offsets(probe)
        al = offs["asset_lists"][0]
        if len(offs["asset_lists"]) != 1 or len(al["assets"]) != 1 or al["assets"][0]["span"][1] - al["assets"][0]["span"][0] != len(data):
            raise ValueError("asset data is the wrong size")
    except AssetEditError:
        raise
    except Exception as e:
        raise AssetEditError(f"Can't use that saved asset: {e}")
    return folder, data


def _wrap_asset_as_recipe(folder: str, asset_bytes: bytes) -> bytes:
    """Minimal throwaway recipe (name 'x', flag 0) holding one asset, used only
    to validate a saved blob with the same walker that reads real recipes."""
    name = b"x"
    head = b"\x00\x00\x00\x07" + _u32(len(name)) + name + _u32(0) + b"\x00\x00\x00\x0f\x00\x00\x00\x00"
    head += b"\x00\x00\x00\x01"                       # one asset list
    fb = folder.encode("ascii")
    return head + _u32(len(fb)) + fb + b"\x00\x00\x00\x01" + asset_bytes + b"\x00" * 8


def add_saved_asset(raw: bytes, saved: dict):
    """Add a saved asset: joins the existing folder if the recipe already has
    one, otherwise adds a new folder entry. Returns (new_raw, message)."""
    folder, blob = _validate_saved(saved)
    offs = compute_offsets(raw)
    new_id = blob[:8]
    for info in list_assets(raw):
        if info.asset_id == new_id:
            raise AssetEditError(f"This recipe already contains that asset ({info.label}).")
    existing = next((al for al in offs["asset_lists"] if al["folder_name"] == folder), None)
    if existing is not None:
        if raw[existing["count_pos"]] >= 255:
            raise AssetEditError(f"The {folder} folder can't hold any more assets.")
        cp = existing["count_pos"]
        patches = [(cp, cp + 1, bytes([raw[cp] + 1])), (existing["span"][1], existing["span"][1], blob)]
        msg = f"Added to existing {folder} folder."
    else:
        cp = offs["asset_list_count_pos"]
        if raw[cp] >= 255:
            raise AssetEditError("This recipe can't hold any more asset folders.")
        fb = folder.encode("ascii")
        header = _u32(len(fb)) + fb + b"\x00\x00\x00\x01"
        at = offs["asset_lists_end"]
        patches = [(cp, cp + 1, bytes([raw[cp] + 1])), (at, at, header + blob)]
        msg = f"Added new {folder} folder."
    return _apply(raw, patches), msg


# ---- per-asset RGB ------------------------------------------------------------

def _rgb_block_for(raw: bytes, offs: dict, asset_id: bytes):
    for i, b in enumerate(offs["rgb_blocks"]):
        if bytes(raw[slice(*b["asset_id"])]) == asset_id:
            return i, b
    return None, None


def get_asset_rgb(raw: bytes, label: str):
    offs = compute_offsets(raw)
    _, a, _ = _locate(offs, label)
    if not offs["has_tail"]:
        return None
    _, blk = _rgb_block_for(raw, offs, bytes(raw[slice(*a["asset_id"])]))
    if blk is None:
        return None
    return tuple(struct.unpack(">f", raw[slice(*blk[c])])[0] for c in ("r", "g", "b"))


def set_asset_rgb(raw: bytes, labels: list, rgb: tuple) -> bytes:
    """Recolor (or add a color block for) each labelled asset. Recolors in
    place when a block already exists; adds one otherwise; builds a tail if the
    recipe has none (and sets the texture-unlock flag, as every reference tool
    does whenever color data is written)."""
    offs = compute_offsets(raw)
    targets = []
    for lab in labels:
        _, a, _ = _locate(offs, lab)
        aid = bytes(raw[slice(*a["asset_id"])])
        mid = bytes(raw[slice(*a["models"][0]["material_id"])]) if a["models"] else bytes(8)
        if (aid, mid) not in targets:
            targets.append((aid, mid))
    if not targets:
        raise AssetEditError("Nothing to color.")

    has_tail = offs["has_tail"]
    patches, fresh = [], []
    for aid, mid in targets:
        i, blk = _rgb_block_for(raw, offs, aid) if has_tail else (None, None)
        if blk is not None:
            for chan, pair, val in zip("rgb", ("r2", "g2", "b2"), rgb):
                packed = struct.pack(">f", val)
                patches += [(*blk[chan], packed), (*blk[pair], packed)]
        else:
            fresh.append((aid, mid))

    if fresh:
        count = len(offs["rgb_blocks"]) if has_tail else 0
        if count + len(fresh) > 255:
            raise AssetEditError("A recipe can't hold more than 255 colors.")
        floats = b"".join(struct.pack(">f", v) for v in rgb)
        blocks = b"".join(bytes([0, 0, 0, count + k]) + floats + floats + a + m
                          for k, (a, m) in enumerate(fresh))
        total = _u32(count + len(fresh))
        if has_tail:
            end = offs["rgb_blocks_end"]
            patches.append((end, end, blocks))
            for s0, e0 in offs["rgb_count_spans"]:
                patches.append((s0, e0, total))
        else:
            # No tail yet: build one, exactly as the recipe editor does. It
            # replaces everything after the asset lists, so cut the buffer
            # there first - otherwise the zero padding of a live memory
            # buffer would be read as body-mod/vector space after the tail.
            tail = (TAIL_SIGNATURE + b"\x00" + total + total + blocks
                    + b"\x00\x00\x00\x05" + b"\x00\x00\x00\x00")
            raw = raw[:offs["asset_lists_end"]]
            patches = [(offs["asset_lists_end"], offs["asset_lists_end"], tail)]
            flag_pos = offs["flag"][0]
            if raw[flag_pos] != 2:
                patches.append((flag_pos, flag_pos + 1, b"\x02"))
            return _apply(raw, patches)

    # Colors only take effect when the texture folder is unlocked (flag 0x02).
    flag_pos = offs["flag"][0]
    if patches and raw[flag_pos] != 2:
        patches.append((flag_pos, flag_pos + 1, b"\x02"))
    return _apply(raw, patches)


# ---- misc ---------------------------------------------------------------------

def write_span(old_raw: bytes, new_raw: bytes) -> bytes:
    """Bytes to write to memory for `new_raw`: the new recipe, zero-extended over
    whatever the old recipe occupied so no stale tail bytes are left behind."""
    old_len = recipe_length(old_raw)
    return new_raw + b"\x00" * max(0, old_len - len(new_raw))
