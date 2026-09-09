import struct

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown, MetroTabControl
from color_picker import open_color_picker

SUBTAB_FONT = ("Segoe UI", 9)

PARK_RGB_BASE_ADDRESS = 0x40E81460
PARK_RGB_ROW_STRIDE = 128
PARK_RGB_COL_STRIDE = 16
PARK_RGB_ROWS = 8
PARK_RGB_COLS = 8


def park_rgb_address(row_index: int, col_index: int) -> int:
    # each grid cell is 16 bytes, each row is 128 bytes (8 cells wide)
    return PARK_RGB_BASE_ADDRESS + (row_index * PARK_RGB_ROW_STRIDE) + (col_index * PARK_RGB_COL_STRIDE)


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
