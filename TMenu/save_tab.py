"""
save_tab.py
============
Builds the top-level SAVE tab as two subtabs: DIFFICULTY (a single dropdown
that writes the same 00-03 code to both the saveable and active difficulty
addresses at once) and STATS (currently just Board Sales, a plain int field
built with field_widgets.py like ADJUSTABLES/VISUALS use for floats).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from TsUI_qt import MetroButton, MetroLabel, MetroGroupBox, MetroDropdown, MetroTabControl
from field_widgets import build_float_grid, simple_int_field
from save_data import (
    SAVEABLE_DIFFICULTY_ADDRESS, ACTIVE_DIFFICULTY_ADDRESS, DIFFICULTY_OPTIONS,
    BOARD_SALES_ADDRESS,
)

SUBTAB_FONT = ("Segoe UI", 9)

STATS_FIELDS = [
    simple_int_field("Board Sales", BOARD_SALES_ADDRESS),
]


def _build_difficulty(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Difficulty")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    dd = MetroDropdown(group, items=[label for _, label in DIFFICULTY_OPTIONS], width=200)
    group.add(dd)

    get_btn = MetroButton(group, text="GET", width=200)
    group.add(get_btn)

    set_btn = MetroButton(group, text="SET", width=200)
    group.add(set_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, ACTIVE_DIFFICULTY_ADDRESS, 1))
            code = raw[0]
            for i, (opt_code, _label) in enumerate(DIFFICULTY_OPTIONS):
                if opt_code == code:
                    dd.setCurrentIndex(i)
                    break
            status_lbl.setText("Difficulty loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        code = DIFFICULTY_OPTIONS[dd.currentIndex()][0]
        try:
            data = bytes([code])
            state.ps3.Process.Memory.Set(state.pid, SAVEABLE_DIFFICULTY_ADDRESS, data)
            state.ps3.Process.Memory.Set(state.pid, ACTIVE_DIFFICULTY_ADDRESS, data)
            status_lbl.setText(f"Difficulty set to {dd.currentText()}.")
        except Exception as e:
            status_lbl.setText(str(e))

    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("DIFFICULTY")
    _build_difficulty(subtabs.tab("DIFFICULTY"), state)

    subtabs.add("STATS")
    build_float_grid(subtabs.tab("STATS"), state, "Stats", STATS_FIELDS, columns=1, group_width=250)

    return subtabs
