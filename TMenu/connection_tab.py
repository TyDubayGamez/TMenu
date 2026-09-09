import threading

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroSwitch
from connection_core import do_connect_and_attach


class _Signals(QObject):
    connect_result = Signal(bool, str)
    disconnect_result = Signal(bool, str)


def build(parent_tab, win, state, settings=None):
    signals = _Signals(win)  # parented to the window so it lives on the GUI thread
    win._connection = None  # populated below with the connect/disconnect/auto helpers

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 30, 0, 0)

    group = MetroGroupBox(parent_tab, title="Connection")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    ip_box = MetroTextBox(group, width=200, height=26)
    ip_box.setPlaceholderText("PS3 IP address")
    if settings is not None and settings.last_ip:
        ip_box.setText(settings.last_ip)

    connect_btn = MetroButton(group, text="CONNECT", width=200)
    disconnect_btn = MetroButton(group, text="DISCONNECT", width=200)

    if state.is_ready():
        initial_status = f"Attached to {state.attached_name}" if state.attached_name else "Connected"
    elif state.connected:
        initial_status = f"Connected to {state.ip}"
    else:
        initial_status = "Disconnected"
    status_lbl = MetroLabel(group, text=initial_status)
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    for w in (ip_box, connect_btn, disconnect_btn):
        group.add(w)

    # Auto-connect switch
    auto_switch = None
    if settings is not None:
        switch_row = QWidget(group)
        switch_row.setStyleSheet("background: transparent;")
        switch_row_layout = QHBoxLayout(switch_row)
        switch_row_layout.setContentsMargins(0, 4, 0, 0)
        switch_row_layout.setSpacing(10)
        switch_label = MetroLabel(switch_row, text="Auto-connect on startup")
        auto_switch = MetroSwitch(switch_row)
        auto_switch.setChecked(settings.auto_connect)
        switch_row_layout.addWidget(switch_label)
        switch_row_layout.addStretch(1)
        switch_row_layout.addWidget(auto_switch)
        group.add(switch_row)

        def on_auto_toggled(checked):
            settings.auto_connect = checked
            settings.save()

        auto_switch.toggled.connect(on_auto_toggled)

    group.add(status_lbl)

    # background work (runs off the GUI thread)

    def do_connect():
        ip = ip_box.text().strip()
        if not ip:
            signals.connect_result.emit(False, "Enter an IP address first.")
            return
        ok, msg = do_connect_and_attach(state, ip, settings=settings)
        signals.connect_result.emit(ok, msg)

    def do_disconnect():
        try:
            state.ps3.DisconnectTarget()
        except Exception:
            pass
        state.connected = False
        state.attached = False
        state.attached_name = ""
        signals.disconnect_result.emit(True, "Disconnected.")

    # UI callbacks

    def on_connect_clicked():
        status_lbl.setText("Connecting...")
        connect_btn.setEnabled(False)
        threading.Thread(target=do_connect, daemon=True).start()

    def on_disconnect_clicked():
        status_lbl.setText("Disconnecting...")
        disconnect_btn.setEnabled(False)
        threading.Thread(target=do_disconnect, daemon=True).start()

    def on_connect_result(ok, msg):
        status_lbl.setText(msg)
        connect_btn.setEnabled(True)

    def on_disconnect_result(ok, msg):
        status_lbl.setText(msg)
        disconnect_btn.setEnabled(True)
        connect_btn.setEnabled(True)

    connect_btn.clicked.connect(on_connect_clicked)
    disconnect_btn.clicked.connect(on_disconnect_clicked)
    signals.connect_result.connect(on_connect_result)
    signals.disconnect_result.connect(on_disconnect_result)

    def auto_connect():
        # runs at startup if auto_connect is on and there's a saved IP
        if settings is None or not settings.auto_connect:
            return
        if not ip_box.text().strip():
            return
        on_connect_clicked()

    return {
        "group": group,
        "connect": on_connect_clicked,
        "disconnect": on_disconnect_clicked,
        "auto_connect": auto_connect,
    }
