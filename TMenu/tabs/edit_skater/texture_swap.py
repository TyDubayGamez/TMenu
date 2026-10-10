"""
texture_swap.py
===============
Data + logic behind the TEXTURE SWAPPER group on EDIT SKATER > ASSETS.

The preset textures come from three JSON files in the app's data folder
(made by tools/extract_diffuse_textures.py from the default recipes):

    marquee_diffuse.json      {skater: {part: textureId}}   pros / AI skaters
    livingworld_diffuse.json  {skater: {part: textureId}}   peds and props
    vehicles_diffuse.json     {skater: {part: textureId}}   cars

Living World and Vehicle recipes share textures, so they're offered together
as one category. Which category is offered is decided by the TYPE of the
recipe currently in memory:

    Marquee             -> "Marquee"
    Living World / Vehicle -> "Vehicles and Living World"
    Create-a-Character  -> nothing (not supported yet)
"""

import json
import os

from core.app_paths import data_dir
from tabs.edit_skater.recipe_type import RecipeType, read_recipe_type

CAT_MARQUEE = "Marquee"
CAT_WORLD = "Vehicles and Living World"

# category -> JSON files that feed it (in the order they're listed)
_SOURCES = {
    CAT_MARQUEE: ("marquee_diffuse.json",),
    CAT_WORLD: ("livingworld_diffuse.json", "vehicles_diffuse.json"),
}

_cache = {}


def category_for_recipe(raw):
    """Category offered for the recipe bytes, or None (CAS / unknown type)."""
    kind = read_recipe_type(raw) if raw else None
    if kind == RecipeType.MARQUEE:
        return CAT_MARQUEE
    if kind in (RecipeType.LIVINGWORLD, RecipeType.VEHICLE):
        return CAT_WORLD
    return None


def _load_json(name):
    try:
        with open(os.path.join(data_dir(), name), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_category(category, reload=False):
    """{skater: {part: textureId}} for a category (merged, cached)."""
    if reload or category not in _cache:
        merged = {}
        for name in _SOURCES.get(category, ()):
            for skater, parts in _load_json(name).items():
                if isinstance(parts, dict):
                    merged.setdefault(skater, {}).update(parts)
        _cache[category] = merged
    return _cache[category]


def skaters(category):
    return list(load_category(category).keys())


def parts(category, skater):
    """[(part label, textureId)] for one skater of a category."""
    return list(load_category(category).get(skater, {}).items())
