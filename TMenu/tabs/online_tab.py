"""
online_tab.py
=============
Builds the ONLINE tab as four subtabs - CHALLENGES, SERVER, TOGGLEABLES,
and PLAYERS - using the same MetroTabControl-as-subtabs pattern
edit_skater_tab.py / toggleables_tab.py use.

This used to be four separate files (challenges_tab.py, server_tab.py,
multiplayer_toggleables_tab.py, multiplayer_teleporter_tab.py) plus the
multiplayer_tab.py that stitched them together. It's now one tab file +
online_data.py for the addresses/presets/JSON paths, same split as
toggleables_tab.py / toggleables_data.py.

Subtabs -------------------------------------------------------------------
  CHALLENGES  - sets challenge type/key/privacy/player-count/team/
                difficulty in local memory, written all at once with
                "Apply to Game". Export/Import via a Save/Open dialog
                defaulted into the challenge/ folder next to the app.
  SERVER      - routes the game at a target server IP, and sends chat
                messages through that server's HTTP chat API.
  TOGGLEABLES - Disable Border / Reset Border for the challenge boundary.
  PLAYERS     - the lobby's player names (read on demand with REFRESH LIST,
                never on a timer) with a Teleport button to the right of
                each name, plus a Reset button (the RTM reset - then the
                debug cam is teleported to that player first). More per-player
                actions will go in that same spot later - plus a Custom Coordinates box. Local-only: it
                never writes to another skater's slot.
"""

import json
import os
import threading
import time
import urllib.parse

import requests
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QFileDialog

from ui.TsUI_qt import (
    MetroButton, MetroLabel, MetroTextBox, MetroTextArea, MetroDropdown,
    MetroGroupBox, MetroTabControl, SearchableDropdown, PlainKeyDropdown,
    labeled_row,
)
from core.app_paths import export_dir, export_save_path

from tabs import online_data as data

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
    subtabs.add("PLAYERS")

    _build_challenges(subtabs.tab("CHALLENGES"), win, state)
    _build_server(subtabs.tab("SERVER"), win, state)
    _build_toggleables(subtabs.tab("TOGGLEABLES"), win, state)
    _build_players(subtabs.tab("PLAYERS"), win, state)

    return subtabs


# ============================================================================
# CHALLENGES
# ============================================================================

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

    # -- Challenge type (plain - only 14 options, search is unnecessary) ----
    type_dropdown = PlainKeyDropdown(group, list(challenge_types.items()), width=FIELD_WIDTH)
    group.add(labeled_row(group, "Challenge Type", type_dropdown))

    key_dropdown = SearchableDropdown(
        group, list(challenge_keys.items()), placeholder="Search challenge / map...", width=FIELD_WIDTH)
    group.add(labeled_row(group, "Challenge / Map", key_dropdown))

    # -- Private / max players / team ---------------------------------------
    is_private_dd = MetroDropdown(group, items=data.BOOL_OPTIONS, width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Private", is_private_dd))

    is_team_dd = MetroDropdown(group, items=data.BOOL_OPTIONS, width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Team Challenge", is_team_dd))

    difficulty_dd = MetroDropdown(group, items=[name for name, _ in data.DIFFICULTY_OPTIONS], width=FIELD_WIDTH, height=28)
    group.add(labeled_row(group, "Difficulty", difficulty_dd))

    # -- Set Challenge --------------------------------------------------------
    apply_btn = MetroButton(group, text="Set Challenge", width=FIELD_WIDTH, height=36)
    group.add(apply_btn)

    grab_btn = MetroButton(group, text="Grab Current", width=FIELD_WIDTH, height=36)
    group.add(grab_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    # -- Export / Import ------------------------------------------------------
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

    # -- helpers --------------------------------------------------------------

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
    #    fields instead of writing them) --------------------------------------

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

    # -- Export/Import --------------------------------------------------------

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
        """Pushes a {challenge_type, challenge_key, is_private,
        is_team_challenge, difficulty_mode} dict into the fields, same shape
        current_values()/on_export_clicked produce. Shared by Import (loaded
        from challenge.json) and Grab Current (loaded from game memory).
        Returns a list of any keys that couldn't be applied."""
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


# ============================================================================
# SERVER
# ============================================================================

class _ServerSignals(QObject):
    apply_result = Signal(bool, str)
    chat_result = Signal(bool, str)


def _build_server(parent_tab, win, state):
    signals = _ServerSignals(win)

    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(14)

    # -- Server IP routing -------------------------------------------------
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

    # -- Chat ---------------------------------------------------------------
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


# ============================================================================
# TOGGLEABLES (Challenge Boundary)
# ============================================================================

class _ToggleSignals(QObject):
    result = Signal(bool, str)
    freeskate_result = Signal(bool, str)
    proposals_result = Signal(bool, str)


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
            # FLAG_1 toggles back off, FLAG_2's whole region gets zeroed out,
            # and the opcode write goes back to its original 3 bytes.
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_FLAG_1, bytes([0x00]))
            state.ps3.Process.Memory.Set(pid, data.ADDR_BORDER_FLAG_2, data.BORDER_FLAG_2_RESET_BYTES)
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

    # -- Freeskate ------------------------------------------------------------
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

    # -- Allow Proposals -------------------------------------------------------
    # Not a toggle: every click just writes "true\0" over the word "false".
    proposals_group = MetroGroupBox(parent_tab, title="Proposals")
    proposals_group.setFixedWidth(300)
    layout.addWidget(proposals_group, alignment=Qt.AlignHCenter)

    proposals_btn = MetroButton(proposals_group, text="Allow Proposals", width=260, height=36)
    proposals_group.add(proposals_btn)

    proposals_status_lbl = MetroLabel(proposals_group, text="")
    proposals_status_lbl.setAlignment(Qt.AlignCenter)
    proposals_status_lbl.setWordWrap(True)
    proposals_group.add(proposals_status_lbl)

    def do_allow_proposals():
        if not state.is_ready():
            signals.proposals_result.emit(False, "Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, data.ADDR_ALLOW_PROPOSALS, data.ALLOW_PROPOSALS_BYTES)
            signals.proposals_result.emit(True, "Proposals allowed.")
        except Exception as e:
            signals.proposals_result.emit(False, str(e))

    def on_proposals_clicked():
        proposals_btn.setEnabled(False)
        proposals_status_lbl.setText("Working...")
        threading.Thread(target=do_allow_proposals, daemon=True).start()

    def on_proposals_result(ok, msg):
        proposals_status_lbl.setText(msg)
        proposals_btn.setEnabled(True)

    proposals_btn.clicked.connect(on_proposals_clicked)
    signals.proposals_result.connect(on_proposals_result)

    return {"group": group, "freeskate_group": freeskate_group, "proposals_group": proposals_group}


# ============================================================================
# PLAYERS
# ============================================================================

class _PlayersSignals(QObject):
    result = Signal(bool, str)
    camera_coords = Signal(bool, str, float, float, float)
    names = Signal(bool, str, object, bool, int)   # ok, message, [name|None]*6, in_online_game, local slot (-1 unknown)
    reset_done = Signal(bool, str)


def _write_teleport(state, x, y, z):
    """Each write is separate and explicit so a failure clearly shows which
    of the three didn't go through, instead of one opaque error."""
    pid = state.pid
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_ADDR, data.VEC3_BE.pack(x, y + data.TELEPORT_Y_OFFSET, z))
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_FLAG_1, bytes([0x01]))
    state.ps3.Process.Memory.Set(pid, data.TELEPORT_FLAG_2, bytes([0x02]))


_reset_lock = threading.Lock()
YOU_STYLE = "color: #4DA3FF; font-weight: bold; border: none; background: transparent;"


def _reset_player(state, index):
    """Blocking (call off the GUI thread). Grabs player `index`'s (0-5)
    coordinates and teleports the debug cam to them (the normal teleport -
    this is the ONLY place the debug cam flag at TELEPORT_FLAG_1 is written),
    then RTM-resets them: patch the function to `li r9,index`, poke the
    remaining trigger byte, wait, restore the original bytes (always, even if
    a write fails). Returns the player's (x, y, z)."""
    mem = state.ps3.Process.Memory
    pid = state.pid
    cur = bytes(mem.Get(pid, data.RESET_FUNC_ADDR, 4))
    if cur != data.RESET_FUNC_ORIG and cur[:3] != b"\x39\x20\x00":
        raise RuntimeError(f"Unexpected bytes at {data.RESET_FUNC_ADDR:#010x}: {cur.hex(' ')} - not writing")

    # 1) debug cam -> that player (once, via the regular teleport)
    x, y, z = data.VEC3_BE.unpack(bytes(mem.Get(pid, data.skater_addr(index), 12)))
    _write_teleport(state, x, y, z)

    # 2) reset them: 4-byte function patch for RESET_RESTORE_DELAY seconds
    patched = False
    try:
        mem.Set(pid, data.RESET_FUNC_ADDR, data.li_r9(index))
        patched = True
        for a in data.RESET_EXTRA_ADDRS:
            mem.Set(pid, a, bytes([data.RESET_EXTRA_VALUE]))
        time.sleep(data.RESET_RESTORE_DELAY)
    finally:
        if patched:
            last = None
            for _ in range(3):
                try:
                    mem.Set(pid, data.RESET_FUNC_ADDR, data.RESET_FUNC_ORIG)
                    last = None
                    break
                except Exception as e:
                    last = e
                    time.sleep(0.5)
            if last is not None:
                raise RuntimeError(f"Reset ran but restoring the original bytes failed: {last}")
    return x, y, z


def _build_players(parent_tab, win, state):
    signals = _PlayersSignals(win)

    outer = QVBoxLayout(parent_tab)
    outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    outer.setContentsMargins(0, 20, 0, 0)
    outer.setSpacing(12)

    columns = QWidget(parent_tab)
    columns.setStyleSheet("background: transparent;")
    columns_layout = QHBoxLayout(columns)
    columns_layout.setContentsMargins(0, 0, 0, 0)
    columns_layout.setSpacing(16)
    columns_layout.setAlignment(Qt.AlignTop)
    outer.addWidget(columns, alignment=Qt.AlignHCenter)

    # -- Player list ------------------------------------------------------
    players_group = MetroGroupBox(columns, title="Players")
    players_group.setFixedWidth(490)
    columns_layout.addWidget(players_group, alignment=Qt.AlignTop)

    refresh_btn = MetroButton(players_group, text="REFRESH LIST", width=458, height=32)
    players_group.add(refresh_btn)

    name_labels = []
    name_styles = []      # each label's normal stylesheet, restored when it's not "you"
    teleport_btns = []
    reset_btns = []
    for i in range(data.NUM_SKATERS):
        row = QWidget(players_group)
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        slot_lbl = MetroLabel(row, text=f"Player {i + 1}")
        slot_lbl.setFixedWidth(60)
        name_lbl = MetroLabel(row, text="-")
        # Actions sit to the RIGHT of the name. Future per-player buttons go
        # in this same row, after the Teleport button.
        tp_btn = MetroButton(row, text="Teleport", width=90, height=28)
        tp_btn.setEnabled(False)
        reset_btn = MetroButton(row, text="Reset", width=90, height=28)
        reset_btn.setEnabled(False)

        row_layout.addWidget(slot_lbl)
        row_layout.addWidget(name_lbl, 1)
        row_layout.addWidget(tp_btn)
        row_layout.addWidget(reset_btn)
        players_group.add(row)
        name_labels.append(name_lbl)
        name_styles.append(name_lbl.styleSheet())
        teleport_btns.append(tp_btn)
        reset_btns.append(reset_btn)

    # -- Custom Coordinates --------------------------------------------------
    custom_group = MetroGroupBox(columns, title="Custom Coordinates")
    custom_group.setFixedWidth(300)
    columns_layout.addWidget(custom_group, alignment=Qt.AlignTop)

    coord_row = QWidget(custom_group)
    coord_row.setStyleSheet("background: transparent;")
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

    status_lbl = MetroLabel(parent_tab, text="Press REFRESH LIST to load the lobby's players.")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    # A word-wrapped label with no fixed width, centred in a layout, sizes
    # itself to its text and clips longer messages. Give it the same width as
    # the two columns above it (490 + 16 spacing + 300) so it wraps there and
    # the layout reserves the right height, plus room for at least 2 lines.
    status_lbl.setFixedWidth(490 + 16 + 300)
    status_lbl.setMinimumHeight(status_lbl.fontMetrics().lineSpacing() * 2 + 6)
    outer.addWidget(status_lbl, alignment=Qt.AlignHCenter)

    # -- Refresh (manual only - no timer) ----------------------------------
    def do_refresh():
        if not state.is_ready():
            signals.names.emit(False, "Connect and attach first.", [None] * data.NUM_SKATERS, True, -1)
            return
        try:
            raw = state.ps3.Process.Memory.Get(state.pid, data.PLAYER_NAME_BASE, data.PLAYER_LIST_READ_LEN)
            names, online = data.parse_player_names(raw)
            local = -1
            if online:
                try:
                    local = state.ps3.Process.Memory.Get(state.pid, data.LOCAL_PLAYER_INDEX_ADDR, 1)[0]
                    if local >= data.NUM_SKATERS:
                        local = -1   # not a valid slot (game not in a lobby yet)
                except Exception:
                    pass
            if not online:
                msg = "Names can't be read yet - go into an online game, then refresh."
            else:
                msg = f"{sum(n is not None for n in names)}/{data.NUM_SKATERS} players in lobby."
            signals.names.emit(True, msg, names, online, local)
        except Exception as e:
            signals.names.emit(False, f"Read failed: {e}", [None] * data.NUM_SKATERS, True, -1)

    def on_refresh_clicked():
        refresh_btn.setEnabled(False)
        status_lbl.setText("Refreshing...")
        threading.Thread(target=do_refresh, daemon=True).start()

    def on_names(ok, msg, names, online, local):
        refresh_btn.setEnabled(True)
        for i, n in enumerate(names):
            text = n if n is not None else "N/A"
            is_you = n is not None and i == local
            if is_you:
                text += "  (YOU)"
            name_labels[i].setText(text)
            # you = blue name, everyone else = the theme's normal text color
            name_labels[i].setStyleSheet(YOU_STYLE if is_you else name_styles[i])
            usable = ok and online and n is not None
            teleport_btns[i].setEnabled(usable)
            reset_btns[i].setEnabled(usable)
        status_lbl.setText(msg)

    refresh_btn.clicked.connect(on_refresh_clicked)
    signals.names.connect(on_names)

    # -- Teleport to a listed player ---------------------------------------
    def do_teleport_to_skater(index, name):
        if not state.is_ready():
            signals.result.emit(False, "Connect and attach first.")
            return
        try:
            raw = state.ps3.Process.Memory.Get(state.pid, data.skater_addr(index), 12)
            x, y, z = data.VEC3_BE.unpack(bytes(raw))
            _write_teleport(state, x, y, z)
            signals.result.emit(True, f"Teleported to {name} ({x:.2f}, {y:.2f}, {z:.2f})")
        except Exception as e:
            signals.result.emit(False, str(e))

    def make_skater_handler(index):
        def handler():
            status_lbl.setText("Teleporting...")
            # read the name here on the GUI thread, never from the worker
            threading.Thread(target=do_teleport_to_skater,
                             args=(index, name_labels[index].text()), daemon=True).start()
        return handler

    for i, btn in enumerate(teleport_btns):
        btn.clicked.connect(make_skater_handler(i))

    # -- Reset a listed player (RTM), then send the debug cam to them -------
    def do_reset(index, name):
        try:
            if not state.is_ready():
                signals.reset_done.emit(False, "Connect and attach first.")
                return
            x, y, z = _reset_player(state, index)
            signals.reset_done.emit(True, f"Debug cam sent to ({x:.2f}, {y:.2f}, {z:.2f}) and reset {name}.")
        except Exception as e:
            signals.reset_done.emit(False, str(e))
        finally:
            _reset_lock.release()

    def make_reset_handler(index):
        def handler():
            if not _reset_lock.acquire(blocking=False):
                status_lbl.setText("A reset is already running...")
                return
            for b in reset_btns:
                b.setEnabled(False)
            status_lbl.setText(f"Resetting Player {index + 1} (takes about {data.RESET_RESTORE_DELAY:g}s)...")
            # read the name here on the GUI thread, never from the worker
            name = name_labels[index].text().replace("  (YOU)", "")
            threading.Thread(target=do_reset, args=(index, name), daemon=True).start()
        return handler

    for i, btn in enumerate(reset_btns):
        btn.clicked.connect(make_reset_handler(i))

    def on_reset_done(ok, msg):
        # buttons come back only for slots that still have a name
        for i, b in enumerate(reset_btns):
            b.setEnabled(name_labels[i].text() not in ("-", "N/A"))
        status_lbl.setText(msg)

    signals.reset_done.connect(on_reset_done)

    # -- Custom coordinates ---------------------------------------------------
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
    signals.result.connect(lambda ok, msg: status_lbl.setText(msg))

    return {"group_players": players_group, "group_custom": custom_group}
