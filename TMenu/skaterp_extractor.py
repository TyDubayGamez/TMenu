"""
skaterp_extractor.py
====================
Small, dependency-free library that pulls the skater recipes out of a Skate 3
`skater.p` save file. It is the logic of the standalone "Skater.p Recipe
Extractor" tool with the GUI taken off, so TMenu can use it in the background.

How a recipe is located (identical to the standalone tool)
----------------------------------------------------------
  * Search the save for a known recipe name (b"cas_db", b"male_skater_1", ...).
  * The recipe starts START_PRE_OFFSET (8) bytes BEFORE the name, because every
    recipe begins with a 4-byte version + 4-byte name length before the name.
  * It ends END_OFFSET (37) bytes BEFORE the next b"average" marker.
  * Repeat hits of the same name are numbered: cas_db, cas_db(2), cas_db(3)...
  * After a hit, searching resumes just past that recipe's end.

On top of that, every extracted blob is checked: the name length field has to
match the name, and the recipe has to walk cleanly with asset_core's walker
(the same one the asset editor uses). Blobs that fail are kept in `all` with an
`error` message but never counted as skaters.

Which recipes are "the skaters"
-------------------------------
SKATER_RECIPE_NAMES (default: cas_db, the create-a-skater recipe name). They
are returned in file order, so the first is Skater 1, and capped at 5.
If a save ever stores them under another name, that one constant is all that
needs changing.

Typical use
-----------
    import skaterp_extractor as sx

    sp = sx.read_skater_p(r"C:\\...\\skater.p")      # raises SkaterPError on a bad file
    print(len(sp.skaters), "skater(s)")
    for i, r in enumerate(sp.skaters, 1):
        print(i, r.summary())                       # r.data is the .recipe bytes
    folder = sx.export_skaters(sp, "recipes/saves") # recipes/saves/<save>_<time>/skater_N.recipe

No Qt, no tkinter. Nothing here touches the PS3 - callers decide what to do
with the bytes.
"""

import datetime
import os
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Constants (from the standalone tool)
# --------------------------------------------------------------------------

START_PRE_OFFSET = 8
END_MARKER = b"average"
END_OFFSET = 37
MAX_SKATERS = 5

# Recipe names that count as a player's skater.
SKATER_RECIPE_NAMES = (b"cas_db",)

# Every name the standalone tool searched for (characters, props, cars).
CHARACTER_NAMES = [
    b'cas_db', b'big_black_lw', b'female_adult_1', b'female_adult_2', b'female_adult_3',
    b'female_business_3', b'female_granny_1', b'female_granny_2', b'female_skater_2',
    b'female_skater_1', b'female_skater_3', b'female_teenager_1', b'female_teenager_2',
    b'female_teenager_3', b'female_tourist_1', b'female_tourist_2', b'male_adult_1',
    b'female_tourist_3', b'male_adult_2', b'male_adult_3', b'female_business_1',
    b'male_ambassadors_big', b'male_ambassadors_medium', b'male_bum_1', b'male_bum_2',
    b'male_bum_3', b'male_business_1', b'female_business_2', b'male_business_2',
    b'male_business_3', b'male_jock_1', b'male_jock_3', b'male_jock_2',
    b'male_securityguard_1', b'male_securityguard_2', b'male_securityguard_3',
    b'male_skater_3', b'male_skater_2', b'male_teenager_1', b'male_teenager_2',
    b'male_teenager_3', b'male_tourist_1', b'male_tourist_2', b'male_tourist_3',
    b'male_worker_1', b'male_worker_2', b'male_worker_3', b'male_worker_4',
    b'male_worker_5', b'male_worker_6', b'male_skater_1', b'zprop_beachball',
    b'zprop_big_camera', b'zprop_bleachers', b'zprop_coffee_cup', b'zprop_couch',
    b'zprop_crumpled_paper', b'zprop_dumpster', b'zprop_garbage_can', b'zprop_ghettoBlaster',
    b'zprop_jumbo_sign', b'zprop_mediatower', b'zprop_paperwrapped_bottle',
    b'zprop_patio_chair', b'zprop_patio_table', b'zprop_patio_umbrella', b'zprop_pen',
    b'zprop_picnicTable_wood', b'zprop_podium', b'zprop_portapotty', b'zprop_poster_01',
    b'zprop_poster_02', b'zprop_rail', b'zprop_pop_can', b'zprop_waterbottle',
    b'zprop_saftybarrier', b'zprop_tent', b'z_pipeline_lw_ped', b'ai_skater_01',
    b'ai_skater_02', b'ai_skater_03', b'ai_skater_04', b'ai_skater_05', b'ai_skater_06',
    b'ai_skater_07', b'ai_skater_08', b'ai_skater_09', b'alex_chalmers', b'andrew_reynolds',
    b'andrew_reynolds_prop', b'attiba_jefferson', b'attiba_jefferson_prop', b'benny_fairfax',
    b'big_black', b'brayden_szafranski', b'chris_cole', b'chris_haslam', b'coach_frank',
    b'colin_mckay', b'cuz', b'cuz_can', b'danny_way', b'dan_drehobl', b'dan_drehobl_prop',
    b'darren_navarette', b'darren_navarette_prop', b'deerman_of_darkwoods', b'dem_bones',
    b'dem_bones_hom', b'dennis_busenitz', b'dennis_busenitz_prop', b'eric_koston',
    b'eric_koston_prop', b'giovanni_reda', b'giovanni_reda_prop', b'jake_brown',
    b'jason_dill', b'jerry_hsu', b'joey_brezinski', b'john_cardiel', b'john_cardiel_prop',
    b'john_rattray', b'josh_kalis', b'josh_kalis_prop', b'lizard_king', b'lizard_king_prop',
    b'lucas_puig', b'marc_johnson', b'mark_appleyard', b'michael_burnette',
    b'michael_burnette_prop', b'mike_carroll', b'mike_carroll_prop', b'mike_prop',
    b'mike_prop_nocrow', b'pat_duffy', b'pj_ladd', b'ray_barbee', b'rob_dyrdek',
    b'rob_dyrdek_prop', b'ryan_gallant', b'ryan_smith', b'sammy', b'sammy_prop', b'seb',
    b'seb_prop', b'security_03', b'shingo', b'shingo_prop', b'skate_ambassador',
    b'skate_ambassador_prop', b'terry_kennedy', b'tutorial_male', b'z_fresh_1',
    b'z_jason_dill', b'z_missing_model', b'z_legend', b'z_pen', b'z_pipeline_marquee',
    b'z_podium', b'z_railing_cap', b'z_tally_board', b'static_db_xbfdba595_000',
    b'fourdoor_sedan_01', b'hatchback_01', b'minivan_01', b'mongo_patrol_01',
    b'muscle_car_01', b'older_sedan_01', b'pickup_truck_01', b'pickup_truck_02',
    b'reda_car', b'sedan_4door_02', b'sedan_4door_03', b'sports_car_01', b'sports_car_02',
    b'sports_car_03', b'suv_01', b'suv_02', b'taxi_sedan_01', b'z_pipeline_lw_vih',
]


class SkaterPError(Exception):
    """The file couldn't be read, or contained nothing usable."""


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

@dataclass
class ExtractedRecipe:
    name: str                 # recipe name, e.g. "cas_db"
    occurrence: int           # 1 for the first hit of that name, 2 for the next...
    start: int                # byte offset of the recipe inside the save
    end: int                  # exclusive end offset inside the save
    data: bytes               # the recipe bytes, exactly as the standalone tool wrote them
    assets: int = 0           # number of assets found when walked (0 if invalid)
    error: str = ""           # why it was rejected ("" = parsed fine)

    @property
    def valid(self) -> bool:
        return not self.error

    @property
    def file_stem(self) -> str:
        """Standalone-tool style name: cas_db, cas_db(2), cas_db(3)..."""
        return self.name if self.occurrence == 1 else f"{self.name}({self.occurrence})"

    def summary(self) -> str:
        if not self.valid:
            return f"{self.file_stem}: unreadable ({self.error})"
        return f"{self.file_stem}  |  {self.assets} asset(s)  |  {len(self.data)} bytes"


@dataclass
class SkaterP:
    path: str
    size: int
    all: list = field(default_factory=list)        # every recipe found, valid or not
    skaters: list = field(default_factory=list)    # valid skater recipes, file order, max 5
    warnings: list = field(default_factory=list)   # human-readable notes from the scan
    skater_hits: int = 0                           # skater-named hits found (valid or not)

    @property
    def save_name(self) -> str:
        return save_label(self.path)


# --------------------------------------------------------------------------
# Core scan
# --------------------------------------------------------------------------

def _check(blob: bytes, name: bytes):
    """Return (asset_count, error). Header must carry the name's length, and the
    recipe must walk with asset_core's walker."""
    if len(blob) < 0x20:
        return 0, "too short"
    if int.from_bytes(blob[4:8], "big") != len(name) or blob[8:8 + len(name)] != name:
        return 0, "header doesn't match the name"
    try:
        import asset_core
        offs = asset_core.compute_offsets(blob)
        count = sum(len(al["assets"]) for al in offs["asset_lists"])
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"
    if count == 0:
        return 0, "no assets"
    return count, ""


def extract_recipes(raw: bytes, names=None, warnings=None) -> list:
    """Find every known recipe in `raw`. Same search rules as the standalone tool."""
    names = CHARACTER_NAMES if names is None else names
    warnings = [] if warnings is None else warnings
    found = []
    for name_bytes in names:
        name_str = name_bytes.decode("ascii", errors="replace")
        search_from = 0
        count = 0
        while True:
            idx = raw.find(name_bytes, search_from)
            if idx == -1:
                break
            count += 1
            label = name_str if count == 1 else f"{name_str}({count})"

            start = idx - START_PRE_OFFSET
            if start < 0:
                warnings.append(f"'{label}' found too early (0x{idx:X}); skipped.")
                search_from = idx + 1
                continue
            marker = raw.find(END_MARKER, idx)
            if marker == -1:
                warnings.append(f"End marker not found after '{label}'; skipped.")
                search_from = idx + 1
                continue
            end = marker - END_OFFSET
            if end <= start:
                warnings.append(f"Bad range for '{label}' (0x{start:X}..0x{end:X}); skipped.")
                search_from = idx + 1
                continue

            blob = bytes(raw[start:end])
            assets, error = _check(blob, name_bytes)
            found.append(ExtractedRecipe(name_str, count, start, end, blob, assets, error))
            search_from = end + 1
    return found


def read_skater_p(path: str, skater_names=None) -> SkaterP:
    """Read `path` and return a SkaterP. Raises SkaterPError if the file can't be
    read or holds no usable skater."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise SkaterPError(f"Couldn't read the file: {e}")
    return parse_skater_p(raw, path, skater_names)


def parse_skater_p(raw: bytes, path: str = "skater.p", skater_names=None) -> SkaterP:
    skater_names = SKATER_RECIPE_NAMES if skater_names is None else skater_names
    sp = SkaterP(path=path, size=len(raw))
    sp.all = extract_recipes(raw, warnings=sp.warnings)

    wanted = {n.decode("ascii") for n in skater_names}
    hits = [r for r in sp.all if r.name in wanted]
    hits.sort(key=lambda r: r.start)                 # file order == slot order
    sp.skater_hits = len(hits)
    sp.skaters = [r for r in hits if r.valid][:MAX_SKATERS]

    bad = [r for r in hits if not r.valid]
    for r in bad:
        sp.warnings.append(f"{r.file_stem} skipped: {r.error}")
    if not sp.skaters:
        if hits:
            raise SkaterPError(f"Found {len(hits)} skater entr{'y' if len(hits) == 1 else 'ies'} "
                               f"but none could be read ({bad[0].error}).")
        raise SkaterPError("No skaters found - this doesn't look like a Skate 3 skater.p.")
    return sp


# --------------------------------------------------------------------------
# Exporting
# --------------------------------------------------------------------------

_BAD = '<>:"/\\|?*'


def save_label(path: str) -> str:
    """Name to show / folder-name a save by. A save's skater.p normally sits in a
    folder named after the save, so that folder wins; anything else uses the
    file's own name."""
    p = os.path.abspath(path)
    stem = os.path.splitext(os.path.basename(p))[0]
    label = stem
    if stem.lower() == "skater":
        parent = os.path.basename(os.path.dirname(p))
        if parent:
            label = parent
    label = "".join("_" if c in _BAD or ord(c) < 32 else c for c in label).strip(" .")
    return label or "save"


def export_skaters(sp: SkaterP, saves_root: str, when: datetime.datetime = None) -> str:
    """Write every skater to <saves_root>/<save name>_<YYYY-MM-DD_HH-MM-SS>/skater_N.recipe
    and return that folder. Raises SkaterPError on a write failure."""
    when = when or datetime.datetime.now()
    folder = os.path.join(saves_root, f"{sp.save_name}_{when.strftime('%Y-%m-%d_%H-%M-%S')}")
    try:
        os.makedirs(folder, exist_ok=True)
        for i, r in enumerate(sp.skaters, 1):
            with open(os.path.join(folder, f"skater_{i}.recipe"), "wb") as f:
                f.write(r.data)
    except OSError as e:
        raise SkaterPError(f"Couldn't export the recipes: {e}")
    return folder
