"""
asset_editor_tab.py
====================
The EDIT SKATER > ASSETS subtab. A live asset editor for a skater's recipe in
PS3 memory, laid out like the Xenia tool's "Asset Editor" page:

    EDITOR                      ASSET RGB EDITOR
      skater / refresh            red / green / blue
      asset to edit (or All)      GET / SET / PICK COLOR
      action + APPLY
      name + SAVE CURRENT ASSET  ASSET LIST (saved assets)
                                  saved-asset dropdown + DELETE

Actions (the EDITOR dropdown):
    Add Saved Asset   adds the asset picked in ASSET LIST to the skater
    Remove Asset      removes the selected asset (never the last one)
    Apply Low Poly    copies the low-LOD model onto the main model
    Fix Crash         drops the low-LOD model from every asset

Every edit reads the skater's recipe fresh from memory, splices the change in
with asset_core (which leaves every byte it doesn't understand untouched and
rebuilds the length footer), then writes it back and reads it to confirm.
Saved assets live in <exe folder>/assets/*.json.
"""

import json
import os
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown
from color_picker import open_color_picker
from app_paths import export_dir
from edit_skater_data import RECIPE_ADDRESSES, RECIPE_LENGTH

import asset_core as core

ACTIONS = ["Add Saved Asset", "Remove Asset", "Apply Low Poly", "Fix Crash"]
ALL = "All"
COL_W = 250          # width of each column of groups
FIELD_W = COL_W - 34  # dropdown / button width inside a group
BTN_H = 30

_BAD_NAME_CHARS = re.compile(r'[^A-Za-z0-9 _\-().]')


def _skater_num(dropdown):
    return int(dropdown.currentText().split()[-1])


def _status_label(group):
    lbl = MetroLabel(group, text="")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _saved_dir():
    return export_dir("assets")


def _saved_names():
    try:
        return sorted(os.path.splitext(f)[0] for f in os.listdir(_saved_dir())
                      if f.lower().endswith(".json"))
    except OSError:
        return []


def _transparent(widget):
    widget.setStyleSheet("background: transparent;")
    return widget


def build(tab, win, state):
    root = QHBoxLayout(tab)
    root.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    root.setContentsMargins(0, 18, 0, 0)
    root.setSpacing(16)
    root.addStretch(1)      # left spacer  }  together these centre the
                            #              }  two columns in the subtab

    # ------------------------------------------------------------------
    # Left column: EDITOR
    # ------------------------------------------------------------------
    editor = MetroGroupBox(tab, title="Editor")
    editor.setFixedWidth(COL_W)
    root.addWidget(editor, alignment=Qt.AlignTop)

    skater_dd = MetroDropdown(editor, items=[f"Skater {i}" for i in range(1, 6)], width=FIELD_W)
    editor.add(skater_dd)

    refresh_btn = MetroButton(editor, text="REFRESH CURRENT ASSETS", width=FIELD_W, height=BTN_H)
    editor.add(refresh_btn)

    asset_dd = MetroDropdown(editor, items=[], width=FIELD_W)
    editor.add(asset_dd)

    info_lbl = MetroLabel(editor, text="")
    info_lbl.setWordWrap(True)
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setStyleSheet(info_lbl.styleSheet() + " font-size: 8pt;")
    editor.add(info_lbl)

    action_dd = MetroDropdown(editor, items=ACTIONS, width=FIELD_W)
    editor.add(action_dd)

    apply_btn = MetroButton(editor, text="APPLY", width=FIELD_W, height=BTN_H)
    editor.add(apply_btn)

    name_box = MetroTextBox(editor, width=FIELD_W, height=26)
    name_box.setPlaceholderText("Asset name")
    editor.add(name_box)

    save_btn = MetroButton(editor, text="SAVE CURRENT ASSET", width=FIELD_W, height=BTN_H)
    editor.add(save_btn)

    # ------------------------------------------------------------------
    # Right column: ASSET RGB EDITOR + ASSET LIST
    # ------------------------------------------------------------------
    right = _transparent(QWidget(tab))
    right_layout = QVBoxLayout(right)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(14)
    root.addWidget(right, alignment=Qt.AlignTop)
    root.addStretch(1)      # right spacer

    rgb_group = MetroGroupBox(right, title="Asset RGB Editor")
    rgb_group.setFixedWidth(COL_W)
    right_layout.addWidget(rgb_group)

    grid_holder = _transparent(QWidget(rgb_group))
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    boxes = {}
    for row, channel in enumerate(("RED", "GREEN", "BLUE")):
        lbl = MetroLabel(grid_holder, text=channel)
        box = MetroTextBox(grid_holder, width=110, height=26)
        box.setPlaceholderText("float")
        grid.addWidget(lbl, row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, row, 1, alignment=Qt.AlignRight)
        boxes[channel] = box
    rgb_group.add(grid_holder)

    half = (FIELD_W - 8) // 2
    rgb_row = _transparent(QWidget(rgb_group))
    rgb_row_layout = QHBoxLayout(rgb_row)
    rgb_row_layout.setContentsMargins(0, 0, 0, 0)
    rgb_row_layout.setSpacing(8)
    get_btn = MetroButton(rgb_row, text="GET", width=half, height=BTN_H)
    set_btn = MetroButton(rgb_row, text="SET", width=half, height=BTN_H)
    rgb_row_layout.addWidget(get_btn)
    rgb_row_layout.addWidget(set_btn)
    rgb_group.add(rgb_row)

    pick_btn = MetroButton(rgb_group, text="PICK COLOR", width=FIELD_W, height=BTN_H)
    rgb_group.add(pick_btn)

    list_group = MetroGroupBox(right, title="Asset List")
    list_group.setFixedWidth(COL_W)
    right_layout.addWidget(list_group)

    saved_dd = MetroDropdown(list_group, items=[], width=FIELD_W)
    list_group.add(saved_dd)

    delete_btn = MetroButton(list_group, text="DELETE SAVED ASSET", width=FIELD_W, height=BTN_H)
    list_group.add(delete_btn)

    status_lbl = _status_label(right)
    status_lbl.setFixedWidth(COL_W)
    right_layout.addWidget(status_lbl)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def say(text):
        status_lbl.setText(text)

    def read_recipe(skater):
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, RECIPE_ADDRESSES[skater], RECIPE_LENGTH))
        if not core.looks_like_recipe(raw):
            raise core.AssetEditError(f"Skater {skater} doesn't have a readable recipe loaded yet.")
        core.compute_offsets(raw)   # raises if it can't be walked
        return raw

    def write_recipe(skater, old_raw, new_raw):
        payload = core.write_span(old_raw, new_raw)
        addr = RECIPE_ADDRESSES[skater]
        state.ps3.Process.Memory.Set(state.pid, addr, payload)
        back = bytes(state.ps3.Process.Memory.Get(state.pid, addr, len(payload)))
        if back != payload:
            raise core.AssetEditError("The game didn't take the write (memory read back different). "
                                      "Try REFRESH and apply again.")

    def ready():
        if not state.is_ready():
            say("Connect and attach first.")
            return False
        return True

    def fill_assets(raw, keep=None):
        labels = [a.label for a in core.list_assets(raw)]
        asset_dd.blockSignals(True)
        asset_dd.clear()
        asset_dd.addItems(labels + [ALL])
        if keep in labels + [ALL]:
            asset_dd.setCurrentText(keep)
        asset_dd.blockSignals(False)
        show_info(raw)

    def show_info(raw=None):
        label = asset_dd.currentText()
        if not label or label == ALL or raw is None:
            info_lbl.setText("Every asset on this skater" if label == ALL else "")
            return
        info = core.find_asset(raw, label)
        info_lbl.setText(core.describe(info) if info else "")

    current_raw = {"raw": None}

    def do_refresh(keep=None, announce=True):
        if not ready():
            return
        try:
            skater = _skater_num(skater_dd)
            raw = read_recipe(skater)
            current_raw["raw"] = raw
            fill_assets(raw, keep)
            if announce:
                say(f"Skater {skater}: {asset_dd.count() - 1} asset(s) loaded.")
        except Exception as e:
            say(str(e))

    def refill_saved(keep=None):
        names = _saved_names()
        saved_dd.clear()
        saved_dd.addItems(names)
        if keep in names:
            saved_dd.setCurrentText(keep)

    def load_saved(name):
        path = os.path.join(_saved_dir(), name + ".json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            raise core.AssetEditError(f"Couldn't read saved asset '{name}': {e}")

    # ------------------------------------------------------------------
    # callbacks
    # ------------------------------------------------------------------

    def on_apply():
        if not ready():
            return
        action = action_dd.currentText()
        target = asset_dd.currentText()
        skater = _skater_num(skater_dd)
        try:
            raw = read_recipe(skater)
            if action == "Add Saved Asset":
                name = saved_dd.currentText()
                if not name:
                    say("Pick a saved asset in ASSET LIST first.")
                    return
                new_raw, msg = core.add_saved_asset(raw, load_saved(name))
                result, keep = f"Skater {skater}: '{name}' - {msg}", target
            elif action == "Remove Asset":
                if not target or target == ALL:
                    say("Pick a single asset to remove (not All).")
                    return
                new_raw = core.remove_asset(raw, target)
                result, keep = f"Skater {skater}: removed {target}.", None
            elif action == "Apply Low Poly":
                new_raw, n = core.apply_low_poly(raw, None if target == ALL else target)
                if n == 0:
                    say("Nothing to change - no low-poly model on that asset.")
                    return
                result, keep = f"Skater {skater}: low poly applied to {n} asset(s).", target
            else:  # Fix Crash
                new_raw, n = core.fix_crash(raw)
                if n == 0:
                    say("Nothing to fix - no asset has a low-poly model.")
                    return
                result, keep = f"Skater {skater}: fix crash removed {n} low-poly model(s).", target
            write_recipe(skater, raw, new_raw)
            current_raw["raw"] = new_raw
            fill_assets(new_raw, keep)
            say(result)
        except core.AssetEditError as e:
            say(str(e))
        except Exception as e:
            say(str(e))

    def on_save():
        if not ready():
            return
        target = asset_dd.currentText()
        if not target or target == ALL:
            say("Pick a single asset to save (not All).")
            return
        name = _BAD_NAME_CHARS.sub("", name_box.text()).strip()
        if not name:
            say("Enter a name for the asset first.")
            return
        try:
            raw = read_recipe(_skater_num(skater_dd))
            data = core.export_saved_asset(raw, target)
            with open(os.path.join(_saved_dir(), name + ".json"), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            refill_saved(keep=name)
            say(f"Saved {target} as '{name}'.")
        except Exception as e:
            say(str(e))

    def on_delete():
        name = saved_dd.currentText()
        if not name:
            say("No saved asset selected.")
            return
        try:
            os.remove(os.path.join(_saved_dir(), name + ".json"))
            refill_saved()
            say(f"Deleted saved asset '{name}'.")
        except OSError as e:
            say(str(e))

    def parse_rgb():
        try:
            return tuple(float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE"))
        except ValueError:
            return None

    def on_get():
        if not ready():
            return
        target = asset_dd.currentText()
        if not target or target == ALL:
            say("Pick a single asset to read its color.")
            return
        try:
            rgb = core.get_asset_rgb(read_recipe(_skater_num(skater_dd)), target)
            if rgb is None:
                say(f"{target} has no color set.")
                return
            for c, v in zip(("RED", "GREEN", "BLUE"), rgb):
                boxes[c].setText(f"{v:.4f}")
            say(f"Read {target}'s color.")
        except Exception as e:
            say(str(e))

    def on_set():
        if not ready():
            return
        rgb = parse_rgb()
        if rgb is None:
            say("Enter numbers in all three color boxes.")
            return
        target = asset_dd.currentText()
        if not target:
            say("Refresh to load this skater's assets first.")
            return
        skater = _skater_num(skater_dd)
        try:
            raw = read_recipe(skater)
            labels = [a.label for a in core.list_assets(raw)] if target == ALL else [target]
            new_raw = core.set_asset_rgb(raw, labels, rgb)
            write_recipe(skater, raw, new_raw)
            current_raw["raw"] = new_raw
            fill_assets(new_raw, target)
            say(f"Color set on {len(labels)} asset(s).")
        except Exception as e:
            say(str(e))

    def on_pick():
        current = parse_rgb() or (0.0, 0.0, 0.0)

        def apply_rgb(r, g, b):
            for c, v in zip(("RED", "GREEN", "BLUE"), (r, g, b)):
                boxes[c].setText(f"{v:.4f}")

        open_color_picker(win, current, apply_rgb, title="Asset Color Picker")

    def on_asset_changed(_text=None):
        show_info(current_raw["raw"])

    refresh_btn.clicked.connect(lambda: do_refresh())
    apply_btn.clicked.connect(on_apply)
    save_btn.clicked.connect(on_save)
    delete_btn.clicked.connect(on_delete)
    get_btn.clicked.connect(on_get)
    set_btn.clicked.connect(on_set)
    pick_btn.clicked.connect(on_pick)
    asset_dd.currentTextChanged.connect(on_asset_changed)
    skater_dd.currentTextChanged.connect(lambda _t: do_refresh(announce=False) if state.is_ready() else None)

    refill_saved()

    # re-list saved assets whenever the tab is shown, in case files were added by hand
    orig_show = tab.showEvent

    def show_event(ev):
        refill_saved(keep=saved_dd.currentText())
        orig_show(ev)

    tab.showEvent = show_event

    return {"refresh": do_refresh}
