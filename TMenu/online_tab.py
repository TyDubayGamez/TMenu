import json
import os
import threading
import urllib.parse

import requests
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QFileDialog

from TsUI_qt import (
    MetroButton, MetroLabel, MetroTextBox, MetroTextArea, MetroDropdown,
    MetroGroupBox, MetroTabControl, SearchableDropdown, PlainKeyDropdown,
    labeled_row,
)
from app_paths import export_dir, export_save_path

import online_data as data

SUBTAB_FONT = ("Segoe UI", 9)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("CHALLENGES")
    subtabs.add("SERVER")
    subtabs.add("TOGGLEABLES")
    subtabs.add("TELEPORTER")

    _build_challenges(subtabs.tab("CHALLENGES"), win, state)
    _build_server(subtabs.tab("SERVER"), win, state)
    _build_toggleables(subtabs.tab("TOGGLEABLES"), win, state)
    _build_teleporter(subtabs.tab("TELEPORTER"), win, state)

    return subtabs

# CHALLENGES


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class _ChallengeSignals(QObject):
    apply_result = Signal(bool, str)
    io_result = Signal(bool, str)
    grab_result = Signal(bool, str, object)


def _build_challenges(parent_tab, win, state):
    signals = _ChallengeSignals(win)

    challenge_types = _load_json(data.CHALLENGE_TYPES_PATH)   # {"22": "Freeskate", ...}
    challenge_keys = _load_json(data.CHALLENGE_KEYS_PATH)      # {"38678...": "Downtown Park", ...}

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(12)

    FIELD_WIDTH = 440

    group = MetroGroupBox(parent_tab, title="Challenge")
    group.setFixedWidth(480)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    # Challenge type (plain - only 14 options, search is unnecessary)
    type_dropdown = PlainKeyDropdown(group, list(challenge_types.items()), width=FIELD_WIDTH)
    group.add(labeled_row(group, "Challenge Type", type_dropdown))

    key_dropdown = SearchableDropdown(
        group, list(challenge_keys.items()), placeholder="Search challenge / map...", width=FIELD_WIDTH)
    group.add(labeled_row(group, "Challenge / Map", key_dropdown))

    # Private / max players / team
    is_private_dd = MetroDropdown(group, items=data.BOOL_OPTIONS, width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Private", is_private_dd))

    is_team_dd = MetroDropdown(group, items=data.BOOL_OPTIONS, width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Team Challenge", is_team_dd))

    difficulty_dd = MetroDropdown(group, items=[name for name, _ in data.DIFFICULTY_OPTIONS], width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Difficulty", difficulty_dd))

    # Set Challenge
    apply_btn = MetroButton(group, text="Set Challenge", width=FIELD_WIDTH, height=36)
    group.add(apply_btn)

    grab_btn = MetroButton(group, text="Grab Current", width=FIELD_WIDTH, height=36)
    group.add(grab_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    # Export / Import
    io_row = QWidget(group)
    io_layout = QHBoxLayout(io_row)
    io_layout.setContentsMargins(0, 0, 0, 0)
    io_layout.setSpacing(10)
    export_btn = MetroButton(io_row, text="Export", width=215, height=32)
    import_btn = MetroButton(io_row, text="Import", width=215, height=32)
    io_layout.addWidget(export_btn)
    io_layout.addWidget(import_btn)
    group.add(io_row)

    io_status_lbl = MetroLabel(group, text="")
    io_status_lbl.setAlignment(Qt.AlignCenter)
    io_status_lbl.setWordWrap(True)
    group.add(io_status_lbl)

    # helpers

    def current_values():
        return {
            "challenge_type": type_dropdown.selected_key(),
            "challenge_key": key_dropdown.selected_key(),
            "is_private": is_private_dd.currentText() == "True",
            "is_team_challenge": is_team_dd.currentText() == "True",
            "difficulty_mode": difficulty_dd.currentText(),
        }

    def do_apply(values):
        try:
            if not state.is_ready():
                signals.apply_result.emit(False, "Connect and attach first.")
                return

            difficulty_write = dict(data.DIFFICULTY_OPTIONS)[values["difficulty_mode"]]

            state.ps3.Process.Memory.Set(state.pid, data.ADDR_CHALLENGE_TYPE, data.pack_ascii(str(values["challenge_type"]), 32))
            state.ps3.Process.Memory.Set(state.pid, data.ADDR_CHALLENGE_KEY, data.pack_ascii(str(values["challenge_key"]), 32))
            state.ps3.Process.Memory.Set(state.pid, data.ADDR_IS_PRIVATE, data.pack_ascii("1" if values["is_private"] else "0", 8))
            state.ps3.Process.Memory.Set(state.pid, data.ADDR_IS_TEAM, data.pack_ascii("1" if values["is_team_challenge"] else "0", 8))
            state.ps3.Process.Memory.Set(state.pid, data.ADDR_DIFFICULTY, data.pack_ascii(difficulty_write, 8))

            signals.apply_result.emit(True, "Set. Loads in at the end of the current results screen.")
        except Exception as e:
            signals.apply_result.emit(False, str(e))

    def on_apply_clicked():
        values = current_values()
        if values["challenge_type"] is None or values["challenge_key"] is None:
            status_lbl.setText("Pick a challenge type and challenge/map first.")
            return
        apply_btn.setEnabled(False)
        status_lbl.setText("Setting...")
        threading.Thread(target=do_apply, args=(values,), daemon=True).start()

    def on_apply_result(ok, msg):
        status_lbl.setText(msg)
        apply_btn.setEnabled(True)

    apply_btn.clicked.connect(on_apply_clicked)
    signals.apply_result.connect(on_apply_result)

    # -- Grab Current (reverse of Set Challenge - reads memory back into the
    # fields instead of writing them)

    def do_grab():
        try:
            if not state.is_ready():
                signals.grab_result.emit(False, "Connect and attach first.", None)
                return
            difficulty_reverse = {value: name for name, value in data.DIFFICULTY_OPTIONS}
            loaded = {
                "challenge_type": data.read_null_terminated_string(state, data.ADDR_CHALLENGE_TYPE, 32),
                "challenge_key": data.read_null_terminated_string(state, data.ADDR_CHALLENGE_KEY, 32),
                "is_private": data.read_null_terminated_string(state, data.ADDR_IS_PRIVATE, 8) == "1",
                "is_team_challenge": data.read_null_terminated_string(state, data.ADDR_IS_TEAM, 8) == "1",
                "difficulty_mode": difficulty_reverse.get(
                    data.read_null_terminated_string(state, data.ADDR_DIFFICULTY, 8)),
            }
            signals.grab_result.emit(True, "", loaded)
        except Exception as e:
            signals.grab_result.emit(False, str(e), None)

    def on_grab_clicked():
        grab_btn.setEnabled(False)
        status_lbl.setText("Grabbing...")
        threading.Thread(target=do_grab, daemon=True).start()

    def on_grab_result(ok, msg, loaded):
        grab_btn.setEnabled(True)
        if not ok:
            status_lbl.setText(msg)
            return
        errors = _apply_loaded_values(loaded)
        if errors:
            status_lbl.setText("Grabbed with issues, skipped: " + ", ".join(errors))
        else:
            status_lbl.setText("Grabbed current challenge from the game.")

    grab_btn.clicked.connect(on_grab_clicked)
    signals.grab_result.connect(on_grab_result)

    # Export/Import

    def on_export_clicked():
        values = current_values()
        if values["challenge_type"] is None or values["challenge_key"] is None:
            io_status_lbl.setText("Pick a challenge type and challenge/map first.")
            return
        path = export_save_path(
            group, "challenge", "challenge.json",
            "Export Challenge", "Challenge Files (*.json)",
        )
        if not path:
            return  # user cancelled the save dialog
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(values, f, indent=4)
            io_status_lbl.setText(f"Exported to {os.path.basename(path)}.")
        except OSError as e:
            io_status_lbl.setText(f"Export failed: {e}")

    def _apply_loaded_values(loaded):
        # pushes a challenge dict into the fields, shared by Import and Grab Current.
        # returns a list of any keys that couldn't be applied
        errors = []

        challenge_type = str(loaded.get("challenge_type", ""))
        if challenge_type not in challenge_types:
            errors.append("challenge_type")
        elif not type_dropdown.set_selected_key(challenge_type):
            errors.append("challenge_type")

        challenge_key = str(loaded.get("challenge_key", ""))
        if challenge_key not in challenge_keys:
            errors.append("challenge_key")
        elif not key_dropdown.set_selected_key(challenge_key):
            errors.append("challenge_key")

        if isinstance(loaded.get("is_private"), bool):
            is_private_dd.setCurrentText("True" if loaded["is_private"] else "False")
        else:
            errors.append("is_private")

        if isinstance(loaded.get("is_team_challenge"), bool):
            is_team_dd.setCurrentText("True" if loaded["is_team_challenge"] else "False")
        else:
            errors.append("is_team_challenge")

        difficulty_mode = loaded.get("difficulty_mode")
        if difficulty_mode in dict(data.DIFFICULTY_OPTIONS):
            difficulty_dd.setCurrentText(difficulty_mode)
        else:
            errors.append("difficulty_mode")

        return errors

    def on_import_clicked():
        # Export now lets the user pick any name/location (defaulting into
        # challenge/), so Import prompts too instead of assuming a single
        # fixed challenge.json - it still opens in challenge/ by default.
        path, _ = QFileDialog.getOpenFileName(
            group, "Import Challenge", export_dir("challenge"), "Challenge Files (*.json)"
        )
        if not path:
            return  # user cancelled the open dialog
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            io_status_lbl.setText(f"Import failed: {e}")
            return

        errors = _apply_loaded_values(loaded)
        if errors:
            io_status_lbl.setText("Imported with issues, skipped: " + ", ".join(errors))
        else:
            io_status_lbl.setText("Imported.")

    export_btn.clicked.connect(on_export_clicked)
    import_btn.clicked.connect(on_import_clicked)

    return {"group": group}

# SERVER


class _ServerSignals(QObject):
    apply_result = Signal(bool, str)
    chat_result = Signal(bool, str)


def _build_server(parent_tab, win, state):
    signals = _ServerSignals(win)

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(14)

    # Server IP routing
    ip_group = MetroGroupBox(parent_tab, title="Server IP")
    ip_group.setFixedWidth(420)
    layout.addWidget(ip_group, alignment=Qt.AlignHCenter)

    ip_row = QWidget(ip_group)
    ip_row_layout = QHBoxLayout(ip_row)
    ip_row_layout.setContentsMargins(0, 0, 0, 0)
    ip_row_layout.setSpacing(8)

    preset_dropdown = MetroDropdown(ip_row, items=[name for name, _ in data.SERVER_PRESETS], width=190, height=28)
    ip_row_layout.addWidget(preset_dropdown)

    ip_text = MetroTextBox(ip_row, width=190, height=26)
    ip_row_layout.addWidget(ip_text)

    ip_group.add(ip_row)

    apply_btn = MetroButton(ip_group, text="APPLY", width=200, height=32)
    ip_group.add(apply_btn)

    ip_status_lbl = MetroLabel(ip_group, text="")
    ip_status_lbl.setAlignment(Qt.AlignCenter)
    ip_status_lbl.setWordWrap(True)
    ip_group.add(ip_status_lbl)

    _suppress_edit_signal = {"on": False}

    def on_preset_changed(text):
        for name, ip in data.SERVER_PRESETS:
            if name == text and ip is not None:
                _suppress_edit_signal["on"] = True
                ip_text.setText(ip)
                _suppress_edit_signal["on"] = False
                return
        # "Custom" selected directly - leave the text box as-is for editing.

    def on_ip_text_edited(_text):
        if _suppress_edit_signal["on"]:
            return
        # Manual edit -> flip the dropdown to "Custom" without re-triggering
        # on_preset_changed's auto-fill.
        preset_dropdown.blockSignals(True)
        preset_dropdown.setCurrentText("Custom")
        preset_dropdown.blockSignals(False)

    preset_dropdown.currentTextChanged.connect(on_preset_changed)
    ip_text.textEdited.connect(on_ip_text_edited)

    # Default to the first preset on load.
    preset_dropdown.setCurrentIndex(0)
    ip_text.setText(data.SERVER_PRESETS[0][1])

    def do_apply(ip):
        try:
            if not state.is_ready():
                signals.apply_result.emit(False, "Connect and attach first.")
                return
            packed = data.pack_ascii(ip, data.IP_FIELD_WIDTH)
            state.ps3.Process.Memory.Set(state.pid, data.IP_FIELD_ADDRESS, packed)
            state.server_ip = ip  # used by the chat panel below
            signals.apply_result.emit(True, f"Applied: {ip}")
        except Exception as e:
            signals.apply_result.emit(False, str(e))

    def on_apply_clicked():
        ip = ip_text.text().strip()
        if not ip:
            ip_status_lbl.setText("Enter or select a server IP first.")
            return
        apply_btn.setEnabled(False)
        ip_status_lbl.setText("Applying...")
        threading.Thread(target=do_apply, args=(ip,), daemon=True).start()

    def on_apply_result(ok, msg):
        ip_status_lbl.setText(msg)
        apply_btn.setEnabled(True)

    apply_btn.clicked.connect(on_apply_clicked)
    signals.apply_result.connect(on_apply_result)

    # Chat
    chat_group = MetroGroupBox(parent_tab, title="Server Chat")
    chat_group.setFixedWidth(420)
    layout.addWidget(chat_group, alignment=Qt.AlignHCenter)

    chat_box = MetroTextArea(chat_group, width=380, height=90)
    chat_group.add(chat_box)

    send_btn = MetroButton(chat_group, text="SEND CHAT", width=200, height=32)
    chat_group.add(send_btn)

    chat_status_lbl = MetroLabel(chat_group, text="")
    chat_status_lbl.setAlignment(Qt.AlignCenter)
    chat_status_lbl.setWordWrap(True)
    chat_group.add(chat_status_lbl)

    def do_send_chat(message):
        try:
            if not state.is_ready():
                signals.chat_result.emit(False, "Connect and attach first.")
                return
            server_ip = getattr(state, "server_ip", None) or ip_text.text().strip()
            if not server_ip:
                signals.chat_result.emit(False, "Apply a server IP first.")
                return

            token = data.read_null_terminated_string(state, data.BLAZE_TOKEN_ADDRESS, data.BLAZE_TOKEN_MAX_LEN)
            if not token:
                signals.chat_result.emit(False, "Couldn't read a Blaze token from memory.")
                return

            url = f"http://{server_ip}/sendchat?token={token}&msg={urllib.parse.quote(message)}"
            resp = requests.get(url, timeout=5)
            signals.chat_result.emit(True, f"Sent ({resp.status_code}).")
        except Exception as e:
            signals.chat_result.emit(False, str(e))

    def on_send_clicked():
        message = chat_box.toPlainText()
        if not message.strip():
            chat_status_lbl.setText("Type a message first.")
            return
        send_btn.setEnabled(False)
        chat_status_lbl.setText("Sending...")
        threading.Thread(target=do_send_chat, args=(message,), daemon=True).start()

    def on_chat_result(ok, msg):
        chat_status_lbl.setText(msg)
        send_btn.setEnabled(True)
        if ok:
            chat_box.clear()

    send_btn.clicked.connect(on_send_clicked)
    signals.chat_result.connect(on_chat_result)

    return {"group_ip": ip_group, "group_chat": chat_group}

# TOGGLEABLES (Challenge Boundary)


class _ToggleSignals(QObject):
    result = Signal(bool, str)
    freeskate_result = Signal(bool, str)


def _build_toggleables(parent_tab, win, state):
    signals = _ToggleSignals(win)

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(12)

    group = MetroGroupBox(parent_tab, title="Challenge Boundary")
    group.setFixedWidth(300)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    disable_btn = MetroButton(group, text="Disable Border", width=260, height=36)
    group.add(disable_btn)

    reset_btn = MetroButton(group, text="Reset Border", width=260, height=36)
    group.add(reset_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def do_disable():
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            pid = state.pid
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_FLAG_1, bytes([0x00]))
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_FLAG_2, bytes([0x00]))
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_OPCODE, data.DISABLE_OPCODE_BYTES)
            signals.result.emit(True, "Border disabled.")
        except Exception as e:
            signals.result.emit(False, str(e))

    def do_reset():
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            pid = state.pid
            # FLAG_1 / FLAG_2 are write-once for disabling and have no
            # meaningful "original" value to restore, so reset only touches
            # the opcode address (which does have a real original value).
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_OPCODE, data.ORIGINAL_OPCODE_BYTES)
            signals.result.emit(True, "Border reset.")
        except Exception as e:
            signals.result.emit(False, str(e))

    def on_disable_clicked():
        disable_btn.setEnabled(False)
        reset_btn.setEnabled(False)
        status_lbl.setText("Working...")
        threading.Thread(target=do_disable, daemon=True).start()

    def on_reset_clicked():
        disable_btn.setEnabled(False)
        reset_btn.setEnabled(False)
        status_lbl.setText("Working...")
        threading.Thread(target=do_reset, daemon=True).start()

    def on_result(ok, msg):
        status_lbl.setText(msg)
        disable_btn.setEnabled(True)
        reset_btn.setEnabled(True)

    disable_btn.clicked.connect(on_disable_clicked)
    reset_btn.clicked.connect(on_reset_clicked)
    signals.result.connect(on_result)

    # Freeskate
    # Same flip mechanic as toggleables_tab.py's toggles: read the current
    # bytes at ADDR_CHALLENGE_TYPE, if they already match "on" (Freeskate,
    # "22") write "off" (Spot Battle, "53") instead, otherwise write "on".
    freeskate_group = MetroGroupBox(parent_tab, title="Freeskate")
    freeskate_group.setFixedWidth(300)
    layout.addWidget(freeskate_group, alignment=Qt.AlignHCenter)

    freeskate_btn = MetroButton(freeskate_group, text="Freeskate", width=260, height=36)
    freeskate_group.add(freeskate_btn)

    freeskate_status_lbl = MetroLabel(freeskate_group, text="")
    freeskate_status_lbl.setAlignment(Qt.AlignCenter)
    freeskate_status_lbl.setWordWrap(True)
    freeskate_group.add(freeskate_status_lbl)

    def do_freeskate_toggle():
        if not state.is_ready():
            signals.freeskate_result.emit(False, "Connect and attach first.")
            return
        try:
            pid = state.pid
            on_bytes = data.pack_ascii(data.FREESKATE_TYPE_ON, data.CHALLENGE_TYPE_FIELD_WIDTH)
            off_bytes = data.pack_ascii(data.FREESKATE_TYPE_OFF, data.CHALLENGE_TYPE_FIELD_WIDTH)
            current = bytes(state.ps3.Process.Memory.Get(pid, data.ADDR_CHALLENGE_TYPE, len(on_bytes)))
            turning_on = current != on_bytes
            state.ps3.Process.Memory.Set(pid, data.ADDR_CHALLENGE_TYPE, on_bytes if turning_on else off_bytes)
            signals.freeskate_result.emit(True, f"Freeskate {'ON' if turning_on else 'OFF'}.")
        except Exception as e:
            signals.freeskate_result.emit(False, str(e))

    def on_freeskate_clicked():
        freeskate_btn.setEnabled(False)
        freeskate_status_lbl.setText("Working...")
        threading.Thread(target=do_freeskate_toggle, daemon=True).start()

    def on_freeskate_result(ok, msg):
        freeskate_status_lbl.setText(msg)
        freeskate_btn.setEnabled(True)

    freeskate_btn.clicked.connect(on_freeskate_clicked)
    signals.freeskate_result.connect(on_freeskate_result)

    return {"group": group, "freeskate_group": freeskate_group}

# TELEPORTER


class _TeleportSignals(QObject):
    result = Signal(bool, str)
    camera_coords = Signal(bool, str, float, float, float)


def _write_teleport(state, x, y, z):
    # each write separate/explicit so a failure shows which of the three didn't go through
    pid = state.pid
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_ADDR, data.VEC3_BE.pack(x, y + data.TELEPORT_Y_OFFSET, z))
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_FLAG_1, bytes([0x01]))
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_FLAG_2, bytes([0x02]))


def _build_teleporter(parent_tab, win, state):
    signals = _TeleportSignals(win)

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(12)

    # Teleport to Player
    skater_group = MetroGroupBox(parent_tab, title="Teleport to Player")
    skater_group.setFixedWidth(300)
    layout.addWidget(skater_group, alignment=Qt.AlignHCenter)

    def do_teleport_to_skater(index):
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            raw = state.ps3.Process.Memory.Get(state.pid, data.skater_addr(index), 12)
            x, y, z = data.VEC3_BE.unpack(bytes(raw))
            _write_teleport(state, x, y, z)
            signals.result.emit(True, f"Teleported to Player {index + 1} ({x:.2f}, {y:.2f}, {z:.2f})")
        except Exception as e:
            signals.result.emit(False, str(e))

    def make_skater_handler(index):
        def handler():
            status_lbl.setText("Teleporting...")
            threading.Thread(target=do_teleport_to_skater, args=(index,), daemon=True).start()
        return handler

    for i in range(data.NUM_SKATERS):
        btn = MetroButton(skater_group, text=f"Teleport to Player {i + 1}", width=260, height=32)
        btn.clicked.connect(make_skater_handler(i))
        skater_group.add(btn)

    # Custom Coordinates
    custom_group = MetroGroupBox(parent_tab, title="Custom Coordinates")
    custom_group.setFixedWidth(300)
    layout.addWidget(custom_group, alignment=Qt.AlignHCenter)

    coord_row = QWidget(custom_group)
    coord_layout = QHBoxLayout(coord_row)
    coord_layout.setContentsMargins(0, 0, 0, 0)
    coord_layout.setSpacing(8)
    coord_fields = {}
    for axis in ("X", "Y", "Z"):
        col = QWidget(coord_row)
        col_layout = QVBoxLayout(col)
        col_layout.setContentsMargins(0, 0, 0, 0)
        col_layout.setSpacing(4)
        col_layout.addWidget(MetroLabel(col, text=axis))
        field = MetroTextBox(col, width=80, height=26)
        col_layout.addWidget(field)
        coord_layout.addWidget(col)
        coord_fields[axis] = field
    custom_group.add(coord_row)

    custom_btn = MetroButton(custom_group, text="Teleport to Coords", width=260, height=32)
    custom_group.add(custom_btn)

    get_coords_btn = MetroButton(custom_group, text="Get Camera Coords", width=260, height=32)
    custom_group.add(get_coords_btn)

    status_lbl = MetroLabel(parent_tab, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    layout.addWidget(status_lbl, alignment=Qt.AlignHCenter)

    def do_teleport_to_custom(x, y, z):
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            _write_teleport(state, x, y, z)
            signals.result.emit(True, f"Teleported to ({x:.2f}, {y:.2f}, {z:.2f})")
        except Exception as e:
            signals.result.emit(False, str(e))

    def on_custom_clicked():
        try:
            x = float(coord_fields["X"].text())
            y = float(coord_fields["Y"].text())
            z = float(coord_fields["Z"].text())
        except ValueError:
            status_lbl.setText("Enter valid numbers for X, Y and Z.")
            return
        status_lbl.setText("Teleporting...")
        threading.Thread(target=do_teleport_to_custom, args=(x, y, z), daemon=True).start()

    custom_btn.clicked.connect(on_custom_clicked)

    def do_get_camera_coords():
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            raw = state.ps3.Process.Memory.Get(state.pid, data.TELEPORT_ADDR, 12)
            x, y, z = data.VEC3_BE.unpack(bytes(raw))
            signals.camera_coords.emit(True, f"Loaded camera coords ({x:.2f}, {y:.2f}, {z:.2f}).", x, y, z)
        except Exception as e:
            signals.camera_coords.emit(False, str(e), 0.0, 0.0, 0.0)

    def on_get_coords_clicked():
        status_lbl.setText("Reading camera coords...")
        threading.Thread(target=do_get_camera_coords, daemon=True).start()

    get_coords_btn.clicked.connect(on_get_coords_clicked)

    def on_camera_coords(ok, msg, x, y, z):
        if ok:
            coord_fields["X"].setText(f"{x:.2f}")
            coord_fields["Y"].setText(f"{y:.2f}")
            coord_fields["Z"].setText(f"{z:.2f}")
        status_lbl.setText(msg)

    signals.camera_coords.connect(on_camera_coords)

    def on_result(ok, msg):
        status_lbl.setText(msg)

    signals.result.connect(on_result)

    return {"group_skater": skater_group, "group_custom": custom_group}
