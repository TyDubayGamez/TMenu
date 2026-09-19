"""
misc_tab.py
===========
Builds the top-level MISC tab as its own row of subtabs, using the same
MetroTabControl-as-subtabs pattern edit_skater_tab.py / toggleables_tab.py
use. Right now it holds a single DEBUG subtab.

DEBUG contains:

  - Debug Cam - a one-way write button (no off state). Every click writes the
    same fixed bytes to two addresses and reports "Debug Cam SET".
        47C98DD0 = 02
        47C68157 = 02

  - Animation Debug - a plain on/off toggle at a single address. It reads the
    current byte to decide direction, same mechanic as the TOGGLEABLES tab.
        47C98DD2 = 00  (on)
        47C98DD2 = 01  (off)

These are plain 8-digit PS3 addresses (same style as toggleables_data), used
exactly as given - nothing to strip.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from TsUI_qt import MetroButton, MetroLabel, MetroGroupBox, MetroTabControl

SUBTAB_FONT = ("Segoe UI", 9)

# Debug Cam - one-way write, always the same bytes to both addresses.
DEBUG_CAM_WRITES = [
    {"address": 0x47C98DD0, "value": bytes([0x02])},
    {"address": 0x47C68157, "value": bytes([0x02])},
]

# Animation Debug - single-address on/off toggle.
ANIMATION_DEBUG = {
    "address": 0x47C98DD2,
    "on": bytes([0x00]),
    "off": bytes([0x01]),
}


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("DEBUG")
    _build_debug(subtabs.tab("DEBUG"), state)

    return subtabs


def _build_debug(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Debug")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    # -- Debug Cam - one-way write ---------------------------------------
    debug_cam_btn = MetroButton(group, text="Debug Cam", width=240, height=32)
    group.add(debug_cam_btn)

    def on_debug_cam_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            pid = state.pid
            for w in DEBUG_CAM_WRITES:
                state.ps3.Process.Memory.Set(pid, w["address"], w["value"])
            status_lbl.setText("Debug Cam SET.")
        except Exception as e:
            status_lbl.setText(str(e))

    debug_cam_btn.clicked.connect(on_debug_cam_clicked)

    # -- Animation Debug - on/off toggle ---------------------------------
    anim_btn = MetroButton(group, text="Animation Debug", width=240, height=32)
    group.add(anim_btn)

    def on_anim_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            pid = state.pid
            current = bytes(state.ps3.Process.Memory.Get(
                pid, ANIMATION_DEBUG["address"], len(ANIMATION_DEBUG["on"])))
            turning_on = current != ANIMATION_DEBUG["on"]
            data = ANIMATION_DEBUG["on"] if turning_on else ANIMATION_DEBUG["off"]
            state.ps3.Process.Memory.Set(pid, ANIMATION_DEBUG["address"], data)
            status_lbl.setText(f"Animation Debug {'ON' if turning_on else 'OFF'}.")
        except Exception as e:
            status_lbl.setText(str(e))

    anim_btn.clicked.connect(on_anim_clicked)

    group.add(status_lbl)
