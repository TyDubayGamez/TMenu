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
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from ui.TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroTabControl
from ui.field_widgets import build_float_grid, build_rgb_field_group
from core.gui_refresh import on_attach_refresh
from ui.layout_helpers import card_row
from tabs.toggleables_tab import build_toggle_group, SUBTAB_FONT
from core import session_changes
from tabs.toggleables_data import VISUALS_TOGGLES, HUD_TOGGLES
from tabs.visuals_data import (
    ADJUSTABLES_FIELDS, ENVIRONMENT_FIELDS, SCREEN_FIELDS, WORLD_FIELDS, HUD_FIELDS,
    SKATER_COLOR_ADDRESS, SKATER_COLOR_DEFAULT,
    FOG_COLOR_ADDRESS, FOG_COLOR_DEFAULT,
    SCORE_X1_ADDRESS, SCORE_MULTIPLIER_DEFAULT, SCORE_MULTIPLIER_FACTORS, SCORE_ADDRESSES,
    read_score_multiplier,
)


def _build_score_multiplier(tab, state, parent_layout):
    """One base value the person types in (e.g. 30) gets multiplied by 1 /
    0.5 / 0.25 for ScoreX1 / X2 / X3 (30 / 15 / 7.5). GET reads ScoreX1
    back and divides by 1 to recover the base. Added into HUD's shared layout by
    _build_hud below, same `parent_layout` convention as
    field_widgets.build_float_grid/build_rgb_field_group."""
    group = MetroGroupBox(tab, title="Score Multiplier")
    group.setFixedWidth(250)
    parent_layout.addWidget(group, alignment=Qt.AlignHCenter)

    lbl = MetroLabel(group, text="Base Score")
    lbl.setAlignment(Qt.AlignCenter)
    group.add(lbl)

    box = MetroTextBox(group, width=208, height=26)
    box.setPlaceholderText(f"{SCORE_MULTIPLIER_DEFAULT:g}")
    group.add(box)

    btn_row = QWidget(group)
    btn_row.setStyleSheet("background: transparent;")
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 0, 0, 0)
    btn_row_layout.setSpacing(10)
    get_btn = MetroButton(btn_row, text="GET", width=99, height=30)
    set_btn = MetroButton(btn_row, text="SET", width=99, height=30)
    btn_row_layout.addWidget(get_btn)
    btn_row_layout.addWidget(set_btn)
    group.add(btn_row)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            value = read_score_multiplier(state)
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
            written = [base * f for f in SCORE_MULTIPLIER_FACTORS]
            for addr, val in zip(SCORE_ADDRESSES, written):
                state.ps3.Process.Memory.Set(state.pid, addr, struct.pack(">f", val))
            session_changes.mark_hud_score_multiplier(base, SCORE_MULTIPLIER_DEFAULT)
            status_lbl.setText(f"Score Multiplier set to {written[0]:g} / {written[1]:g} / {written[2]:g}.")
        except Exception as e:
            status_lbl.setText(str(e))

    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)

    def _read_on_attach():
        # Runs on a background thread (memory read only, no widgets).
        return read_score_multiplier(state)

    def _apply_on_attach(value):
        # Same "only prefill if it isn't the vanilla default" rule as the
        # plain field grids (field_widgets.py) - base 1.0 is the untouched
        # state, anything else means someone's already set a multiplier.
        if not math.isclose(value, SCORE_MULTIPLIER_DEFAULT, rel_tol=1e-4, abs_tol=1e-4):
            box.setText(f"{value:.4f}")

    on_attach_refresh(state, group, _apply_on_attach, read=_read_on_attach)


def _build_adjustables(tab, win, state):
    layout = card_row(tab)   # Adjustables + Skater Color side by side

    build_float_grid(tab, state, "Adjustables", ADJUSTABLES_FIELDS, columns=2, parent_layout=layout)
    build_rgb_field_group(
        tab, win, state, "Skater Color", SKATER_COLOR_ADDRESS,
        default=SKATER_COLOR_DEFAULT, parent_layout=layout, session_key="skater_color",
    )


def _build_world(tab, win, state):
    layout = card_row(tab)   # Fog Color + Fog side by side

    build_rgb_field_group(
        tab, win, state, "Fog Color", FOG_COLOR_ADDRESS,
        default=FOG_COLOR_DEFAULT, parent_layout=layout, session_key="fog_color",
    )
    build_float_grid(tab, state, "Fog", WORLD_FIELDS, columns=2, parent_layout=layout)


def _build_hud(tab, state):
    """Score Multiplier - one base value the person types in (e.g. 30) gets
    multiplied by 1 / 0.5 / 0.25 for ScoreX1 / X2 / X3 (30 / 15 / 7.5). Exposure is a plain single float field. Glitchy Text is a
    plain on/off toggle (toggleables_data.HUD_TOGGLES) - all three share
    this one subtab/layout since none is a plain multi-field grid on its
    own."""
    layout = card_row(tab)   # Score Multiplier / Exposure / toggles in one row

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
