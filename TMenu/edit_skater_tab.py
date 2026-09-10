"""
edit_skater_tab.py
===================
Builds the EDIT SKATER tab as its own row of subtabs (RGB / BODY MODS /
STYLE / RECIPES / CLOTHING LOCK / GRAPHICS / EXTRA / TEAM NAMES), using the
same MetroTabControl the top-level tabs use, just smaller - same underline
animation, same look, scaled down.

_populate_subtabs() is the single place that lists what belongs under EDIT
SKATER and builds it into the normal inline subtab control.

Subtabs are built once at startup and never torn down, so switching away to
another top-level tab and back doesn't reset anything - whichever subtab you
were last on is still selected. That state only lives in memory for this run
though; nothing is saved to disk, so a fresh launch always starts back on
the first subtab (RGB).

RGB / Body Mods / Style / Clothing Lock / Extra each get their own
"Skater 1-5" dropdown so you pick which of the 5 skater slots you're
editing. Gestures (in Style) and the Extra subtab's Invisible/Set Other
toggles are NOT per-skater in the underlying memory layout - there's only
one set of those addresses, and in-game they always apply to whichever
skater is currently being controlled/edited. That's just how the game
stores them, so there's nothing to expose to the user about it - the
dropdowns just work (or, for Extra, are simply not consulted for those
particular mods).

CLOTHING LOCK only ever keeps one clothing item locked at a time (across
all skaters) - picking a different item/skater or hitting the toggle again
replaces/clears whichever lock was previously active, it never stacks.
"""

import os
import struct
import threading

from PySide6.QtCore import QObject, Signal, Qt, QTimer
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QFileDialog, QApplication

from TsUI_qt import (
    MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown,
    MetroTabControl, MetroSwitch, show_subtab_gallery,
)
from color_picker import open_color_picker
from app_paths import export_dir, export_save_path
from dds_builder import build_dds, FIT_STRETCH, FIT_LETTERBOX, FIT_COVER

from edit_skater_data import (
    SKATERS, GESTURES, GESTURE_OPTIONS, RGB_PARTS, BODY_MOD_FIELDS,
    RECIPE_ADDRESSES, RECIPE_LENGTH,
    SWAP_TARGET_PARTS, RGB_SWAP_SOURCES, RGB_SWAP_SOURCE_OFFSETS,
    BOARD_SWATCH_BYTES, RGB_SWAP_SHOES_BYTE_BUMP,
    rgb_swap_target_address, rgb_swap_source_address,
    CLOTHING_LOCK_ITEMS, CLOTHING_LOCK_INTERVAL_MS, clothing_lock_address,
    INVISIBLE_TOGGLES, INVISIBLE_PANTS_ADDRESS, INVISIBLE_PANTS_ON_BYTES,
    EXTRA_MOD_NAMES, GENDER_OPTIONS,
    OTHER_CLOTHING_ITEMS, OTHER_CLOTHING_NAMES, other_clothing_address,
    MISSING_TEXTURE_ITEMS, MISSING_TEXTURE_UNEQUIPPED_FLAG,
    asset_data_address, missing_texture_bytes,
    NAME_FIELDS, NAME_ICON_SKATE, NAME_ICON_BOLT,
    GRAPHICS_SPOOFER_USER_ID_ADDRESS,
    GRAPHICS_SLOTS, GRAPHICS_FIELD_OFFSETS, graphics_slot_address,
    GRAPHIC_INJECTOR_SLOTS, GRAPHIC_INJECTOR_HEADERS_HEX,
    GRAPHIC_INJECTOR_DDS_HEADER_SKIP, GRAPHIC_INJECTOR_EXPECTED_DDS_SIZE,
    graphic_injector_pixel_address, graphic_injector_header_address,
)

SUBTAB_FONT = ("Segoe UI", 9)


def _populate_subtabs(subtabs, win, state):
    """
    Registers every EDIT SKATER subtab into `subtabs` and builds all their
    content. Shared by the normal inline tab control (build(), below) and
    the VIEW ALL gallery popup, so there's exactly one place that lists what
    belongs under EDIT SKATER - the gallery just calls this again against a
    second, freshly-made MetroTabControl rather than trying to share widgets
    with the inline one.
    """
    # RGB and GRAPHICS are each really two independently-bordered groups
    # shown together, not one group - add_multi keeps them paired in
    # compact mode but lets the gallery's masonry packing treat them as two
    # separate boxes instead of one bounding box sized to whichever is
    # taller (see MetroTabControl.add_multi's docstring). Registered in a
    # fixed left-to-right order so the tab bar (and the gallery) always
    # lists things the same way.
    colors_frame, rgb_swap_frame = subtabs.add_multi("RGB", 2)
    subtabs.add("BODY MODS")
    subtabs.add("STYLE")
    subtabs.add("RECIPES")
    subtabs.add("CLOTHING LOCK")
    graphics_spoofer_frame, graphic_editor_frame = subtabs.add_multi("GRAPHICS", 2)
    subtabs.add("EXTRA")
    subtabs.add("TEAM NAMES")

    _build_rgb(colors_frame, rgb_swap_frame, win, state)
    _build_body_mods(subtabs.tab("BODY MODS"), state)
    _build_style(subtabs.tab("STYLE"), state)
    _build_recipes(subtabs.tab("RECIPES"), state)
    _build_clothing_lock(subtabs.tab("CLOTHING LOCK"), win, state)
    _build_graphics(graphics_spoofer_frame, graphic_editor_frame, state)
    _build_extra(subtabs.tab("EXTRA"), state)
    _build_names(subtabs.tab("TEAM NAMES"), state)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    _populate_subtabs(subtabs, win, state)

    return subtabs


# -- small shared helpers ---------------------------------------------------

def _skater_dropdown(parent):
    return MetroDropdown(parent, items=[f"Skater {i}" for i in range(1, 6)], width=200)


def _skater_num(dropdown):
    return int(dropdown.currentText().split()[-1])


def _status_label(group):
    lbl = MetroLabel(group, text="")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    return lbl


def _unique_output_path(folder: str, base_name: str, ext: str) -> str:
    """<folder>/<base_name><ext>, auto-numbered to the next free name if
    that already exists - so converting the same source image twice never
    clobbers a previous DDS Outputs file."""
    candidate = os.path.join(folder, f"{base_name}{ext}")
    if not os.path.exists(candidate):
        return candidate
    n = 1
    while True:
        candidate = os.path.join(folder, f"{base_name} ({n}){ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _hex_str_to_bytes(hex_str: str) -> bytes:
    return bytes(int(b, 16) for b in hex_str.split())


# ---------------------------------------------------------------------------
# RGB
# ---------------------------------------------------------------------------

def _build_rgb(colors_tab, swap_tab, win, state):
    """
    Colors and RGB Swapping used to share one subtab frame via an internal
    row layout - now they're each given their own independent frame (see
    build()'s add_multi("RGB", 2) call) so flat mode's masonry packing can
    treat them as two separate boxes instead of one bounding box sized to
    whichever was taller. Compact mode still shows them side by side exactly
    as before - add_multi handles that automatically.
    """
    _build_colors(colors_tab, win, state)
    _build_rgb_swap(swap_tab, state)


def _build_colors(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Colors")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    part_dropdown = MetroDropdown(group, items=[p.capitalize() for p in RGB_PARTS], width=200)
    group.add(part_dropdown)

    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    boxes = {}
    for grid_row, channel in enumerate(("RED", "GREEN", "BLUE")):
        lbl = MetroLabel(grid_holder, text=channel)
        box = MetroTextBox(grid_holder, width=90, height=26)
        box.setPlaceholderText("float")
        grid.addWidget(lbl, grid_row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, grid_row, 1, alignment=Qt.AlignRight)
        boxes[channel] = box
    group.add(grid_holder)

    get_btn = MetroButton(group, text="GET RGB", width=200)
    group.add(get_btn)

    set_btn = MetroButton(group, text="SET RGB", width=200)
    group.add(set_btn)

    picker_btn = MetroButton(group, text="PICK COLOR", width=200)
    group.add(picker_btn)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    def on_picker_clicked():
        try:
            current = tuple(float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE"))
        except ValueError:
            current = (0.0, 0.0, 0.0)

        def apply_rgb(r, g, b):
            boxes["RED"].setText(f"{r:.4f}")
            boxes["GREEN"].setText(f"{g:.4f}")
            boxes["BLUE"].setText(f"{b:.4f}")

        part_name = part_dropdown.currentText()
        open_color_picker(win, current, apply_rgb, title=f"{part_name} Color Picker")

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        part = part_dropdown.currentText().lower()
        offsets = SKATERS[skater]["rgb_colors"][part]

        try:
            values = {c: float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE")}
        except ValueError:
            status_lbl.setText("RGB values must be numbers.")
            return

        try:
            pid = state.pid
            for channel, key in (("RED", "red"), ("GREEN", "green"), ("BLUE", "blue")):
                data = struct.pack(">f", values[channel])
                state.ps3.Process.Memory.Set(pid, offsets[key], data)
            status_lbl.setText(f"Skater {skater} {part.capitalize()} RGB set.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        part = part_dropdown.currentText().lower()
        offsets = SKATERS[skater]["rgb_colors"][part]

        try:
            pid = state.pid
            for channel, key in (("RED", "red"), ("GREEN", "green"), ("BLUE", "blue")):
                raw = bytes(state.ps3.Process.Memory.Get(pid, offsets[key], 4))
                value = struct.unpack(">f", raw)[0]
                boxes[channel].setText(f"{value:.4f}")
            status_lbl.setText(f"Skater {skater} {part.capitalize()} RGB loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    picker_btn.clicked.connect(on_picker_clicked)
    set_btn.clicked.connect(on_set_clicked)
    get_btn.clicked.connect(on_get_clicked)


def _build_rgb_swap(tab, state):
    """
    RGB Swapping - points one part's color/swatch reference at another
    asset's swatch, the same mechanic the RPCS3 tool uses (e.g. making the
    sock RGB become the black custom board's RGB). This writes a 16-byte
    reference, not a float, so it's a completely separate write from the
    Colors group even though they share the RGB subtab.
    """
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="RGB Swapping")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    target_dropdown = MetroDropdown(group, items=[p.capitalize() for p in SWAP_TARGET_PARTS], width=200)
    group.add(target_dropdown)

    source_dropdown = MetroDropdown(group, items=RGB_SWAP_SOURCES, width=200)
    group.add(source_dropdown)

    swap_btn = MetroButton(group, text="SWAP RGB", width=200)
    group.add(swap_btn)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    def on_swap_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        target_part = target_dropdown.currentText().lower()
        source = source_dropdown.currentText()
        target_addr = rgb_swap_target_address(skater, target_part)

        try:
            pid = state.pid
            if source == "Board":
                swatch = BOARD_SWATCH_BYTES
                state.ps3.Process.Memory.Set(pid, target_addr, swatch)
                status_lbl.setText(
                    f"Skater {skater} {target_dropdown.currentText()} swapped to Board. "
                    "Select the black custom board and exit Edit Skater to see it."
                )
                return

            source_addr = rgb_swap_source_address(skater, source)
            swatch = bytearray(state.ps3.Process.Memory.Get(pid, source_addr, 16))
            if source == "Current Shoes":
                swatch[15] = (swatch[15] + RGB_SWAP_SHOES_BYTE_BUMP) & 0xFF
            state.ps3.Process.Memory.Set(pid, target_addr, bytes(swatch))
            status_lbl.setText(f"Skater {skater} {target_dropdown.currentText()} swapped to {source}.")
        except Exception as e:
            status_lbl.setText(str(e))

    swap_btn.clicked.connect(on_swap_clicked)


# ---------------------------------------------------------------------------
# Body Mods
# ---------------------------------------------------------------------------

def _build_body_mods(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Body Mods")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    field_dropdown = MetroDropdown(group, items=BODY_MOD_FIELDS, width=200)
    group.add(field_dropdown)

    value_box = MetroTextBox(group, width=200, height=26)
    value_box.setPlaceholderText("value")
    group.add(value_box)

    set_btn = MetroButton(group, text="SET VALUE", width=200)
    group.add(set_btn)

    get_btn = MetroButton(group, text="GET VALUE", width=200)
    group.add(get_btn)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        field = field_dropdown.currentText()
        addr = SKATERS[skater]["body_mods"][field]

        try:
            value = float(value_box.text().strip())
        except ValueError:
            status_lbl.setText("Value must be a number.")
            return

        try:
            data = struct.pack(">f", value)
            state.ps3.Process.Memory.Set(state.pid, addr, data)
            status_lbl.setText(f"Skater {skater} {field} set.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        field = field_dropdown.currentText()
        addr = SKATERS[skater]["body_mods"][field]

        try:
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 4))
            value = struct.unpack(">f", raw)[0]
            value_box.setText(f"{value:.4f}")
            status_lbl.setText(f"Skater {skater} {field} loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    set_btn.clicked.connect(on_set_clicked)
    get_btn.clicked.connect(on_get_clicked)


# ---------------------------------------------------------------------------
# Style - Stance / Style / Posture / Trucks Tightness / Wheels Hardness +
# Gestures. Every field gets its own SET + GET pair instead of writing to
# memory the instant a dropdown changes - picking a value is "safe", nothing
# is actually poked until you click SET, and GET reads the field's current
# value back into its dropdown/box. SET and GET sit side by side under each
# field, together exactly as wide as the dropdown/value box above them.
# Laid out as a 3-column grid instead of one long vertical column so the tab
# doesn't turn into a scroll-fest, with the Skater 1-5 selector pinned to
# the top-left above the grid and a GET ALL / SET ALL pair spread across the
# bottom for touching every field on the tab at once.
# ---------------------------------------------------------------------------

_STYLE_BTN_HEIGHT = 30
_STYLE_FIELD_WIDTH = 180
_STYLE_BTN_SPACING = 8
_STYLE_HALF_BTN_WIDTH = (_STYLE_FIELD_WIDTH - _STYLE_BTN_SPACING) // 2


def _build_style(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Style")
    group.setFixedWidth(620)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    # -- Skater selector, top-left of the group ------------------------
    skater_row = QWidget(group)
    skater_row.setStyleSheet("background: transparent;")
    skater_row_layout = QHBoxLayout(skater_row)
    skater_row_layout.setContentsMargins(0, 0, 0, 0)
    skater_dd = _skater_dropdown(skater_row)
    skater_row_layout.addWidget(skater_dd, alignment=Qt.AlignLeft)
    skater_row_layout.addStretch()
    group.add(skater_row)

    status_lbl = _status_label(group)  # added to the group last, shared by every field below

    # -- 3-column grid of fields -----------------------------------------
    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(20)
    grid.setVerticalSpacing(16)
    group.add(grid_holder)

    all_fields = []  # (set_fn, get_fn) pairs, filled in as fields are registered below

    def make_cell(row, col, label_text):
        cell = QWidget(grid_holder)
        cell.setStyleSheet("background: transparent;")
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(4)
        cell_layout.addWidget(MetroLabel(cell, text=label_text))
        grid.addWidget(cell, row, col)
        return cell, cell_layout

    def make_set_get_row(cell, cell_layout):
        """A GET + SET pair side by side, together as wide as the field
        above. GET goes on the left since reading a value in feels like a
        starting point, SET on the right since committing a value feels
        like an "enter"/confirm action."""
        btn_row = QWidget(cell)
        btn_row.setStyleSheet("background: transparent;")
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(_STYLE_BTN_SPACING)
        get_btn = MetroButton(btn_row, text="GET", width=_STYLE_HALF_BTN_WIDTH, height=_STYLE_BTN_HEIGHT)
        set_btn = MetroButton(btn_row, text="SET", width=_STYLE_HALF_BTN_WIDTH, height=_STYLE_BTN_HEIGHT)
        btn_row_layout.addWidget(get_btn)
        btn_row_layout.addWidget(set_btn)
        cell_layout.addWidget(btn_row)
        return set_btn, get_btn

    def add_dropdown_setting(row, col, setting_name):
        options = SKATERS[1]["settings"][setting_name]["options"]  # same option list for every skater
        cell, cell_layout = make_cell(row, col, setting_name)

        dd = MetroDropdown(cell, items=[label for _, label in options], width=_STYLE_FIELD_WIDTH)
        cell_layout.addWidget(dd)
        set_btn, get_btn = make_set_get_row(cell, cell_layout)

        def do_set(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            skater = _skater_num(skater_dd)
            addr = SKATERS[skater]["settings"][setting_name]["address"]
            code = options[dd.currentIndex()][0]
            try:
                state.ps3.Process.Memory.Set(state.pid, addr, bytes([code]))
                if not quiet:
                    status_lbl.setText(f"Skater {skater} {setting_name} set to {dd.currentText()}.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        def do_get(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            skater = _skater_num(skater_dd)
            addr = SKATERS[skater]["settings"][setting_name]["address"]
            try:
                raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 1))
                code = raw[0]
                for i, (opt_code, _label) in enumerate(options):
                    if opt_code == code:
                        dd.setCurrentIndex(i)
                        break
                if not quiet:
                    status_lbl.setText(f"Skater {skater} {setting_name} loaded.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        set_btn.clicked.connect(lambda: do_set())
        get_btn.clicked.connect(lambda: do_get())
        all_fields.append((do_set, do_get))

    def add_float_setting(row, col, setting_name):
        cell, cell_layout = make_cell(row, col, setting_name)

        box = MetroTextBox(cell, width=_STYLE_FIELD_WIDTH, height=26)
        box.setPlaceholderText("float value")
        cell_layout.addWidget(box)
        set_btn, get_btn = make_set_get_row(cell, cell_layout)

        def do_set(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            skater = _skater_num(skater_dd)
            addr = SKATERS[skater]["settings"][setting_name]["address"]
            try:
                value = float(box.text().strip())
            except ValueError:
                if not quiet:
                    status_lbl.setText(f"{setting_name} must be a number.")
                return False
            try:
                data = struct.pack(">f", value)
                state.ps3.Process.Memory.Set(state.pid, addr, data)
                if not quiet:
                    status_lbl.setText(f"Skater {skater} {setting_name} set to {value}.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        def do_get(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            skater = _skater_num(skater_dd)
            addr = SKATERS[skater]["settings"][setting_name]["address"]
            try:
                raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 4))
                value = struct.unpack(">f", raw)[0]
                box.setText(f"{value:.4f}")
                if not quiet:
                    status_lbl.setText(f"Skater {skater} {setting_name} loaded.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        set_btn.clicked.connect(lambda: do_set())
        get_btn.clicked.connect(lambda: do_get())
        all_fields.append((do_set, do_get))

    def add_gesture_setting(row, col, gesture_name):
        addr = GESTURES[gesture_name]
        cell, cell_layout = make_cell(row, col, gesture_name)

        dd = MetroDropdown(cell, items=[label for _, label in GESTURE_OPTIONS], width=_STYLE_FIELD_WIDTH)
        cell_layout.addWidget(dd)
        set_btn, get_btn = make_set_get_row(cell, cell_layout)

        def do_set(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            code = GESTURE_OPTIONS[dd.currentIndex()][0]
            try:
                state.ps3.Process.Memory.Set(state.pid, addr, bytes([code]))
                if not quiet:
                    status_lbl.setText(f"{gesture_name} set to {dd.currentText()}.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        def do_get(quiet=False):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            try:
                raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 1))
                code = raw[0]
                for i, (opt_code, _label) in enumerate(GESTURE_OPTIONS):
                    if opt_code == code:
                        dd.setCurrentIndex(i)
                        break
                if not quiet:
                    status_lbl.setText(f"{gesture_name} loaded.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        set_btn.clicked.connect(lambda: do_set())
        get_btn.clicked.connect(lambda: do_get())
        all_fields.append((do_set, do_get))

    # Row 0: Stance / Style / Posture
    add_dropdown_setting(0, 0, "Stance")
    add_dropdown_setting(0, 1, "Style")
    add_dropdown_setting(0, 2, "Posture")

    # Row 1: Trucks Tightness / Wheels Hardness / Gesture 1
    add_float_setting(1, 0, "Trucks Tightness")
    add_float_setting(1, 1, "Wheels Hardness")
    add_gesture_setting(1, 2, "Gesture 1")

    # Row 2: Gesture 2 / Gesture 3 / Gesture 4
    add_gesture_setting(2, 0, "Gesture 2")
    add_gesture_setting(2, 1, "Gesture 3")
    add_gesture_setting(2, 2, "Gesture 4")

    # -- GET ALL / SET ALL, spread left-to-right across the bottom --------
    all_row = QWidget(group)
    all_row.setStyleSheet("background: transparent;")
    all_row_layout = QHBoxLayout(all_row)
    all_row_layout.setContentsMargins(0, 4, 0, 0)
    get_all_btn = MetroButton(all_row, text="GET ALL", width=180, height=_STYLE_BTN_HEIGHT + 4)
    set_all_btn = MetroButton(all_row, text="SET ALL", width=180, height=_STYLE_BTN_HEIGHT + 4)
    all_row_layout.addStretch()
    all_row_layout.addWidget(get_all_btn)
    all_row_layout.addStretch()
    all_row_layout.addWidget(set_all_btn)
    all_row_layout.addStretch()
    group.add(all_row)

    def on_get_all_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        ok = all(get_fn(quiet=True) for _set_fn, get_fn in all_fields)
        skater = _skater_num(skater_dd)
        status_lbl.setText(
            f"Skater {skater} all Style fields loaded." if ok else "Some fields failed to load."
        )

    def on_set_all_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        ok = all(set_fn(quiet=True) for set_fn, _get_fn in all_fields)
        skater = _skater_num(skater_dd)
        status_lbl.setText(
            f"Skater {skater} all Style fields set." if ok else "Some fields failed to set."
        )

    get_all_btn.clicked.connect(on_get_all_clicked)
    set_all_btn.clicked.connect(on_set_all_clicked)

    group.add(status_lbl)


# ---------------------------------------------------------------------------
# Recipes - export a skater's full recipe blob to a .recipe file (via a Save
# dialog defaulted into the recipes/ folder next to the app), or inject one
# back in. The socket read/write is the same kind of blocking I/O as
# CONNECT/ATTACH, so it runs on a background thread and reports back through
# Qt signals; the file dialogs themselves run on the GUI thread as usual.
# ---------------------------------------------------------------------------

class _RecipeSignals(QObject):
    export_result = Signal(bool, str)
    import_result = Signal(bool, str)


def _build_recipes(tab, state):
    signals = _RecipeSignals(tab)  # parented to the tab frame so it lives as long as the UI does

    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 30, 0, 0)

    group = MetroGroupBox(tab, title="Recipes")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    # IMPORT + EXPORT side by side, together the same width as the dropdown above
    btn_row = QWidget(group)
    btn_row.setStyleSheet("background: transparent;")
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 0, 0, 0)
    btn_row_layout.setSpacing(8)
    import_btn = MetroButton(btn_row, text="IMPORT", width=96)
    export_btn = MetroButton(btn_row, text="EXPORT", width=96)
    btn_row_layout.addWidget(import_btn)
    btn_row_layout.addWidget(export_btn)
    group.add(btn_row)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    # -- background work (runs off the GUI thread) ------------------------

    def do_export(path, skater):
        addr = RECIPE_ADDRESSES[skater]
        try:
            data = state.ps3.Process.Memory.Get(state.pid, addr, RECIPE_LENGTH)
            with open(path, "wb") as f:
                f.write(data)
            signals.export_result.emit(True, f"Skater {skater} recipe exported.")
        except Exception as e:
            signals.export_result.emit(False, str(e))

    def do_import(path, skater):
        addr = RECIPE_ADDRESSES[skater]
        try:
            with open(path, "rb") as f:
                data = f.read()
            state.ps3.Process.Memory.Set(state.pid, addr, data)
            signals.import_result.emit(True, f"Skater {skater} recipe imported.")
        except Exception as e:
            signals.import_result.emit(False, str(e))

    # -- UI callbacks -------------------------------------------------------

    def on_export_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        skater = _skater_num(skater_dd)
        path = export_save_path(
            export_btn, "recipes", f"skater_{skater}.recipe",
            "Export Recipe", "Recipe Files (*.recipe)",
        )
        if not path:
            return  # user cancelled the save dialog
        status_lbl.setText("Exporting...")
        export_btn.setEnabled(False)
        threading.Thread(target=do_export, args=(path, skater), daemon=True).start()

    def on_import_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        skater = _skater_num(skater_dd)
        path, _ = QFileDialog.getOpenFileName(
            import_btn, "Import Recipe", export_dir("recipes"), "Recipe Files (*.recipe)"
        )
        if not path:
            return  # user cancelled the open dialog
        status_lbl.setText("Importing...")
        import_btn.setEnabled(False)
        threading.Thread(target=do_import, args=(path, skater), daemon=True).start()

    def on_export_result(ok, msg):
        status_lbl.setText(msg)
        export_btn.setEnabled(True)

    def on_import_result(ok, msg):
        status_lbl.setText(msg)
        import_btn.setEnabled(True)

    export_btn.clicked.connect(on_export_clicked)
    import_btn.clicked.connect(on_import_clicked)
    signals.export_result.connect(on_export_result)
    signals.import_result.connect(on_import_result)


# ---------------------------------------------------------------------------
# Clothing Lock - RTM (real-time-memory) lock, re-writes a snapshot of one
# clothing item's bytes every 500ms so the game can't change it. Only one
# item (across all 5 skaters) can be locked at a time - picking a different
# skater/item, or hitting the toggle again, always replaces or clears
# whichever lock was previously running rather than stacking.
# ---------------------------------------------------------------------------

def _build_clothing_lock(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 30, 0, 0)

    group = MetroGroupBox(tab, title="Clothing Lock")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    item_dropdown = MetroDropdown(group, items=CLOTHING_LOCK_ITEMS, width=200)
    group.add(item_dropdown)

    switch_row = QWidget(group)
    switch_row.setStyleSheet("background: transparent;")
    switch_row_layout = QHBoxLayout(switch_row)
    switch_row_layout.setContentsMargins(0, 0, 0, 0)
    switch_row_layout.setSpacing(10)
    switch_label = MetroLabel(switch_row, text="Lock")
    lock_switch = MetroSwitch(switch_row)
    switch_row_layout.addStretch(1)
    switch_row_layout.addWidget(switch_label)
    switch_row_layout.addWidget(lock_switch)
    switch_row_layout.addStretch(1)
    group.add(switch_row)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    # -- lock state - only ever describes ONE active lock at a time --------
    lock = {"active": False, "skater": None, "item": None, "snapshot": None}

    timer = QTimer(win)
    timer.setInterval(CLOTHING_LOCK_INTERVAL_MS)

    def on_tick():
        if not lock["active"]:
            return
        if not state.is_ready():
            return
        addr = clothing_lock_address(lock["skater"], lock["item"])
        try:
            state.ps3.Process.Memory.Set(state.pid, addr, lock["snapshot"])
        except Exception as e:
            status_lbl.setText(str(e))

    timer.timeout.connect(on_tick)
    timer.start()

    def on_switch_toggled(checked):
        if not checked:
            lock["active"] = False
            status_lbl.setText("Clothing lock disabled.")
            return

        if not state.is_ready():
            lock_switch.setChecked(False)
            status_lbl.setText("Connect and attach first.")
            return

        skater = _skater_num(skater_dd)
        item = item_dropdown.currentText()
        addr = clothing_lock_address(skater, item)
        try:
            # Snapshot whatever is currently equipped - this is what gets
            # continuously re-written, same as the RPCS3 tool grabbing
            # prevHat/prevShirt/etc. the moment the checkbox is ticked.
            snapshot = state.ps3.Process.Memory.Get(state.pid, addr, 16)
        except Exception as e:
            lock_switch.setChecked(False)
            status_lbl.setText(str(e))
            return

        lock["active"] = True
        lock["skater"] = skater
        lock["item"] = item
        lock["snapshot"] = snapshot
        status_lbl.setText(f"Skater {skater} {item} locked.")

    lock_switch.toggled.connect(on_switch_toggled)

    # Changing skater or item while a lock is running just turns it off -
    # forces you to re-arm the switch (and grab a fresh snapshot) instead of
    # silently locking a different item than the one you were looking at.
    def on_selection_changed(_=None):
        if lock["active"]:
            lock["active"] = False
            lock_switch.setChecked(False)
            status_lbl.setText("Selection changed - lock disabled.")

    skater_dd.currentTextChanged.connect(on_selection_changed)
    item_dropdown.currentTextChanged.connect(on_selection_changed)


# ---------------------------------------------------------------------------
# Graphics - Graphics Spoofer, ported from the standalone "Graphics Spoofer
# PS3" tool. That tool did its own Connect/Attach (its Form1 had its own
# PS3MAPI instance) - here we just use the menu's existing connection, so
# all that's left is the User ID field + SPOOF button. Not per-skater, no
# skater dropdown.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Graphics - Graphics Spoofer (left) ported from the standalone "Graphics
# Spoofer PS3" tool, plus a Graphic Editor (right) for the rotation/scale/
# x/y of each skater's 5 custom graphic slots, from Skate_3_Skaters.CT.
# Spoofer isn't per-skater (that tool had its own single literal address);
# the editor is - pick the skater, then which of their 5 graphics, then
# GET to read its current 16 bytes into the four fields, or SET to write
# whatever's in the four fields back as one 16-byte block.
# ---------------------------------------------------------------------------

def _build_graphics(spoofer_tab, editor_tab, state):
    """Graphics Spoofer and Graphic Editor - see _build_rgb's docstring for
    why these are two independent frames (from add_multi) instead of one
    subtab frame with an internal row layout."""
    _build_graphics_spoofer(spoofer_tab, state)
    _build_graphic_editor(editor_tab, state)


def _build_graphics_spoofer(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Graphics Spoofer")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    lbl = MetroLabel(group, text="User ID")
    lbl.setAlignment(Qt.AlignCenter)
    group.add(lbl)

    user_id_box = MetroTextBox(group, width=200, height=26)
    group.add(user_id_box)

    spoof_btn = MetroButton(group, text="SPOOF", width=200)
    group.add(spoof_btn)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    def on_spoof_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            data = user_id_box.text().encode("ascii") + b"\x00"
        except UnicodeEncodeError:
            status_lbl.setText("Only ASCII characters are supported here.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, GRAPHICS_SPOOFER_USER_ID_ADDRESS, data)
            status_lbl.setText(f"User ID spoofed to \"{user_id_box.text()}\".")
        except Exception as e:
            status_lbl.setText(str(e))

    spoof_btn.clicked.connect(on_spoof_clicked)

    _build_graphic_injector(tab, layout, state)


# Crop Type dropdown options -> dds_builder fit modes. Order here is also
# the dropdown order; "Fit" is the default (matches the standalone
# converter tool's default).
_CROP_TYPES = {
    "Stretch": FIT_STRETCH,
    "Fit (letterbox)": FIT_LETTERBOX,
    "Fill (crop to cover)": FIT_COVER,
}

_INJECTOR_INPUT_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tga *.tif *.tiff *.webp)"


def _build_graphic_injector(tab, layout, state):
    """Custom Graphic Injector - pick one of the 4 custom graphic slots and
    a crop type, browse for a source image, and Inject converts it to the
    game's fixed 256x128 DXT5 DDS format and writes it straight into that
    slot's memory. The converted DDS is also dropped into a DDS Outputs
    folder next to the exe (auto-numbered if a file with that name already
    exists there) purely so the user has a copy - nothing has to be
    manually saved for the injection itself to work.

    The fixed header blob for the selected slot is always written right
    after the pixel data - that isn't a user-facing option (unlike the
    standalone test tool's checkbox), it's just always on.

    Shares the Graphics Spoofer group's own QVBoxLayout (passed in as
    `layout`) rather than installing a second layout on the same `tab`
    widget - a widget can only ever have one layout.
    """
    group = MetroGroupBox(tab, title="Custom Graphic Injector")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    slot_dropdown = MetroDropdown(group, items=GRAPHIC_INJECTOR_SLOTS, width=200)
    group.add(slot_dropdown)

    crop_dropdown = MetroDropdown(group, items=list(_CROP_TYPES.keys()), width=200)
    crop_dropdown.setCurrentIndex(1)  # default: Fit (letterbox)
    group.add(crop_dropdown)

    browse_btn = MetroButton(group, text="Browse...", width=200)
    group.add(browse_btn)

    path_lbl = MetroLabel(group, text="No file selected.")
    path_lbl.setAlignment(Qt.AlignCenter)
    path_lbl.setWordWrap(True)
    group.add(path_lbl)

    inject_btn = MetroButton(group, text="Inject", width=200)
    group.add(inject_btn)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    selected_path = {"value": ""}

    def on_browse_clicked():
        path, _ = QFileDialog.getOpenFileName(group, "Select Graphic", "", _INJECTOR_INPUT_FILTER)
        if path:
            selected_path["value"] = path
            path_lbl.setText(os.path.basename(path))

    def on_inject_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        src_path = selected_path["value"]
        if not src_path:
            status_lbl.setText("Choose an image first.")
            return

        slot_index = slot_dropdown.currentIndex()
        fit_mode = _CROP_TYPES[crop_dropdown.currentText()]

        try:
            status_lbl.setText("Converting...")
            QApplication.processEvents()
            dds_data = build_dds(src_path, fit_mode=fit_mode)
        except Exception as e:
            status_lbl.setText(f"Conversion failed: {e}")
            return

        if len(dds_data) != GRAPHIC_INJECTOR_EXPECTED_DDS_SIZE:
            status_lbl.setText(
                f"Unexpected DDS size ({len(dds_data)} bytes) - aborted."
            )
            return

        try:
            out_folder = export_dir("DDS Outputs")
            base_name = os.path.splitext(os.path.basename(src_path))[0]
            out_path = _unique_output_path(out_folder, base_name, ".dds")
            with open(out_path, "wb") as f:
                f.write(dds_data)
        except Exception as e:
            status_lbl.setText(f"Could not save to DDS Outputs: {e}")
            return

        pixel_data = dds_data[GRAPHIC_INJECTOR_DDS_HEADER_SKIP:]
        pixel_addr = graphic_injector_pixel_address(slot_index)
        header_addr = graphic_injector_header_address(slot_index)

        try:
            status_lbl.setText(f"Writing {len(pixel_data)} bytes to slot...")
            QApplication.processEvents()
            state.ps3.Process.Memory.Set(state.pid, pixel_addr, pixel_data)

            # Fixed header blob write is always on in the background - not
            # a user-facing toggle.
            header_hex = GRAPHIC_INJECTOR_HEADERS_HEX[slot_index]
            if header_hex:
                header_bytes = _hex_str_to_bytes(header_hex)
                state.ps3.Process.Memory.Set(state.pid, header_addr, header_bytes)
                status_lbl.setText(
                    f"Injected into {slot_dropdown.currentText()}. Saved as "
                    f"{os.path.basename(out_path)}."
                )
            else:
                status_lbl.setText(
                    f"Injected into {slot_dropdown.currentText()} (no header blob "
                    f"configured for this slot yet). Saved as {os.path.basename(out_path)}."
                )
        except Exception as e:
            status_lbl.setText(str(e))

    browse_btn.clicked.connect(on_browse_clicked)
    inject_btn.clicked.connect(on_inject_clicked)


def _build_graphic_editor(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Graphic Editor")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    graphic_dropdown = MetroDropdown(group, items=GRAPHICS_SLOTS, width=200)
    group.add(graphic_dropdown)

    # GET fills these four from memory; SET writes whatever's in them back.
    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    boxes = {}
    for grid_row, field in enumerate(("Rotation", "X", "Y", "Size")):
        lbl = MetroLabel(grid_holder, text=field)
        box = MetroTextBox(grid_holder, width=90, height=26)
        box.setPlaceholderText("float")
        grid.addWidget(lbl, grid_row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, grid_row, 1, alignment=Qt.AlignRight)
        boxes[field] = box
    group.add(grid_holder)

    btn_row = QWidget(group)
    btn_row.setStyleSheet("background: transparent;")
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 0, 0, 0)
    btn_row_layout.setSpacing(8)
    get_btn = MetroButton(btn_row, text="GET", width=96)
    set_btn = MetroButton(btn_row, text="SET", width=96)
    btn_row_layout.addWidget(get_btn)
    btn_row_layout.addWidget(set_btn)
    group.add(btn_row)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    # "Size" in the UI is the CT's "Scale" field - same float, friendlier name.
    _FIELD_TO_MEMORY_NAME = {"Rotation": "Rotation", "X": "X", "Y": "Y", "Size": "Scale"}

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        skater = _skater_num(skater_dd)
        slot = graphic_dropdown.currentText()
        addr = graphics_slot_address(skater, slot)
        try:
            data = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 16))
            for field, mem_name in _FIELD_TO_MEMORY_NAME.items():
                offset = GRAPHICS_FIELD_OFFSETS[mem_name]
                value = struct.unpack(">f", data[offset:offset + 4])[0]
                boxes[field].setText(f"{value:g}")
            status_lbl.setText(f"Skater {skater} {slot} loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        skater = _skater_num(skater_dd)
        slot = graphic_dropdown.currentText()
        addr = graphics_slot_address(skater, slot)

        try:
            values = {field: float(boxes[field].text().strip()) for field in _FIELD_TO_MEMORY_NAME}
        except ValueError:
            status_lbl.setText("Rotation/X/Y/Size must all be numbers.")
            return

        try:
            data = bytearray(16)
            for field, mem_name in _FIELD_TO_MEMORY_NAME.items():
                offset = GRAPHICS_FIELD_OFFSETS[mem_name]
                data[offset:offset + 4] = struct.pack(">f", values[field])
            state.ps3.Process.Memory.Set(state.pid, addr, bytes(data))
            status_lbl.setText(f"Skater {skater} {slot} set.")
        except Exception as e:
            status_lbl.setText(str(e))

    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)


# ---------------------------------------------------------------------------
# Extra - invisible parts (own dropdown + Apply) side by side with Gender
# (own dropdown + Apply). They used to share one dropdown/button (Gender
# swapped in as a value of the invisible-mod dropdown); now they're two
# independent controls that just happen to sit next to each other. Gender
# IS per-skater (unlike the invisible toggles), so it still reads the
# skater dropdown at the top; the invisible toggles ignore it.
# ---------------------------------------------------------------------------

def _build_extra(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 30, 0, 0)

    group = MetroGroupBox(tab, title="Extra")
    group.setFixedWidth(420)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    skater_dd = _skater_dropdown(group)
    group.add(skater_dd)

    # Row holding the two independent columns side by side.
    row = QWidget(group)
    row.setStyleSheet("background: transparent;")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(16)
    group.add(row)

    # -- Invisible parts column --------------------------------------
    invisible_col = QWidget(row)
    invisible_col.setStyleSheet("background: transparent;")
    invisible_layout = QVBoxLayout(invisible_col)
    invisible_layout.setContentsMargins(0, 0, 0, 0)
    invisible_layout.setSpacing(10)
    row_layout.addWidget(invisible_col)

    mod_dropdown = MetroDropdown(invisible_col, items=EXTRA_MOD_NAMES, width=190)
    invisible_layout.addWidget(mod_dropdown)

    invisible_apply_btn = MetroButton(invisible_col, text="APPLY", width=190)
    invisible_layout.addWidget(invisible_apply_btn)

    # -- Gender column --------------------------------------------------
    gender_col = QWidget(row)
    gender_col.setStyleSheet("background: transparent;")
    gender_layout = QVBoxLayout(gender_col)
    gender_layout.setContentsMargins(0, 0, 0, 0)
    gender_layout.setSpacing(10)
    row_layout.addWidget(gender_col)

    gender_dd = MetroDropdown(gender_col, items=[label for _, label in GENDER_OPTIONS], width=190)
    gender_layout.addWidget(gender_dd)

    gender_apply_btn = MetroButton(gender_col, text="APPLY", width=190)
    gender_layout.addWidget(gender_apply_btn)

    # -- Other Clothing (Dr Pepper set) ----------------------------------
    # Per-skater, but reuses the single skater_dd dropdown at the top of
    # this tab (same one Gender uses) rather than having its own - keeps
    # the tab down to one skater selector total.
    other_group = MetroGroupBox(tab, title="Other Clothing")
    other_group.setFixedWidth(420)
    layout.addWidget(other_group, alignment=Qt.AlignHCenter)

    other_row = QWidget(other_group)
    other_row.setStyleSheet("background: transparent;")
    other_row_layout = QHBoxLayout(other_row)
    other_row_layout.setContentsMargins(0, 0, 0, 0)
    other_row_layout.setSpacing(16)
    other_group.add(other_row)

    other_item_col = QWidget(other_row)
    other_item_col.setStyleSheet("background: transparent;")
    other_item_layout = QVBoxLayout(other_item_col)
    other_item_layout.setContentsMargins(0, 0, 0, 0)
    other_item_layout.setSpacing(10)
    other_row_layout.addWidget(other_item_col)

    other_item_dd = MetroDropdown(other_item_col, items=OTHER_CLOTHING_NAMES, width=190)
    other_item_layout.addWidget(other_item_dd)

    other_gender_col = QWidget(other_row)
    other_gender_col.setStyleSheet("background: transparent;")
    other_gender_layout = QVBoxLayout(other_gender_col)
    other_gender_layout.setContentsMargins(0, 0, 0, 0)
    other_gender_layout.setSpacing(10)
    other_row_layout.addWidget(other_gender_col)

    other_gender_dd = MetroDropdown(other_gender_col, items=[label for _, label in GENDER_OPTIONS], width=190)
    other_gender_layout.addWidget(other_gender_dd)

    other_apply_btn = MetroButton(other_group, text="APPLY", width=190)
    other_group.add(other_apply_btn)

    other_status_lbl = _status_label(other_group)
    other_group.add(other_status_lbl)

    # -- Missing Texture --------------------------------------------------
    # Per-skater, reuses the same shared skater_dd as Gender/Other Clothing.
    # Forces an invalid material on a slot so the game renders it as a
    # missing texture. Refuses to touch a slot the skater isn't wearing
    # anything in (checked by reading it first).
    mt_group = MetroGroupBox(tab, title="Missing Texture")
    mt_group.setFixedWidth(420)
    layout.addWidget(mt_group, alignment=Qt.AlignHCenter)

    mt_item_dd = MetroDropdown(mt_group, items=MISSING_TEXTURE_ITEMS, width=190)
    mt_group.add(mt_item_dd)

    mt_apply_btn = MetroButton(mt_group, text="APPLY", width=190)
    mt_group.add(mt_apply_btn)

    mt_status_lbl = _status_label(mt_group)
    mt_group.add(mt_status_lbl)

    def on_mt_apply_clicked():
        if not state.is_ready():
            mt_status_lbl.setText("Connect and attach first.")
            return

        try:
            skater = _skater_num(skater_dd)
            part = mt_item_dd.currentText()
            addr = asset_data_address(skater, part)
            pid = state.pid
            current = bytes(state.ps3.Process.Memory.Get(pid, addr, 16))
            if current == MISSING_TEXTURE_UNEQUIPPED_FLAG:
                mt_status_lbl.setText(f"Skater {skater} isn't wearing anything in {part} - nothing changed.")
                return
            state.ps3.Process.Memory.Set(pid, addr, missing_texture_bytes(current))
            mt_status_lbl.setText(f"Skater {skater} {part} set to missing texture.")
        except Exception as e:
            mt_status_lbl.setText(str(e))

    mt_apply_btn.clicked.connect(on_mt_apply_clicked)

    status_lbl = _status_label(group)
    group.add(status_lbl)

    def apply_simple_toggle(name):
        cfg = INVISIBLE_TOGGLES[name]
        pid = state.pid
        width = len(cfg["on"])
        current = bytes(state.ps3.Process.Memory.Get(pid, cfg["address"], width))
        if current == cfg["on"]:
            state.ps3.Process.Memory.Set(pid, cfg["address"], cfg["off"])
            status_lbl.setText(f"{name} disabled.")
        else:
            state.ps3.Process.Memory.Set(pid, cfg["address"], cfg["on"])
            status_lbl.setText(f"{name} enabled.")

    def apply_invisible_pants():
        pid = state.pid
        current = state.ps3.Process.Memory.Get(pid, INVISIBLE_PANTS_ADDRESS, 1)[0]
        if current != 0x00:
            state.ps3.Process.Memory.Set(pid, INVISIBLE_PANTS_ADDRESS, bytes([0]))
            status_lbl.setText("Invisible Pants disabled.")
        else:
            state.ps3.Process.Memory.Set(pid, INVISIBLE_PANTS_ADDRESS, INVISIBLE_PANTS_ON_BYTES)
            status_lbl.setText("Invisible Pants enabled.")

    def on_invisible_apply_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        mod_name = mod_dropdown.currentText()
        try:
            if mod_name in INVISIBLE_TOGGLES:
                apply_simple_toggle(mod_name)
            else:  # "Invisible Pants"
                apply_invisible_pants()
        except Exception as e:
            status_lbl.setText(str(e))

    def on_gender_apply_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        try:
            skater = _skater_num(skater_dd)
            code = GENDER_OPTIONS[gender_dd.currentIndex()][0]
            addr = SKATERS[skater]["settings"]["Gender"]["address"]
            state.ps3.Process.Memory.Set(state.pid, addr, bytes([code]))
            status_lbl.setText(f"Skater {skater} Gender set to {gender_dd.currentText()}.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_other_apply_clicked():
        if not state.is_ready():
            other_status_lbl.setText("Connect and attach first.")
            return

        try:
            skater = _skater_num(skater_dd)
            item_name = other_item_dd.currentText()
            gender_label = other_gender_dd.currentText()
            addr = other_clothing_address(skater, item_name)
            cfg = OTHER_CLOTHING_ITEMS[item_name]
            state.ps3.Process.Memory.Set(state.pid, addr, cfg[gender_label])
            other_status_lbl.setText(f"Skater {skater} {item_name} ({gender_label}) applied.")
        except Exception as e:
            other_status_lbl.setText(str(e))

    invisible_apply_btn.clicked.connect(on_invisible_apply_clicked)
    gender_apply_btn.clicked.connect(on_gender_apply_clicked)
    other_apply_btn.clicked.connect(on_other_apply_clicked)


# ---------------------------------------------------------------------------
# Team Names - Team Name + Player 1-5, fixed-length zero-terminated ASCII
# strings. Not per-skater (no Skater 1-5 dropdown here), these are separate
# roster-name buffers.
# ---------------------------------------------------------------------------

def _encode_name(text: str, buffer_length: int) -> bytes:
    """ASCII-ish encode + zero-pad/terminate to fit `buffer_length` bytes exactly."""
    try:
        raw = text.encode("latin-1")  # covers plain ASCII plus « (0xAB) and » (0xBB)
    except UnicodeEncodeError:
        raise ValueError("Only ASCII characters (plus « and ») are supported here.")
    max_chars = buffer_length - 1  # last byte is always the zero terminator
    if len(raw) > max_chars:
        raise ValueError(f"Too long - max {max_chars} characters for this field.")
    return raw.ljust(buffer_length, b"\x00")


def _decode_name(raw: bytes) -> str:
    """Reverse of _encode_name: given the full fixed-length buffer as read
    from memory, decode up to the first zero terminator (or the whole
    buffer if somehow there isn't one)."""
    end = raw.find(b"\x00")
    if end == -1:
        end = len(raw)
    return raw[:end].decode("latin-1")


def _build_names(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Team Names")
    group.setFixedWidth(420)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = _status_label(group)  # added last, shared by every row below

    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(10)
    group.add(grid_holder)

    def write_field(field_name, box):
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        cfg = NAME_FIELDS[field_name]
        try:
            data = _encode_name(box.text(), cfg["length"])
        except ValueError as e:
            status_lbl.setText(str(e))
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, cfg["address"], data)
            status_lbl.setText(f"{field_name} set to \"{box.text()}\".")
        except Exception as e:
            status_lbl.setText(str(e))

    def read_field(field_name, box):
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        cfg = NAME_FIELDS[field_name]
        try:
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, cfg["address"], cfg["length"]))
            box.setText(_decode_name(raw))
            status_lbl.setText(f"{field_name} loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    for row, (field_name, cfg) in enumerate(NAME_FIELDS.items()):
        lbl = MetroLabel(grid_holder, text=field_name)
        box = MetroTextBox(grid_holder, width=140, height=26)
        box.setMaxLength(cfg["length"] - 1)
        get_btn = MetroButton(grid_holder, text="GET", width=50, height=26)
        set_btn = MetroButton(grid_holder, text="SET", width=50, height=26)

        grid.addWidget(lbl, row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, row, 1)
        grid.addWidget(get_btn, row, 2)
        grid.addWidget(set_btn, row, 3)

        get_btn.clicked.connect(lambda _=False, f=field_name, b=box: read_field(f, b))
        set_btn.clicked.connect(lambda _=False, f=field_name, b=box: write_field(f, b))

    # -- special icon characters Skate 3's font renders as skate/bolt icons --
    icon_row = QWidget(group)
    icon_row.setStyleSheet("background: transparent;")
    icon_row_layout = QHBoxLayout(icon_row)
    icon_row_layout.setContentsMargins(0, 4, 0, 0)
    icon_row_layout.setSpacing(8)
    icon_row_layout.addWidget(MetroLabel(icon_row, text="Icons:"))

    def copy_icon(char, label):
        QApplication.clipboard().setText(char)
        status_lbl.setText(f"Copied {label} icon character to clipboard.")

    skate_btn = MetroButton(icon_row, text=f"Copy {NAME_ICON_SKATE} (Skate)", width=130, height=26)
    bolt_btn = MetroButton(icon_row, text=f"Copy {NAME_ICON_BOLT} (Bolt)", width=130, height=26)
    skate_btn.clicked.connect(lambda: copy_icon(NAME_ICON_SKATE, "skate"))
    bolt_btn.clicked.connect(lambda: copy_icon(NAME_ICON_BOLT, "bolt"))
    icon_row_layout.addWidget(skate_btn)
    icon_row_layout.addWidget(bolt_btn)
    group.add(icon_row)

    group.add(status_lbl)
