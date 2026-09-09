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
)

SUBTAB_FONT = ("Segoe UI", 9)


def _populate_subtabs(subtabs, win, state):
    # registers every EDIT SKATER subtab and builds its content. shared by
    # the normal inline tab control (build(), below) and the VIEW ALL gallery popup
    # RGB and GRAPHICS are each two separate boxes shown together via add_multi
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

# small shared helpers


def _skater_dropdown(parent):
    return MetroDropdown(parent, items=[f"Skater {i}" for i in range(1, 6)], width=200)


def _skater_num(dropdown):
    return int(dropdown.currentText().split()[-1])


def _status_label(group):
    lbl = MetroLabel(group, text="")
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(True)
    return lbl

# RGB


def _build_rgb(colors_tab, swap_tab, win, state):
    # Colors and RGB Swapping each get their own frame via add_multi("RGB", 2)
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
    # points one part's color/swatch reference at another asset's swatch -
    # writes a 16-byte reference, not a float, separate from the Colors group
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

# Body Mods


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

# Style - Stance/Style/Posture/Trucks Tightness/Wheels Hardness + Gestures.
# Every field gets its own SET + GET pair - nothing is written until SET is
# clicked. Laid out as a 3-column grid with a GET ALL/SET ALL pair at the bottom.

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

    # Skater selector, top-left of the group
    skater_row = QWidget(group)
    skater_row.setStyleSheet("background: transparent;")
    skater_row_layout = QHBoxLayout(skater_row)
    skater_row_layout.setContentsMargins(0, 0, 0, 0)
    skater_dd = _skater_dropdown(skater_row)
    skater_row_layout.addWidget(skater_dd, alignment=Qt.AlignLeft)
    skater_row_layout.addStretch()
    group.add(skater_row)

    status_lbl = _status_label(group)  # added to the group last, shared by every field below

    # 3-column grid of fields
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
        # GET + SET side by side, as wide as the field above
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

    # GET ALL / SET ALL, spread left-to-right across the bottom
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

# Recipes - export a skater's full recipe blob to a .recipe file, or inject
# one back in. The memory read/write runs on a background thread and
# reports back through Qt signals, same as CONNECT/ATTACH.


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

    # background work (runs off the GUI thread)

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

    # UI callbacks

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

# Clothing Lock - re-writes a snapshot of one clothing item's bytes every
# 500ms so the game can't change it. Only one item can be locked at a time -
# switching skater/item or hitting the toggle again replaces or clears it.


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

    # lock state - only ever describes ONE active lock at a time
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
            # snapshots whatever is currently equipped, gets continuously re-written
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

    # changing skater or item while a lock is running turns it off instead
    # of silently locking the new one
    def on_selection_changed(_=None):
        if lock["active"]:
            lock["active"] = False
            lock_switch.setChecked(False)
            status_lbl.setText("Selection changed - lock disabled.")

    skater_dd.currentTextChanged.connect(on_selection_changed)
    item_dropdown.currentTextChanged.connect(on_selection_changed)

# Graphics - Graphics Spoofer, ported from the standalone "Graphics Spoofer
# PS3" tool. Not per-skater, just a User ID field + SPOOF button.

# Graphics Spoofer (left, not per-skater) plus a Graphic Editor (right) for
# the rotation/scale/x/y of each skater's 5 custom graphic slots - pick the
# skater and graphic, GET reads its 16 bytes into the four fields, SET writes them back.


def _build_graphics(spoofer_tab, editor_tab, state):
    # Graphics Spoofer and Graphic Editor each get their own frame via add_multi
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

# Extra - invisible parts (own dropdown + Apply) next to Gender (own
# dropdown + Apply), two independent controls. Gender is per-skater,
# invisible toggles ignore the skater dropdown.


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

    # Invisible parts column
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

    # Gender column
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

    # Other Clothing (Dr Pepper set) - per-skater, reuses the skater_dd dropdown at the top
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

    # Missing Texture - per-skater, forces an invalid material so a slot
    # renders as missing. Refuses to touch a slot with nothing equipped.
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

# Team Names - Team Name + Player 1-5, fixed-length zero-terminated ASCII
# strings, not per-skater.


def _encode_name(text: str, buffer_length: int) -> bytes:
    # encodes + zero-pads/terminates to fit buffer_length bytes exactly
    try:
        raw = text.encode("latin-1")  # covers plain ASCII plus « (0xAB) and » (0xBB)
    except UnicodeEncodeError:
        raise ValueError("Only ASCII characters (plus « and ») are supported here.")
    max_chars = buffer_length - 1  # last byte is always the zero terminator
    if len(raw) > max_chars:
        raise ValueError(f"Too long - max {max_chars} characters for this field.")
    return raw.ljust(buffer_length, b"\x00")


def _decode_name(raw: bytes) -> str:
    # decodes up to the first zero terminator (or the whole buffer if there isn't one)
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
