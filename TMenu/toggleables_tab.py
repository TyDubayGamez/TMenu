from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroGroupBox, MetroTabControl, set_widget_bold
from gui_refresh import on_attach_refresh

from toggleables_data import (
    ONBOARD_TOGGLES, OFFBOARD_TOGGLES,
    ENVIRONMENT_TOGGLES, MISC_TOGGLES,
)

SUBTAB_FONT = ("Segoe UI", 9)

# (tab label, group box title, data dict) - the order here is the order the
# subtabs appear in.
_SUBTABS = [
    ("ON BOARD", "On Board", ONBOARD_TOGGLES),
    ("OFF BOARD", "Off Board", OFFBOARD_TOGGLES),
    ("ENVIRONMENT", "Environment", ENVIRONMENT_TOGGLES),
    ("MISC", "Misc", MISC_TOGGLES),
]


def _populate_subtabs(subtabs, state):
    # builds every TOGGLEABLES subtab, shared by the tab control and the VIEW ALL popup
    for label, _, _ in _SUBTABS:
        subtabs.add(label)
    for label, title, toggles in _SUBTABS:
        build_toggle_group(subtabs.tab(label), state, title, toggles)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    _populate_subtabs(subtabs, state)

    return subtabs


def build_toggle_group(tab, state, title, toggles, parent_layout=None):
    # builds one toggle-button group box. public so visuals_tab.py can reuse
    # it too. pass an existing QVBoxLayout as parent_layout when a subtab
    # holds more than one group.
    if parent_layout is None:
        layout = QVBoxLayout(tab)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        layout.setContentsMargins(0, 20, 0, 0)
    else:
        layout = parent_layout

    group = MetroGroupBox(tab, title=title)
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    if not toggles:
        empty_lbl = MetroLabel(group, text="Nothing here yet.")
        empty_lbl.setAlignment(Qt.AlignCenter)
        group.add(empty_lbl)
        group.add(status_lbl)
        return

    bold_buttons = []  # (btn, writes) pairs, checked again by the on-attach refresh below

    def _is_on(writes):
        # reads writes[0] from memory and reports whether it's currently on
        first = writes[0]
        current = bytes(state.ps3.Process.Memory.Get(state.pid, first["address"], len(first["on"])))
        return current == first["on"]

    def make_toggle_handler(name, cfg, btn):
        writes = cfg["writes"]

        def on_clicked():
            if not state.is_ready():
                status_lbl.setText("Connect and attach first.")
                return
            pid = state.pid
            try:
                # The first address decides whether this toggle currently
                # reads as on or off - the rest just follow along with it.
                first = writes[0]
                current = bytes(state.ps3.Process.Memory.Get(pid, first["address"], len(first["on"])))
                turning_on = current != first["on"]

                for w in writes:
                    data = w["on"] if turning_on else w["off"]
                    state.ps3.Process.Memory.Set(pid, w["address"], data)

                set_widget_bold(btn, turning_on)
                status_lbl.setText(f"{name} {'ON' if turning_on else 'OFF'}.")
            except Exception as e:
                status_lbl.setText(str(e))

        return on_clicked

    for name, cfg in toggles.items():
        btn = MetroButton(group, text=name, width=240, height=32)
        btn.clicked.connect(make_toggle_handler(name, cfg, btn))
        group.add(btn)
        bold_buttons.append((btn, cfg["writes"]))

    group.add(status_lbl)

    def _refresh_bold_states():
        # Silent - never touches status_lbl. A toggle whose read fails
        # (or that isn't in a determinable state yet) is just left as-is
        # rather than guessed at.
        for btn, writes in bold_buttons:
            try:
                set_widget_bold(btn, _is_on(writes))
            except Exception:
                pass

    on_attach_refresh(state, group, _refresh_bold_states)
