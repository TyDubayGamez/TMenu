from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout

from TsUI_qt import MetroButton, MetroLabel, MetroGroupBox, MetroTabControl

from toggleables_data import DEBUG_CAM_WRITES, ANIMATION_DEBUG_TOGGLE

SUBTAB_FONT = ("Segoe UI", 9)


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

    # debug cam
    debug_cam_btn = MetroButton(group, text="Debug Cam", width=240, height=32)

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
    group.add(debug_cam_btn)

    # animation debug
    anim_btn = MetroButton(group, text="Animation Debug", width=240, height=32)

    def on_anim_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            pid = state.pid
            cfg = ANIMATION_DEBUG_TOGGLE
            current = bytes(state.ps3.Process.Memory.Get(pid, cfg["address"], len(cfg["on"])))
            turning_on = current != cfg["on"]
            data = cfg["on"] if turning_on else cfg["off"]
            state.ps3.Process.Memory.Set(pid, cfg["address"], data)
            status_lbl.setText(f"Animation Debug {'ON' if turning_on else 'OFF'}.")
        except Exception as e:
            status_lbl.setText(str(e))

    anim_btn.clicked.connect(on_anim_clicked)
    group.add(anim_btn)

    group.add(status_lbl)
