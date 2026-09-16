"""
park_tab.py
===========
Builds the top-level PARK tab as its own row of subtabs, using the same
MetroTabControl-as-subtabs pattern edit_skater_tab.py / misc_tab.py use.
Right now it holds a single RGB subtab, converted from the standalone
"S3 Park RGB" C# tool.

PARK_RGB_BASE_ADDRESS is an 8-digit PS3 address, same style as the rest of
this codebase - the original C# tool just wrote it as a decimal ulong
(1088951392) with a hex comment (40E81460); this is that same value,
written as the hex literal instead so it reads the same way every other
address in this tool does. Nothing was stripped/converted - it was already
8 digits.

Grid math (unchanged from the C# tool): each of the 8x8 grid's cells is 16
bytes (12 bytes of R/G/B float data + 4 bytes padding/unused), and each row
is 8 cells wide (128 bytes), so:

    address = PARK_RGB_BASE_ADDRESS + (row_index * 128) + (col_index * 16)

where row_index/col_index are 0-based (Row 1/Column 1 -> index 0).
"""

import struct

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown, MetroTabControl
from color_picker import open_color_picker
from gui_refresh import on_attach_refresh
from toggleables_data import VISUALS_TOGGLES
from toggleables_tab import register_synced_button, set_bold_everywhere

SUBTAB_FONT = ("Segoe UI", 9)

PARK_RGB_BASE_ADDRESS = 0x40E81460
PARK_RGB_ROW_STRIDE = 128
PARK_RGB_COL_STRIDE = 16
PARK_RGB_ROWS = 8
PARK_RGB_COLS = 8


def park_rgb_address(row_index: int, col_index: int) -> int:
    return PARK_RGB_BASE_ADDRESS + (row_index * PARK_RGB_ROW_STRIDE) + (col_index * PARK_RGB_COL_STRIDE)


# ---------------------------------------------------------------------------
# Editor Border - Park Editor's camera/collision border controls, converted
# from the standalone park_editor_tool.py. Two separate one-shot writes:
#
#   Disable Border        - do this once, BEFORE opening the park editor,
#                            while still sat in a normal park (not
#                            free-roam) - applying it from free-roam can
#                            crash the game when you later back out of the
#                            park editor.
#   Disable Camera Border - the actual park-editor toggle; click it fresh
#                            every time you open the park editor, not just
#                            once.
#
# No Black Screen is a third button here, but it's not a separate write of
# its own - it's the exact same TOGGLEABLES>VISUALS entry shown under the
# top-level VISUALS tab (toggleables_data.VISUALS_TOGGLES), reused as-is
# rather than duplicated. Reusing it (not copying its address/bytes) is what
# lets this button and the VISUALS one stay bold-in-sync with each other -
# see toggleables_tab.py's register_synced_button/set_bold_everywhere: on
# open, if either was somehow already on, both buttons go bold; toggling
# either one bolds/un-bolds both.
# ---------------------------------------------------------------------------
DISABLE_BORDER_ADDRESS = 0x018DE580
DISABLE_BORDER_PATTERN = bytes.fromhex("0E2442C8A8142C17")  # 8 bytes
DISABLE_BORDER_DATA = DISABLE_BORDER_PATTERN * 3  # 24 bytes total, pattern x3

DISABLE_CAMERA_BORDER_ADDRESS = 0x455FC9AA
DISABLE_CAMERA_BORDER_DATA = bytes([0x00])

# Overworld check - before every Disable Border write, the first 16 of its
# 24 bytes are read back and compared against these. Each entry is one
# normal (non-editable) map's own signature at that same address - Disable
# Border is only meant for custom parks, so if the 16 bytes currently there
# match ANY of these, the game is sat in one of these normal maps and the
# write is refused instead of going through.
NORMAL_MAP_SIGNATURES = {
    "Downtown": bytes.fromhex("4773016A41B2E05E4773016A41B2E05E"),
    "Industrial": bytes.fromhex("A8B1F47090679026A8B1F47090679026"),
    "University": bytes.fromhex("CB473E68A2EAFABACB473E68A2EAFABA"),
    "Skate.School": bytes.fromhex("2DC7AD2CB158A3D82DC7AD2CB158A3D8"),
    "Maloof Money Cup": bytes.fromhex("E35BB54793619839E35BB54793619839"),
    "Black Box": bytes.fromhex("03D1852F5F9C102B03D1852F5F9C102B"),
    "Maloof NYC": bytes.fromhex("FC482525912D5FB9FC482525912D5FB9"),
    "Danny's Hawaiian Dream": bytes.fromhex("AB0F2591D2EFCD44AB0F2591D2EFCD44"),
    "Sanitorium": bytes.fromhex("607AD0895698257D607AD0895698257D"),
    "Art Gallery": bytes.fromhex("FC94BB6AD3378A9CFC94BB6AD3378A9C"),
}


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("RGB")
    _build_rgb(subtabs.tab("RGB"), win, state)

    subtabs.add("EDITOR BORDER")
    _build_editor_border(subtabs.tab("EDITOR BORDER"), state)

    return subtabs


def _build_rgb(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Park RGB")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    row_lbl = MetroLabel(group, text="Row")
    row_lbl.setAlignment(Qt.AlignCenter)
    group.add(row_lbl)

    row_dd = MetroDropdown(group, items=[str(i) for i in range(1, PARK_RGB_ROWS + 1)], width=200)
    group.add(row_dd)

    col_lbl = MetroLabel(group, text="Col")
    col_lbl.setAlignment(Qt.AlignCenter)
    group.add(col_lbl)

    col_dd = MetroDropdown(group, items=[str(i) for i in range(1, PARK_RGB_COLS + 1)], width=200)
    group.add(col_dd)

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

    def on_picker_clicked():
        try:
            current = tuple(float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE"))
        except ValueError:
            current = (0.0, 0.0, 0.0)

        def apply_rgb(r, g, b):
            boxes["RED"].setText(f"{r:.4f}")
            boxes["GREEN"].setText(f"{g:.4f}")
            boxes["BLUE"].setText(f"{b:.4f}")

        open_color_picker(win, current, apply_rgb, title="Park RGB Color Picker")

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        row_index = int(row_dd.currentText()) - 1
        col_index = int(col_dd.currentText()) - 1

        try:
            addr = park_rgb_address(row_index, col_index)
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 12))
            values = struct.unpack(">fff", raw)
            for channel, value in zip(("RED", "GREEN", "BLUE"), values):
                boxes[channel].setText(f"{value:.4f}")
            status_lbl.setText(f"Loaded RGB from R{row_index + 1} C{col_index + 1}.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        row_index = int(row_dd.currentText()) - 1
        col_index = int(col_dd.currentText()) - 1

        try:
            values = {c: float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE")}
        except ValueError:
            status_lbl.setText("RGB values must be numbers.")
            return

        try:
            addr = park_rgb_address(row_index, col_index)
            buf = b"".join(struct.pack(">f", values[c]) for c in ("RED", "GREEN", "BLUE"))
            state.ps3.Process.Memory.Set(state.pid, addr, buf)
            status_lbl.setText(f"Applied RGB to R{row_index + 1} C{col_index + 1}.")
        except Exception as e:
            status_lbl.setText(str(e))

    picker_btn.clicked.connect(on_picker_clicked)
    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)


def _build_editor_border(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Editor Border")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    info_lbl = MetroLabel(
        group,
        text="Click Disable Camera Border every time you open the park editor. "
             "Only click Disable Border while out of the editor - if you're "
             "already in the editor, click it then reopen the editor.",
    )
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setWordWrap(True)
    group.add(info_lbl)

    disable_border_btn = MetroButton(group, text="Disable Border", width=240, height=32)
    group.add(disable_border_btn)

    disable_camera_border_btn = MetroButton(group, text="Disable Camera Border", width=240, height=32)
    group.add(disable_camera_border_btn)

    no_black_screen_btn = MetroButton(group, text="No Black Screen", width=240, height=32)
    group.add(no_black_screen_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_disable_border_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            current = bytes(state.ps3.Process.Memory.Get(state.pid, DISABLE_BORDER_ADDRESS, 16))
            for map_name, signature in NORMAL_MAP_SIGNATURES.items():
                if current == signature:
                    status_lbl.setText(f"In {map_name} (a normal map) - Disable Border refused.")
                    return
            state.ps3.Process.Memory.Set(state.pid, DISABLE_BORDER_ADDRESS, DISABLE_BORDER_DATA)
            status_lbl.setText("Border disabled. You can open the park editor now.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_disable_camera_border_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, DISABLE_CAMERA_BORDER_ADDRESS, DISABLE_CAMERA_BORDER_DATA)
            status_lbl.setText("Camera border disabled.")
        except Exception as e:
            status_lbl.setText(str(e))

    # Reuses VISUALS_TOGGLES's "No Black Screen" writes directly (same
    # address/bytes, not a copy) so this button and the VISUALS>TOGGLEABLES
    # one are always reading/writing the exact same state.
    no_black_screen_writes = VISUALS_TOGGLES["No Black Screen"]["writes"]

    def _no_black_screen_is_on():
        first = no_black_screen_writes[0]
        current = bytes(state.ps3.Process.Memory.Get(state.pid, first["address"], len(first["on"])))
        return current == first["on"]

    def on_no_black_screen_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            turning_on = not _no_black_screen_is_on()
            for w in no_black_screen_writes:
                data = w["on"] if turning_on else w["off"]
                state.ps3.Process.Memory.Set(state.pid, w["address"], data)
            set_bold_everywhere("No Black Screen", turning_on)
            status_lbl.setText(f"No Black Screen {'ON' if turning_on else 'OFF'}.")
        except Exception as e:
            status_lbl.setText(str(e))

    disable_border_btn.clicked.connect(on_disable_border_clicked)
    disable_camera_border_btn.clicked.connect(on_disable_camera_border_clicked)
    no_black_screen_btn.clicked.connect(on_no_black_screen_clicked)

    register_synced_button("No Black Screen", no_black_screen_btn)

    def _refresh_no_black_screen_bold():
        # Silent, same "leave it as-is on a bad read" rule as
        # toggleables_tab.py's own refresh - covers the case where this
        # button is what's on-screen first and VISUALS>TOGGLEABLES hasn't
        # been built/attached-through yet.
        try:
            set_bold_everywhere("No Black Screen", _no_black_screen_is_on())
        except Exception:
            pass

    on_attach_refresh(state, group, _refresh_no_black_screen_bold)
