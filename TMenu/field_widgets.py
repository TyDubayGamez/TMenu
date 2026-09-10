"""
field_widgets.py
=================
Shared "simple field" building blocks for tabs that are just a grid of
single global values (not per-skater, no skater selector) - ADJUSTABLES,
VISUALS's ADJUSTABLES/ENVIRONMENT/SCREEN subtabs, and SAVE's STATS subtab
all use this instead of each re-writing the same grid/GET/SET/placeholder
boilerplate edit_skater_tab.py's Style subtab already established.

Field spec dict (built by the factory functions below, or by hand for
anything more custom):
    {
        "label": "Transparency",   # shown above the box
        "kind": "float" or "int",  # controls parsing/formatting
        "default": 255.0,          # shown as a greyed-out placeholder only -
                                    # never pre-filled as real text, and never
                                    # used silently: SET requires the box to
                                    # actually have a value typed in unless
                                    # `default` is not None, in which case an
                                    # empty box falls back to it.
        "get": lambda state: <value>,          # reads memory, returns a number
        "set": lambda state, value: None,      # writes `value` to memory
    }

build_float_grid() lays a list of these out as a grid of label/box/GET+SET
cells (GET on the left, SET on the right - same convention as Style), with
an optional GET ALL / SET ALL row spread across the bottom when there's more
than one field.
"""

import math
import struct

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QGridLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox
from gui_refresh import on_attach_refresh
from color_picker import open_color_picker

FIELD_WIDTH = 180
BTN_HEIGHT = 30
BTN_SPACING = 8
HALF_BTN_WIDTH = (FIELD_WIDTH - BTN_SPACING) // 2
GRID_H_SPACING = 20
GRID_V_SPACING = 16


# ---------------------------------------------------------------------------
# Field factories - each returns a field spec dict per the format above.
# All memory addresses in this codebase are big-endian.
# ---------------------------------------------------------------------------

def simple_float_field(label, address, default=None):
    """One address, one float."""
    def get(state):
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, address, 4))
        return struct.unpack(">f", raw)[0]

    def set_(state, value):
        state.ps3.Process.Memory.Set(state.pid, address, struct.pack(">f", float(value)))

    return {"label": label, "kind": "float", "default": default, "get": get, "set": set_}


def multi_address_float_field(label, addresses, default=None):
    """Same float value written to every address in `addresses` at once.
    GET reads back from the first address."""
    def get(state):
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, addresses[0], 4))
        return struct.unpack(">f", raw)[0]

    def set_(state, value):
        data = struct.pack(">f", float(value))
        for addr in addresses:
            state.ps3.Process.Memory.Set(state.pid, addr, data)

    return {"label": label, "kind": "float", "default": default, "get": get, "set": set_}


def linked_offset_float_field(label, primary_address, secondary_address, offset, default=None):
    """Two addresses that move together but aren't equal - `secondary_address`
    is the real, user-facing value; `primary_address` always sits `offset`
    above it. GET/SET only ever touch the field's own displayed number
    (the secondary value); the primary address is kept in sync automatically
    behind the scenes."""
    def get(state):
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, secondary_address, 4))
        return struct.unpack(">f", raw)[0]

    def set_(state, value):
        value = float(value)
        state.ps3.Process.Memory.Set(state.pid, secondary_address, struct.pack(">f", value))
        state.ps3.Process.Memory.Set(state.pid, primary_address, struct.pack(">f", value + offset))

    return {"label": label, "kind": "float", "default": default, "get": get, "set": set_}


def simple_int_field(label, address, size=4, default=None):
    """One address, one big-endian signed int (4 bytes unless told otherwise)."""
    def get(state):
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, address, size))
        return int.from_bytes(raw, byteorder="big", signed=True)

    def set_(state, value):
        data = int(value).to_bytes(size, byteorder="big", signed=True)
        state.ps3.Process.Memory.Set(state.pid, address, data)

    return {"label": label, "kind": "int", "default": default, "get": get, "set": set_}


# ---------------------------------------------------------------------------
# Grid builder
# ---------------------------------------------------------------------------

def _format_value(kind, value):
    return str(int(round(value))) if kind == "int" else f"{value:.4f}"


def _format_placeholder(kind, default):
    if default is None:
        return "value"
    return str(int(default)) if kind == "int" else f"{default:g}"


def _is_default(kind, value, default):
    """True if `value` (as read from memory) matches `default` closely
    enough to still count as \"vanilla\" - floats read back from the game
    are never bit-exact to a hand-typed default, so this is a tolerance
    check, not ==. A field with no known default (default is None) is
    never considered \"default\" - there's nothing to compare against, so
    on-attach prefill always shows whatever's actually there."""
    if default is None:
        return False
    if kind == "int":
        return int(round(value)) == int(round(default))
    return math.isclose(value, default, rel_tol=1e-4, abs_tol=1e-4)


def build_float_grid(tab, state, title, fields, columns=2, group_width=None, parent_layout=None):
    """Builds one MetroGroupBox titled `title` into `tab`, laying `fields`
    (a list of field-spec dicts, see module docstring) out as a grid with
    `columns` columns. GET ALL / SET ALL is added at the bottom automatically
    whenever there's more than one field.

    `parent_layout`: pass an existing QVBoxLayout (already set up on `tab`)
    to add this group into it instead of creating a fresh layout on `tab` -
    needed when a subtab holds more than one group (e.g. VISUALS>WORLD's
    Fog Color group plus this Fog Density/Distance grid, both on the same
    tab widget - see visuals_tab.py). Leave as None for the normal
    one-group-per-tab case, which behaves exactly as before."""
    if parent_layout is None:
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.setContentsMargins(0, 20, 0, 0)
    else:
        layout = parent_layout

    if group_width is None:
        group_width = columns * FIELD_WIDTH + (columns - 1) * GRID_H_SPACING + 32

    group = MetroGroupBox(tab, title=title)
    group.setFixedWidth(group_width)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(GRID_H_SPACING)
    grid.setVerticalSpacing(GRID_V_SPACING)
    group.add(grid_holder)

    all_fields = []  # (do_get, do_set) pairs for GET ALL / SET ALL
    prefill_fields = []  # do_prefill_if_nondefault callables, for the on-attach refresh

    for i, field in enumerate(fields):
        row, col = divmod(i, columns)
        label = field["label"]
        kind = field.get("kind", "float")
        default = field.get("default")

        cell = QWidget(grid_holder)
        cell.setStyleSheet("background: transparent;")
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(4)
        cell_layout.addWidget(MetroLabel(cell, text=label))

        box = MetroTextBox(cell, width=FIELD_WIDTH, height=26)
        box.setPlaceholderText(_format_placeholder(kind, default))
        cell_layout.addWidget(box)

        btn_row = QWidget(cell)
        btn_row.setStyleSheet("background: transparent;")
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setSpacing(BTN_SPACING)
        get_btn = MetroButton(btn_row, text="GET", width=HALF_BTN_WIDTH, height=BTN_HEIGHT)
        set_btn = MetroButton(btn_row, text="SET", width=HALF_BTN_WIDTH, height=BTN_HEIGHT)
        btn_row_layout.addWidget(get_btn)
        btn_row_layout.addWidget(set_btn)
        cell_layout.addWidget(btn_row)

        grid.addWidget(cell, row, col)

        def do_get(quiet=False, field=field, box=box, label=label, kind=kind):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            try:
                value = field["get"](state)
                box.setText(_format_value(kind, value))
                if not quiet:
                    status_lbl.setText(f"{label} loaded.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        def do_set(quiet=False, field=field, box=box, label=label, kind=kind, default=default):
            if not state.is_ready():
                if not quiet:
                    status_lbl.setText("Connect and attach first.")
                return False
            text = box.text().strip()
            if not text:
                if default is None:
                    if not quiet:
                        status_lbl.setText(f"{label} needs a value.")
                    return False
                text = str(default)
            try:
                value = int(text) if kind == "int" else float(text)
            except ValueError:
                if not quiet:
                    status_lbl.setText(f"{label} must be a number.")
                return False
            try:
                field["set"](state, value)
                if not quiet:
                    status_lbl.setText(f"{label} set to {value}.")
                return True
            except Exception as e:
                if not quiet:
                    status_lbl.setText(str(e))
                return False

        def do_prefill_if_nondefault(field=field, box=box, kind=kind, default=default):
            """Quietly loads the field's current value into its box, but
            only if that value isn't (close enough to) the vanilla default -
            called on attach so a field someone's already changed shows its
            real value right away, while an untouched one just keeps
            showing the greyed-out default placeholder. Never touches
            status_lbl and never raises - see gui_refresh.on_attach_refresh,
            which already wraps this in its own try/except."""
            value = field["get"](state)
            if not _is_default(kind, value, default):
                box.setText(_format_value(kind, value))

        get_btn.clicked.connect(lambda _checked=False, g=do_get: g())
        set_btn.clicked.connect(lambda _checked=False, s=do_set: s())
        all_fields.append((do_get, do_set))
        prefill_fields.append(do_prefill_if_nondefault)

    if len(all_fields) > 1:
        all_row = QWidget(group)
        all_row.setStyleSheet("background: transparent;")
        all_row_layout = QHBoxLayout(all_row)
        all_row_layout.setContentsMargins(0, 4, 0, 0)
        get_all_btn = MetroButton(all_row, text="GET ALL", width=180, height=BTN_HEIGHT + 4)
        set_all_btn = MetroButton(all_row, text="SET ALL", width=180, height=BTN_HEIGHT + 4)
        all_row_layout.addStretch()
        all_row_layout.addWidget(get_all_btn)
        all_row_layout.addStretch()
        all_row_layout.addWidget(set_all_btn)
        all_row_layout.addStretch()
        group.add(all_row)

        def on_get_all():
            if not state.is_ready():
                status_lbl.setText("Connect and attach first.")
                return
            ok = all(g(quiet=True) for g, _s in all_fields)
            status_lbl.setText("All values loaded." if ok else "Some values failed to load.")

        def on_set_all():
            if not state.is_ready():
                status_lbl.setText("Connect and attach first.")
                return
            ok = all(s(quiet=True) for _g, s in all_fields)
            status_lbl.setText("All values set." if ok else "Some values failed to set.")

        get_all_btn.clicked.connect(on_get_all)
        set_all_btn.clicked.connect(on_set_all)

    group.add(status_lbl)

    def _refresh_on_attach():
        for prefill in prefill_fields:
            try:
                prefill()
            except Exception:
                pass

    on_attach_refresh(state, group, _refresh_on_attach)

    return group


# ---------------------------------------------------------------------------
# RGB color field - one 12-byte (3 adjacent big-endian floats, no padding)
# color value at a single fixed address. Same shape as PARK's per-cell RGB
# and EDIT SKATER's per-part clothing colors (color_picker.py), just without
# a row/col or skater-part selector - for global colors like VISUALS>WORLD's
# Fog Color or VISUALS>ADJUSTABLES' Skater Color (see visuals_data.py /
# visuals_tab.py).
# ---------------------------------------------------------------------------

_RGB_CHANNELS = ("RED", "GREEN", "BLUE")


def build_rgb_field_group(tab, win, state, title, address, default=None, parent_layout=None, group_width=250):
    """`default`, if given, is an (r, g, b) tuple - shown as each box's
    placeholder and used for the same "only prefill on attach if it isn't
    the vanilla default" rule build_float_grid's fields follow (see
    _is_default above) - a color counts as non-default if ANY of its three
    channels is meaningfully off from `default`."""
    if parent_layout is None:
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.setContentsMargins(0, 20, 0, 0)
    else:
        layout = parent_layout

    group = MetroGroupBox(tab, title=title)
    group.setFixedWidth(group_width)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    boxes = {}
    for row, channel in enumerate(_RGB_CHANNELS):
        lbl = MetroLabel(grid_holder, text=channel)
        box = MetroTextBox(grid_holder, width=90, height=26)
        box.setPlaceholderText("float" if default is None else f"{default[row]:g}")
        grid.addWidget(lbl, row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, row, 1, alignment=Qt.AlignRight)
        boxes[channel] = box
    group.add(grid_holder)

    picker_btn = MetroButton(group, text="PICK COLOR", width=200)
    group.add(picker_btn)

    get_btn = MetroButton(group, text="GET RGB", width=200)
    group.add(get_btn)

    set_btn = MetroButton(group, text="SET RGB", width=200)
    group.add(set_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def _read():
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, address, 12))
        return struct.unpack(">fff", raw)

    def on_picker_clicked():
        try:
            current = tuple(float(boxes[c].text().strip()) for c in _RGB_CHANNELS)
        except ValueError:
            current = default or (0.0, 0.0, 0.0)

        def apply_rgb(r, g, b):
            boxes["RED"].setText(f"{r:.4f}")
            boxes["GREEN"].setText(f"{g:.4f}")
            boxes["BLUE"].setText(f"{b:.4f}")

        open_color_picker(win, current, apply_rgb, title=f"{title} Color Picker")

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            values = _read()
            for channel, value in zip(_RGB_CHANNELS, values):
                boxes[channel].setText(f"{value:.4f}")
            status_lbl.setText(f"{title} loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        values = []
        try:
            for i, c in enumerate(_RGB_CHANNELS):
                text = boxes[c].text().strip()
                if not text:
                    if default is None:
                        status_lbl.setText(f"{title} needs all 3 values.")
                        return
                    text = str(default[i])
                values.append(float(text))
        except ValueError:
            status_lbl.setText(f"{title} values must be numbers.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, address, struct.pack(">fff", *values))
            status_lbl.setText(f"{title} set.")
        except Exception as e:
            status_lbl.setText(str(e))

    picker_btn.clicked.connect(on_picker_clicked)
    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)

    def _refresh_on_attach():
        values = _read()
        is_default = default is not None and all(
            math.isclose(v, d, rel_tol=1e-4, abs_tol=1e-4) for v, d in zip(values, default)
        )
        if not is_default:
            for channel, value in zip(_RGB_CHANNELS, values):
                boxes[channel].setText(f"{value:.4f}")

    on_attach_refresh(state, group, _refresh_on_attach)

    return group
