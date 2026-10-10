"""
challenge_tab.py
=================
Builds the top-level CHALLENGE tab as two subtabs (PARTY PLAY / TIMERS),
same MetroTabControl-as-subtabs pattern the other multi-subtab tabs use.

PARTY PLAY
  - Better Party Play: a normal on/off toggle (built by
    toggleables_tab.build_toggle_group, so its bold on/off state, on-attach
    refresh, BINDS hotkey and SAVE CONFIG tracking all work like any other
    toggle). It used to live under TOGGLEABLES > MISC.
  - 1 Player Party Play: a one-way button that writes 01 to 3004A487. It has
    no off state and is NOT a plain toggle - it only takes effect when it's
    pressed on the Party Play player-amount select screen WITHOUT changing
    the selection, and then X is pressed in-game.

TIMERS
  - Float fields (field_widgets.build_float_grid) for the game's challenge /
    ragdoll timers. Leave a box empty and SET writes the vanilla default
    (shown greyed-out in the box).

Address/value data lives in challenge_data.py.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from ui.TsUI_qt import MetroButton, MetroLabel, MetroGroupBox, MetroTabControl
from ui.field_widgets import build_float_grid
from tabs.toggleables_tab import build_toggle_group
from tabs.challenge.challenge_data import (
    PARTY_PLAY_TOGGLES, ONE_PLAYER_PARTY_PLAY, TIMER_FIELDS,
)

SUBTAB_FONT = ("Segoe UI", 9)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("PARTY PLAY")
    subtabs.add("TIMERS")
    _build_party_play(subtabs.tab("PARTY PLAY"), state)
    # 7 fields in 3 columns keeps this to three short rows; the group is
    # made wider than the default so the longest label ("Hall Of Meat
    # Challenge Timer") doesn't push the last column out of the box.
    build_float_grid(subtabs.tab("TIMERS"), state, "Timers", TIMER_FIELDS, columns=3, group_width=680)

    return subtabs


def _build_party_play(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(14)

    # -- Better Party Play: ordinary on/off toggle ------------------------
    build_toggle_group(tab, state, "Party Play", PARTY_PLAY_TOGGLES, parent_layout=layout)

    # -- 1 Player Party Play: one-way write, order-sensitive --------------
    group = MetroGroupBox(tab, title="1 Player Party Play")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    note = MetroLabel(
        group,
        text="Press this on the Party Play player-amount screen without "
             "changing your selection, then press X.",
    )
    note.setAlignment(Qt.AlignCenter)
    note.setWordWrap(True)
    note.setFixedHeight(58)   # wrapped text doesn't size the group by itself
    group.add(note)

    btn = MetroButton(group, text="1 Player Party Play", width=240, height=32)
    group.add(btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(
                state.pid, ONE_PLAYER_PARTY_PLAY["address"], ONE_PLAYER_PARTY_PLAY["value"])
            status_lbl.setText("1 Player Party Play SET - now press X.")
        except Exception as e:
            status_lbl.setText(str(e))

    btn.clicked.connect(on_clicked)
