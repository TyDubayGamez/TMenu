"""
visuals_tab.py
================
Builds the top-level VISUALS tab as six subtabs: TOGGLEABLES (the on/off
visual mods that used to live under TOGGLEABLES>VISUALS before being split
out into their own top-level tab), ADJUSTABLES (Transparency/FoV plus
Skater Color), ENVIRONMENT, WORLD (Fog Color/Density/Distance), HUD (Score
Multiplier, Exposure, and the Glitchy Text toggle - custom-built below since
none of the three are a plain single-field grid), and SCREEN. Same
MetroTabControl-as-subtabs pattern toggleables_tab.py / edit_skater_tab.py
use.

ADJUSTABLES/ENVIRONMENT/WORLD/SCREEN's plain float fields are built by
field_widgets.build_float_grid against visuals_data.py; ADJUSTABLES' Skater
Color and WORLD's Fog Color are built by field_widgets.build_rgb_field_group
instead (a 12-byte/3-float RGB value isn't a single field). A subtab that
holds more than one group (WORLD, and now ADJUSTABLES/HUD too) shares one
QVBoxLayout across all of them via `parent_layout` - see those two
functions' docstrings for why.
"""

import math
import struct

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroTabControl
from field_widgets import build_float_grid, build_rgb_field_group
from gui_refresh import on_attach_refresh
from toggleables_tab import build_toggle_group, SUBTAB_FONT
from toggleables_data import VISUALS_TOGGLES, HUD_TOGGLES
from visuals_data import (
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, SCREEN_FIELDS, WORLD_FIELDS, HUD_FIELDS,
    SKATER_COLOR_ADDRESS, SKATER_COLOR_DEFAULT,
    FOG_COLOR_ADDRESS, FOG_COLOR_DEFAULT,
    SCORE_X1_ADDRESS, SCORE_X2_ADDRESS, SCORE_X3_ADDRESS, SCORE_MULTIPLIER_DEFAULT,
)


def _build_score_multiplier(tab, state, parent_layout):
    """One base value the person types in (e.g. 30) gets written as-is to
    ScoreX1, doubled to ScoreX2, and tripled to ScoreX3 (30/60/90). GET
    reads ScoreX1 back as the base. Added into HUD's shared layout by
    _build_hud below, same `parent_layout` convention as
    field_widgets.build_float_grid/build_rgb_field_group."""
    group = MetroGroupBox(tab, title="Score Multiplier")
    group.setFixedWidth(250)
    parent_layout.addWidget(group, alignment=Qt.AlignHCenter)

    lbl = MetroLabel(group, text="Base Score (x1)")
    lbl.setAlignment(Qt.AlignCenter)
    group.add(lbl)

    box = MetroTextBox(group, width=200, height=26)
    box.setPlaceholderText(f"{SCORE_MULTIPLIER_DEFAULT:g}")
    group.add(box)

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
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, SCORE_X1_ADDRESS, 4))
            value = struct.unpack(">f", raw)[0]
            box.setText(f"{value:.4f}")
            status_lbl.setText("Score Multiplier loaded.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        text = box.text().strip() or str(SCORE_MULTIPLIER_DEFAULT)
        try:
            base = float(text)
        except ValueError:
            status_lbl.setText("Base Score must be a number.")
            return
        try:
            for addr, mult in ((SCORE_X1_ADDRESS, 1), (SCORE_X2_ADDRESS, 2), (SCORE_X3_ADDRESS, 3)):
                state.ps3.Process.Memory.Set(state.pid, addr, struct.pack(">f", base * mult))
            status_lbl.setText(f"Score Multiplier set to {base:g} / {base * 2:g} / {base * 3:g}.")
        except Exception as e:
            status_lbl.setText(str(e))

    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)

    def _refresh_on_attach():
        # Same "only prefill if it isn't the vanilla default" rule as the
        # plain field grids (field_widgets.py) - base 1.0 is the untouched
        # state, anything else means someone's already set a multiplier.
        raw = bytes(state.ps3.Process.Memory.Get(state.pid, SCORE_X1_ADDRESS, 4))
        value = struct.unpack(">f", raw)[0]
        if not math.isclose(value, SCORE_MULTIPLIER_DEFAULT, rel_tol=1e-4, abs_tol=1e-4):
            box.setText(f"{value:.4f}")

    on_attach_refresh(state, group, _refresh_on_attach)


def _build_adjustables(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    build_float_grid(tab, state, "Adjustables", ADJUSTABLES_FIELDS, columns=2, parent_layout=layout)
    build_rgb_field_group(
        tab, win, state, "Skater Color", SKATER_COLOR_ADDRESS,
        default=SKATER_COLOR_DEFAULT, parent_layout=layout,
    )


def _build_world(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    build_rgb_field_group(
        tab, win, state, "Fog Color", FOG_COLOR_ADDRESS,
        default=FOG_COLOR_DEFAULT, parent_layout=layout,
    )
    build_float_grid(tab, state, "Fog", WORLD_FIELDS, columns=2, parent_layout=layout)


def _build_hud(tab, state):
    """Score Multiplier - one base value the person types in (e.g. 30) gets
    written as-is to ScoreX1, doubled to ScoreX2, and tripled to ScoreX3
    (30/60/90). Exposure is a plain single float field. Glitchy Text is a
    plain on/off toggle (toggleables_data.HUD_TOGGLES) - all three share
    this one subtab/layout since none is a plain multi-field grid on its
    own."""
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    _build_score_multiplier(tab, state, layout)
    build_float_grid(tab, state, "HUD", HUD_FIELDS, columns=1, parent_layout=layout)
    build_toggle_group(tab, state, "HUD Toggles", HUD_TOGGLES, parent_layout=layout)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("TOGGLEABLES")
    build_toggle_group(subtabs.tab("TOGGLEABLES"), state, "Visuals", VISUALS_TOGGLES)

    subtabs.add("ADJUSTABLES")
    _build_adjustables(subtabs.tab("ADJUSTABLES"), win, state)

    subtabs.add("ENVIRONMENT")
    build_float_grid(subtabs.tab("ENVIRONMENT"), state, "Environment", ENVIRONMENT_FIELDS, columns=2)

    subtabs.add("WORLD")
    _build_world(subtabs.tab("WORLD"), win, state)

    subtabs.add("HUD")
    _build_hud(subtabs.tab("HUD"), state)

    subtabs.add("SCREEN")
    build_float_grid(subtabs.tab("SCREEN"), state, "Screen", SCREEN_FIELDS, columns=2)

    return subtabs
