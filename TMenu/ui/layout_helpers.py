"""
layout_helpers.py
=================
Small shared pieces for the card-style tab layout (same look as ONLINE >
PLAYERS): groups sit SIDE BY SIDE in a centered row instead of stacking into
one tall column, and every button/card uses the same sizes.

    row = card_row(tab)                       # centered, top-aligned row
    build_toggle_group(tab, state, ..., parent_layout=row)
    build_float_grid(tab, state, ..., parent_layout=row)

Any builder that takes `parent_layout` and calls
`layout.addWidget(group, alignment=Qt.AlignHCenter)` works unchanged - the
row ignores the horizontal-center hint and pins every card to the top so
cards of different heights line up along their top edge.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

CARD_SPACING = 16          # gap between side-by-side cards
CARD_PADDING = 34          # MetroGroupBox left+right inner margins (16+16) plus its 1px borders
BTN_WIDTH = 200            # standard card button
BTN_HEIGHT = 30
BTN_GAP = 10


def card_width(columns, col_width=BTN_WIDTH, gap=BTN_GAP):
    """Group-box width that exactly fits `columns` columns of `col_width`."""
    return columns * col_width + (columns - 1) * gap + CARD_PADDING


class _TopRow(QHBoxLayout):
    """HBox that always top-aligns whatever is added to it."""

    def addWidget(self, widget, stretch=0, alignment=Qt.Alignment()):
        super().addWidget(widget, stretch, Qt.AlignTop)


def card_row(tab, top_margin=20):
    """Puts a centered row of cards on `tab` and returns the row layout -
    pass it as `parent_layout` to the group builders."""
    outer = QVBoxLayout(tab)
    outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    outer.setContentsMargins(0, top_margin, 0, 0)
    row = _TopRow()
    row.setSpacing(CARD_SPACING)
    outer.addLayout(row)
    return row
