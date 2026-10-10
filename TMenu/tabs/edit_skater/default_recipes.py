"""
default_recipes.py
===================
The "Default Recipes" picker shared by EDIT SKATER > RECIPES (inject a whole
default recipe into a skater) and EDIT SKATER > ASSETS (pull a single asset
out of a default recipe and add it to a skater).

Default recipes ship in a "Default Recipes" folder next to the app (see
app_paths.default_recipes_dir()), laid out as one subfolder per category
with .recipe files inside:

    Default Recipes/
        LivingWorld/   male_adult_1.recipe, zprop_couch.recipe, ...
        Marquee/       chris_cole.recipe, ...
        MarqueeDLC/    ...
        Vehicle/       muscle_car_01.recipe, ...

Nothing here is hardcoded to those four names - the first dropdown lists
whatever subfolders are actually on disk, the second lists the .recipe
files inside the chosen one, and both are re-scanned each time the tab is
shown so recipes dropped in by hand appear without a restart.

This module only does the file side (scan / read) plus the two dropdowns;
what to do with the chosen recipe is up to whichever tab embeds it.
"""

import os

from ui.TsUI_qt import MetroDropdown
from core.app_paths import default_recipes_dir

RECIPE_EXT = ".recipe"


def list_folders() -> list:
    """Category folder names (sorted), or [] if the Default Recipes folder is missing."""
    root = default_recipes_dir()
    try:
        return sorted(
            (d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))),
            key=str.lower,
        )
    except OSError:
        return []


def list_recipes(folder: str) -> list:
    """Recipe names (file name minus .recipe, sorted) inside one category folder."""
    if not folder:
        return []
    path = os.path.join(default_recipes_dir(), folder)
    try:
        return sorted(
            (os.path.splitext(f)[0] for f in os.listdir(path)
             if f.lower().endswith(RECIPE_EXT) and os.path.isfile(os.path.join(path, f))),
            key=str.lower,
        )
    except OSError:
        return []


def recipe_path(folder: str, name: str) -> str:
    return os.path.join(default_recipes_dir(), folder, name + RECIPE_EXT)


def read_recipe_file(folder: str, name: str) -> bytes:
    with open(recipe_path(folder, name), "rb") as f:
        return f.read()


class DefaultRecipePicker:
    """Folder dropdown + recipe dropdown, added straight into `group`
    (a MetroGroupBox). Set `.on_recipe_changed` to a no-arg callable to be
    told whenever the selected recipe changes - including after a folder
    change or a re-scan - so an embedding tab can refresh anything that
    depends on it. (An attribute rather than a constructor argument so the
    callback can refer to widgets built after the picker.)"""

    def __init__(self, group, width):
        self.on_recipe_changed = None
        self.folder_dd = MetroDropdown(group, items=[], width=width)
        self.recipe_dd = MetroDropdown(group, items=[], width=width)
        group.add(self.folder_dd)
        group.add(self.recipe_dd)
        self.folder_dd.currentTextChanged.connect(self._folder_changed)
        self.recipe_dd.currentTextChanged.connect(self._recipe_changed)
        self.rescan()

    def rescan(self):
        """Re-reads the folders/recipes from disk, keeping the current
        selection where it still exists."""
        keep_folder = self.folder_dd.currentText()
        keep_recipe = self.recipe_dd.currentText()
        folders = list_folders()
        self.folder_dd.blockSignals(True)
        self.folder_dd.clear()
        self.folder_dd.addItems(folders)
        if keep_folder in folders:
            self.folder_dd.setCurrentText(keep_folder)
        self.folder_dd.blockSignals(False)
        self._fill_recipes(keep_recipe)

    def selected(self):
        """(folder, recipe name), or None if nothing is available to pick."""
        folder, name = self.folder_dd.currentText(), self.recipe_dd.currentText()
        return (folder, name) if folder and name else None

    def read_selected(self) -> bytes:
        sel = self.selected()
        if sel is None:
            raise FileNotFoundError("No default recipe selected - is the 'Default Recipes' folder next to the app?")
        return read_recipe_file(*sel)

    # -- internals ----------------------------------------------------------

    def _fill_recipes(self, keep=None):
        names = list_recipes(self.folder_dd.currentText())
        self.recipe_dd.blockSignals(True)
        self.recipe_dd.clear()
        self.recipe_dd.addItems(names)
        if keep in names:
            self.recipe_dd.setCurrentText(keep)
        self.recipe_dd.blockSignals(False)
        self._recipe_changed()

    def _folder_changed(self, _text=None):
        self._fill_recipes()

    def _recipe_changed(self, _text=None):
        if self.on_recipe_changed is not None:
            self.on_recipe_changed()
