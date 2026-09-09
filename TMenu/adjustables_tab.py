from PySide6.QtWidgets import QVBoxLayout

from TsUI_qt import MetroTabControl
from field_widgets import build_float_grid
from adjustables_data import ON_BOARD_FIELDS, OFF_BOARD_FIELDS

SUBTAB_FONT = ("Segoe UI", 9)

_SUBTABS = [
    ("ON BOARD", "On Board", ON_BOARD_FIELDS),
    ("OFF BOARD", "Off Board", OFF_BOARD_FIELDS),
]


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    for label, _, _ in _SUBTABS:
        subtabs.add(label)
    for label, title, fields in _SUBTABS:
        build_float_grid(subtabs.tab(label), state, title, fields, columns=2)

    return subtabs
