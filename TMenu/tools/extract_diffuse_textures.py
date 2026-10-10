#!/usr/bin/env python3
"""
extract_diffuse_textures.py
===========================
Standalone tool (no TMenu imports, stdlib only) that reads the default Skate 3
recipes and writes every part's DIFFUSE texture id into three JSON files:

    marquee_diffuse.json      Marquee + MarqueeDLC  (DLC ids end in " (DLC)")
    livingworld_diffuse.json  LivingWorld
    vehicles_diffuse.json     Vehicle

Each file looks like:

    {
      "chris_cole": {
        "Hat": "000007D503E38818",
        "Hair": "000012AB03E38818"
      },
      "some_dlc_skater (DLC)": { ... }
    }

  - skater id : the recipe's file name without ".recipe" (always identical to
                the name inside the recipe header on the default recipes).
  - part      : the same label TMenu's asset editor uses - the asset-list
                folder name ("Hat", "Torso", "Rostral", ...), with a number
                appended for the 2nd, 3rd... asset in that folder ("Hat 2").
  - texture id: the 8-byte texture name as 16 uppercase hex digits - i.e. the
                on-disk "0x000007D503E38818.psg" with the "0x" and ".psg"
                removed, which is the form that gets injected / read.

Create-a-Character recipes (type 3 / "cas_db") are skipped for now.

How a recipe is read
--------------------
The walk follows TMenu's asset_core.compute_offsets (asset lists -> assets ->
models -> textures) with one extension. A model header ends in two counts:

    A  = number of texture "entries"          (first 4 bytes of the filler)
    B  = number of material groups in entry 1 (next 4 bytes)

and entries after the first start with their own 4-byte B. Each material group
is   8B material id + 4B texture count + textures.   TMenu's walker assumes
B == 1 (true for nearly every recipe), so it can't read ray_barbee.recipe
(B == 2) or zprop_saftybarrier.recipe (a LOD stub with B == 0). This walker
handles those; on every recipe TMenu can read, it returns identical results.

Every recipe is sanity-checked after the walk: it must end exactly at the
colour/graphics tail marker or exactly where the length footer says the file
ends. Anything that doesn't is reported, never silently trusted.

Usage
-----
    python extract_diffuse_textures.py                       # looks for ./Default Recipes or ./Default_Recipes.zip
    python extract_diffuse_textures.py "Default_Recipes.zip" -o out
    python extract_diffuse_textures.py "path/to/Default Recipes" -o out

SOURCE can be the "Default Recipes" folder or the zip of it.
"""

import argparse
import json
import os
import struct
import sys
import zipfile

TAIL_SIGNATURE = b"\x01\x00\x00\x00\x06"   # opens the gender/colours/graphics tail
DLC_SUFFIX = " (DLC)"
CAS_TYPE = 3                                # Create-a-Character: skipped for now

# recipe folder -> (output file key, skater-id suffix, expected recipe type byte)
ROUTES = {
    "Marquee":     ("marquee",     "",         0),
    "MarqueeDLC":  ("marquee",     DLC_SUFFIX, 0),
    "LivingWorld": ("livingworld", "",         1),
    "Vehicle":     ("vehicles",    "",         2),
}
OUTPUT_NAMES = {
    "marquee":     "marquee_diffuse.json",
    "livingworld": "livingworld_diffuse.json",
    "vehicles":    "vehicles_diffuse.json",
}


# =============================================================================
# Recipe reading
# =============================================================================

def _u32(data, i):
    return struct.unpack(">I", data[i:i + 4])[0]


def recipe_type(raw):
    """Type byte from the header (0 Marquee, 1 LivingWorld, 2 Vehicle, 3 CAS...)."""
    pos = 0x0B + raw[7]
    return raw[pos] if pos < len(raw) else None


def walk_assets(raw):
    """Walk the asset lists. Returns (parts, end_index) where parts is
    [(part_label, [(channel, texture_id_hex), ...])] in file order, with every
    texture of every model / material group of that part flattened together."""
    idx = 0x18 + raw[7]
    parts = []
    for _ in range(raw[idx - 1]):                     # asset lists (one per folder)
        start = idx
        name_len = raw[idx + 3]
        idx += 8 + name_len
        folder = raw[start + 4:start + 4 + name_len].decode("ascii", "replace")
        for number in range(1, raw[idx - 1] + 1):     # assets in this folder
            idx += 0x0C                               # 8B asset id + 4B model count
            textures = []
            for _ in range(raw[idx - 1]):             # models (LODs)
                idx += 1 + 8 + 8                      # lod, arena id, model name
                entries, groups = _u32(raw, idx), _u32(raw, idx + 4)
                idx += 8
                for entry in range(entries):
                    if entry:                         # later entries carry their own B
                        groups = _u32(raw, idx)
                        idx += 4
                    for _ in range(groups):           # material groups
                        idx += 8                      # material id
                        count = _u32(raw, idx)
                        idx += 4
                        for _ in range(count):        # textures
                            chan_len = _u32(raw, idx)
                            chan = raw[idx + 4:idx + 4 + chan_len].decode("ascii", "replace")
                            name = raw[idx + 4 + chan_len:idx + 12 + chan_len]
                            textures.append((chan, name.hex().upper()))
                            idx += 12 + chan_len
            label = folder if number == 1 else f"{folder} {number}"
            parts.append((label, textures))
    return parts, idx


def layout_ok(raw, end):
    """The walk must stop at the tail marker, or exactly at the file's footer."""
    if raw[end:end + 5] == TAIL_SIGNATURE:
        return True
    pad = 4 - end % 4 if end % 4 else 4
    return end + pad + 4 == len(raw)


# =============================================================================
# Reading the source (folder or zip)
# =============================================================================

def iter_recipes(source):
    """Yield (folder_name, skater_id, raw_bytes) for every .recipe in source."""
    if os.path.isdir(source):
        for dirpath, dirs, files in os.walk(source):
            dirs.sort()
            for fn in sorted(files):
                if fn.lower().endswith(".recipe"):
                    with open(os.path.join(dirpath, fn), "rb") as fh:
                        yield os.path.basename(dirpath), fn[:-7], fh.read()
    else:
        with zipfile.ZipFile(source) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir() or not info.filename.lower().endswith(".recipe"):
                    continue
                bits = info.filename.replace("\\", "/").split("/")
                yield (bits[-2] if len(bits) > 1 else ""), bits[-1][:-7], zf.read(info)


# =============================================================================
# Build the JSON data
# =============================================================================

def build(source):
    """Returns (results, report). results = {key: {skater_id: {part: id}}}."""
    gathered = {key: [] for key in OUTPUT_NAMES}     # key -> [(sort, skater_id, parts)]
    report = {"counts": {}, "skipped": [], "failed": [], "notes": []}

    for folder, stem, raw in iter_recipes(source):
        route = ROUTES.get(folder)
        if route is None:
            report["skipped"].append(f"{folder}/{stem}: folder not handled")
            continue
        key, suffix, expected_type = route
        label = f"{folder}/{stem}"
        try:
            kind = recipe_type(raw)
            if kind == CAS_TYPE or stem == "cas_db":
                report["skipped"].append(f"{label}: Create-a-Character, skipped for now")
                continue
            if kind != expected_type:
                report["notes"].append(f"{label}: header type {kind} != expected {expected_type} for {folder}")
            parts, end = walk_assets(raw)
        except (IndexError, struct.error, ValueError) as exc:
            report["failed"].append(f"{label}: {type(exc).__name__}: {exc}")
            continue
        if not layout_ok(raw, end):
            report["failed"].append(f"{label}: walk ended at {end} of {len(raw)} bytes "
                                    "(unrecognised layout) - not written")
            continue

        report["counts"][folder] = report["counts"].get(folder, 0) + 1
        out = {}
        for part, textures in parts:
            diffuse = list(dict.fromkeys(t for c, t in textures if c == "diffuse"))
            if not diffuse:
                report["notes"].append(f"{label}: {part} has no diffuse texture, left out")
                continue
            if len(diffuse) > 1:
                report["notes"].append(f"{label}: {part} has {len(diffuse)} different diffuse ids "
                                       f"{diffuse}; using the first ({diffuse[0]})")
            if part in out:
                report["notes"].append(f"{label}: duplicate part label '{part}', keeping the first")
                continue
            out[part] = diffuse[0]
        if not out:
            report["notes"].append(f"{label}: no diffuse textures at all, skater left out")
            continue
        gathered[key].append((bool(suffix), stem + suffix, out))

    results = {}
    for key, rows in gathered.items():
        rows.sort(key=lambda r: (r[0], r[1]))        # base skaters first, DLC last
        results[key] = {skater: parts for _dlc, skater, parts in rows}
    return results, report


def main():
    here = os.getcwd()
    default_src = next((p for p in (os.path.join(here, "Default Recipes"),
                                    os.path.join(here, "Default_Recipes.zip")) if os.path.exists(p)), None)
    ap = argparse.ArgumentParser(description="Extract diffuse texture ids from the default recipes.")
    ap.add_argument("source", nargs="?", default=default_src,
                    help='"Default Recipes" folder or the zip of it')
    ap.add_argument("-o", "--out", default="diffuse_json", help="output folder (default: diffuse_json)")
    args = ap.parse_args()
    if not args.source or not os.path.exists(args.source):
        ap.error("couldn't find the recipes - pass the folder or zip as SOURCE")

    results, report = build(args.source)

    os.makedirs(args.out, exist_ok=True)
    for key, name in OUTPUT_NAMES.items():
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(results[key], fh, indent=2)
            fh.write("\n")
        textures = sum(len(p) for p in results[key].values())
        print(f"wrote {path}: {len(results[key])} skaters, {textures} textures")

    print("\nrecipes read: " + ", ".join(f"{k} {v}" for k, v in sorted(report["counts"].items())))
    for title, lines in (("SKIPPED", report["skipped"]), ("NOTES", report["notes"]),
                         ("FAILED", report["failed"])):
        if lines:
            print(f"\n{title}:")
            for line in lines:
                print("  " + line)
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
