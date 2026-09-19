"""
animations_data.py
===================
Data + AOB-scanning/caching backend for the ANIMATIONS tab (animations_tab.py).

data/Animation_AoBs.json ships every known trick name grouped by category
(Flip / Air / Grind / Misc) together with the exact byte pattern ("aob")
that identifies that trick's animation-select data in game memory. The
"address" field in that JSON is just a reference from whenever it was
originally captured - it is NEVER trusted directly. Every time the tool
needs an address it re-scans memory for the AOB pattern itself (see
scan_for_patterns below), because the real in-memory offset shifts between
game builds/runs.

Scanning
--------
scan_and_cache(state) walks 0x30300000-0x30400000 ONCE, checking every
chunk it reads against every trick's AOB pattern at the same time (rather
than doing one full-range pass per trick, which would be extremely slow
over the PS3MAPI socket). The same byte pattern almost always shows up
more than once in that range - per spec, only the FIRST (lowest-address)
occurrence of each trick's pattern is ever kept.

Caching
-------
Results are saved to cache/tricks/aob_cache.json (app_paths.export_dir) as
{trick_name: "AABBCCDD"} hex-address strings. On boot (state.on_attach,
wired up in animations_tab.py via gui_refresh.on_attach_refresh), if that
file doesn't exist a fresh scan is run and the file is (re)written; if it
already exists it's trusted as-is and loaded straight off disk - no
re-scan, no per-entry validation against the JSON. That's the whole
"self-fixing" story: delete the cache (by hand, or via the CACHE subtab's
CLEAR CACHE button) and the very next attach rebuilds it from scratch.
"""

import json
import os

from app_paths import data_dir, export_dir

TRICK_JSON_PATH = os.path.join(data_dir(), "Animation_AoBs.json")

CACHE_KIND = os.path.join("cache", "tricks")
CACHE_FILENAME = "aob_cache.json"

SCAN_START = 0x30300000
SCAN_END = 0x30400000
SCAN_CHUNK = 0x8000  # 32KB per memory read while scanning


def cache_file_path() -> str:
    return os.path.join(export_dir(CACHE_KIND), CACHE_FILENAME)


def _load_trick_json():
    with open(TRICK_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["Animations"]


def _aob_to_bytes(aob_str: str) -> bytes:
    return bytes.fromhex(aob_str.replace(" ", ""))


def _flatten(categories) -> dict:
    """categories: {category_name: [ {name, address, aob}, ... ]}. Returns
    {trick_name: aob_bytes} across every category, skipping any entry with
    no aob (there aren't any in the shipped file, but be defensive)."""
    flat = {}
    for entries in categories.values():
        for entry in entries:
            aob = entry.get("aob")
            if aob:
                flat[entry["name"]] = _aob_to_bytes(aob)
    return flat


_trick_json_cache = None


def load_tricks():
    """Raw {category: [entries]} dict from Animation_AoBs.json, loaded once
    and cached in-process (the file never changes at runtime)."""
    global _trick_json_cache
    if _trick_json_cache is None:
        _trick_json_cache = _load_trick_json()
    return _trick_json_cache


NULL_LABEL = "NULL"


def null_pattern(length: int) -> bytes:
    """Synthetic filler AOB - 0x10, 0x20, 0x30, 0x40, ... (wrapping back to
    0x00 past 0xF0) - a recognizable "blank this trick out" value a user
    can SET a trick to from the FLIP TRICKS 'Set To' dropdown.

    It is NEVER part of all_trick_patterns() / the boot scan - there's no
    real memory location to go looking for, it only ever gets WRITTEN, so
    including it in scan_and_cache would just waste a slot in every scan
    pass for something that can never be found (or worse, could coincidentally
    match real, unrelated memory since it's a short flat sequence). It IS
    included in flip_tricks()'s own list below though, so GET's "what's
    currently written here" comparison still recognizes it - a trick
    that's been nulled out is correctly reported as NULL instead of
    "custom/unrecognized" - all without touching the cache or redoing a
    scan.
    """
    return bytes(((i + 1) * 0x10) & 0xFF for i in range(length))


def flip_tricks(include_null=True):
    """[(name, aob_bytes), ...] for just the 'Flip' category, sorted by
    name, with the synthetic NULL entry (see null_pattern above) appended
    last unless include_null=False - what the ANIMATIONS > FLIP TRICKS
    dropdowns and GET's match-against pool are built from. Every real
    entry in this category is the same 16-byte pattern length, which is
    what makes a straight byte-for-byte swap between any two of them (or
    to/from NULL) safe."""
    entries = load_tricks().get("Flip", [])
    tricks = sorted(
        ((e["name"], _aob_to_bytes(e["aob"])) for e in entries if e.get("aob")),
        key=lambda t: t[0].lower(),
    )
    if include_null and tricks:
        tricks = tricks + [(NULL_LABEL, null_pattern(len(tricks[0][1])))]
    return tricks


def all_trick_patterns() -> dict:
    """{trick_name: aob_bytes} across every category - what a full boot
    scan searches memory for."""
    return _flatten(load_tricks())


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_for_patterns(state, patterns: dict, start=SCAN_START, end=SCAN_END, chunk_size=SCAN_CHUNK) -> dict:
    """One pass over [start, end) in `state`'s attached process, looking for
    every pattern in `patterns` ({name: bytes}) at once. Returns
    {name: address} for whatever it found - a pattern with no hit anywhere
    in range is simply left out of the result. Only the first (lowest-
    address) occurrence of each pattern is ever recorded, even though the
    same pattern almost always repeats further up in the range.

    Reads overlap chunk boundaries by (longest pattern - 1) bytes so a
    match straddling two chunks is never missed.
    """
    remaining = dict(patterns)
    found = {}
    if not remaining:
        return found

    max_len = max(len(p) for p in remaining.values())
    overlap = max(max_len - 1, 0)

    addr = start
    tail = b""
    while addr < end and remaining:
        length = min(chunk_size, end - addr)
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, length))
        buf = tail + raw
        buf_addr = addr - len(tail)

        for name in list(remaining.keys()):
            idx = buf.find(remaining[name])
            if idx != -1:
                found[name] = buf_addr + idx
                del remaining[name]

        tail = raw[-overlap:] if overlap else b""
        addr += length

    return found


def scan_and_cache(state) -> dict:
    """Full boot scan across every trick in Animation_AoBs.json, writes the
    result to cache/tricks/aob_cache.json, and returns it as
    {name: address_int}."""
    found = scan_for_patterns(state, all_trick_patterns())
    save_cache(found)
    return found


def load_cache() -> dict:
    """Raw load off disk, {name: address_int} - {} if the file doesn't
    exist or fails to parse."""
    path = cache_file_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {name: int(addr, 16) for name, addr in raw.items()}
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    raw = {name: f"{addr:08X}" for name, addr in cache.items()}
    with open(cache_file_path(), "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, sort_keys=True)


def clear_cache() -> None:
    """Deletes cache/tricks/aob_cache.json if it exists, and drops the
    in-process copy too. The very next ensure_cache() call (i.e. the next
    attach) rescans from scratch and recreates it - this is the tool's
    whole "self-fixing" mechanism, see module docstring."""
    path = cache_file_path()
    if os.path.isfile(path):
        os.remove(path)
    invalidate_runtime_cache()


_runtime_cache = None  # {name: address_int}, populated by ensure_cache()


def ensure_cache(state) -> dict:
    """The on-attach entry point (wired up in animations_tab.py via
    gui_refresh.on_attach_refresh): if cache/tricks/aob_cache.json doesn't
    exist yet, scans memory and creates it; otherwise just loads whatever's
    already there, untouched. Result is also kept in-process so repeated
    calls this session don't keep re-reading the file."""
    global _runtime_cache
    path = cache_file_path()
    if os.path.isfile(path):
        _runtime_cache = load_cache()
    else:
        _runtime_cache = scan_and_cache(state)
    return _runtime_cache


def current_cache() -> dict:
    """Whatever ensure_cache() last produced this session, without touching
    disk or memory - {} if it hasn't run yet (not attached this session)."""
    return _runtime_cache or {}


def invalidate_runtime_cache() -> None:
    """Drops the in-process cache copy (but not the file) so the next read
    of current_cache() comes up empty until the next ensure_cache() call.
    Used by the CACHE subtab's CLEAR CACHE button so it stops showing
    addresses the disk cache no longer backs, without needing a re-attach
    just to notice."""
    global _runtime_cache
    _runtime_cache = None
