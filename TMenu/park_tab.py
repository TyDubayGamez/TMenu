"""
park_tab.py
===========
Builds the top-level PARK tab as its own row of subtabs, using the same
MetroTabControl-as-subtabs pattern edit_skater_tab.py / misc_tab.py use.
Right now it holds a single RGB subtab, converted from the standalone
"S3 Park RGB" C# tool.

PARK_RGB_BASE_ADDRESS is an 8-digit PS3 address, same style as the rest of
this codebase - the original C# tool just wrote it as a decimal ulong
(1088951392) with a hex comment (40E81460); this is that same value,
written as the hex literal instead so it reads the same way every other
address in this tool does. Nothing was stripped/converted - it was already
8 digits.

Grid math (unchanged from the C# tool): each of the 8x8 grid's cells is 16
bytes (12 bytes of R/G/B float data + 4 bytes padding/unused), and each row
is 8 cells wide (128 bytes), so:

    address = PARK_RGB_BASE_ADDRESS + (row_index * 128) + (col_index * 16)

where row_index/col_index are 0-based (Row 1/Column 1 -> index 0).
"""

import struct

from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QVBoxLayout, QGridLayout, QWidget, QMessageBox

from PySide6.QtWidgets import QHBoxLayout

from TsUI_qt import (
    MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown, MetroTabControl,
    MetroSwitch, MetroSlider, MetroColorStyle,
    ACTIVE_THEME, ACTIVE_STYLE,
)
from color_picker import open_color_picker
from gui_refresh import on_attach_refresh
from toggleables_data import VISUALS_TOGGLES
from toggleables_tab import register_synced_button, set_bold_everywhere

SUBTAB_FONT = ("Segoe UI", 9)

PARK_RGB_BASE_ADDRESS = 0x40E81460
PARK_RGB_ROW_STRIDE = 128
PARK_RGB_COL_STRIDE = 16
PARK_RGB_ROWS = 8
PARK_RGB_COLS = 8


def _wrap_label(label, width):
    """setFixedWidth() alone isn't reliable for a word-wrapped MetroLabel
    inside a MetroGroupBox/MetroTabControl - a subtab frame that hasn't
    been shown yet can get its label's height locked in from the
    unwrapped, single-line sizeHint, and it never gets corrected later.
    That's what was clipping the top and bottom lines of every info label
    on this tab (worst on Editor Border, which is the outer PARK tab's
    default-hidden-until-clicked subtab). Computing the wrapped height
    directly with QFontMetrics and fixing both width AND height sidesteps
    Qt's layout timing entirely instead of hoping a relayout happens at
    the right moment.
    """
    label.setFixedWidth(width)
    metrics = QFontMetrics(label.font())
    rect = metrics.boundingRect(QRect(0, 0, width, 10_000), Qt.TextWordWrap, label.text())
    label.setFixedHeight(rect.height() + 4)


SAVE_CRASH_WARNING = (
    "After saving, changing location (quitting to menu or loading a "
    "different park) will almost certainly freeze or crash the game. "
    "This is expected - your save itself is fine and will still load "
    "normally once you restart."
)


def _themed_warning_box(parent, title, text):
    """Same idea as _themed_info_box, styled with the RED palette instead
    of the app's active accent so a crash warning still reads as a
    warning even when the app's own theme/accent is something else
    (purple, teal, etc)."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    warn = MetroColorStyle.RED
    box.setStyleSheet(f"""
        QMessageBox {{
            background-color: {ACTIVE_THEME['bg']};
        }}
        QMessageBox QLabel {{
            color: {ACTIVE_THEME['text']};
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            background-color: {ACTIVE_THEME['field']};
            color: {ACTIVE_THEME['text']};
            border: 1px solid {warn['accent']};
            padding: 4px 16px;
            min-width: 60px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {warn['hover']};
            color: {ACTIVE_THEME['text']};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {warn['accent']};
        }}
    """)
    box.exec()


def _themed_info_box(parent, title, text):
    """QMessageBox.information, but styled with this app's own theme colors
    instead of relying on default/OS palette - the un-styled version could
    render with black (unreadable) text/buttons depending on the system
    theme."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStyleSheet(f"""
        QMessageBox {{
            background-color: {ACTIVE_THEME['bg']};
        }}
        QMessageBox QLabel {{
            color: {ACTIVE_THEME['text']};
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            background-color: {ACTIVE_THEME['field']};
            color: {ACTIVE_THEME['text']};
            border: 1px solid {ACTIVE_THEME['border']};
            padding: 4px 16px;
            min-width: 60px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {ACTIVE_STYLE['hover']};
            color: {ACTIVE_THEME['text']};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {ACTIVE_STYLE['accent']};
        }}
    """)
    box.exec()


def park_rgb_address(row_index: int, col_index: int) -> int:
    return PARK_RGB_BASE_ADDRESS + (row_index * PARK_RGB_ROW_STRIDE) + (col_index * PARK_RGB_COL_STRIDE)


# ---------------------------------------------------------------------------
# Editor Border - Park Editor's camera/collision border controls, converted
# from the standalone park_editor_tool.py. Two separate one-shot writes:
#
#   Disable Border        - do this once, BEFORE opening the park editor,
#                            while still sat in a normal park (not
#                            free-roam) - applying it from free-roam can
#                            crash the game when you later back out of the
#                            park editor.
#   Disable Camera Border - the actual park-editor toggle; click it fresh
#                            every time you open the park editor, not just
#                            once.
#
# No Black Screen is a third button here, but it's not a separate write of
# its own - it's the exact same TOGGLEABLES>VISUALS entry shown under the
# top-level VISUALS tab (toggleables_data.VISUALS_TOGGLES), reused as-is
# rather than duplicated. Reusing it (not copying its address/bytes) is what
# lets this button and the VISUALS one stay bold-in-sync with each other -
# see toggleables_tab.py's register_synced_button/set_bold_everywhere: on
# open, if either was somehow already on, both buttons go bold; toggling
# either one bolds/un-bolds both.
# ---------------------------------------------------------------------------
DISABLE_BORDER_ADDRESS = 0x018DE580
DISABLE_BORDER_PATTERN = bytes.fromhex("0E2442C8A8142C17")  # 8 bytes
DISABLE_BORDER_DATA = DISABLE_BORDER_PATTERN * 3  # 24 bytes total, pattern x3

DISABLE_CAMERA_BORDER_ADDRESS = 0x455FC9AA
DISABLE_CAMERA_BORDER_DATA = bytes([0x00])

# Overworld check - before every Disable Border write, the first 16 of its
# 24 bytes are read back and compared against these. Each entry is one
# normal (non-editable) map's own signature at that same address - Disable
# Border is only meant for custom parks, so if the 16 bytes currently there
# match ANY of these, the game is sat in one of these normal maps and the
# write is refused instead of going through.
NORMAL_MAP_SIGNATURES = {
    "Downtown": bytes.fromhex("4773016A41B2E05E4773016A41B2E05E"),
    "Industrial": bytes.fromhex("A8B1F47090679026A8B1F47090679026"),
    "University": bytes.fromhex("CB473E68A2EAFABACB473E68A2EAFABA"),
    "Skate.School": bytes.fromhex("2DC7AD2CB158A3D82DC7AD2CB158A3D8"),
    "Maloof Money Cup": bytes.fromhex("E35BB54793619839E35BB54793619839"),
    "Black Box": bytes.fromhex("03D1852F5F9C102B03D1852F5F9C102B"),
    "Maloof NYC": bytes.fromhex("FC482525912D5FB9FC482525912D5FB9"),
    "Danny's Hawaiian Dream": bytes.fromhex("AB0F2591D2EFCD44AB0F2591D2EFCD44"),
    "Sanitorium": bytes.fromhex("607AD0895698257D607AD0895698257D"),
    "Art Gallery": bytes.fromhex("FC94BB6AD3378A9CFC94BB6AD3378A9C"),
}


# ---------------------------------------------------------------------------
# Open World - converted from the standalone Skate 3 PS3 Park Tool (Park
# Editor / Object Dropper / Park Saving). First true subsub-tab in this app:
# a MetroTabControl nested inside a subtab's own frame, rather than the one
# level of subtabs every other tab in this codebase uses.
#
# NOTE: OW_BLOCK_A/B_ADDRESS below are the exact same addresses as
# DISABLE_BORDER_ADDRESS above (0x018DE580/588) - Enable Park Editor here and
# Disable Border on the EDITOR BORDER subtab both write that same 24-byte
# region. Kept as separate named constants (not shared/reused) so this
# section reads as a faithful, self-contained port of the standalone tool -
# but toggling one from either subtab affects the other's state too, since
# it's really one shared flag underneath. EDITOR BORDER's
# NORMAL_MAP_SIGNATURES safety check (refusing the write while sat in a real
# map instead of a custom slot) is intentionally NOT applied here, to keep
# this a faithful port - it could be pulled in here too if that turns out to
# help with this subtab's writes as well.
#
# Loop write names (AvoidCrash1/2, RemoveCeiling) are the original dev's own
# names from the real source, not made up for this port.
# ---------------------------------------------------------------------------

OW_INIT1_ADDRESS = 0x455F6B8F
OW_INIT2_ADDRESS = 0x455FB218
OW_BLOCK_A_ADDRESS = 0x018DE580
OW_BLOCK_B_ADDRESS = 0x018DE588
OW_BLOCK_ON = bytes.fromhex("0E2442C8A8142C170E2442C8A8142C17")   # 16 bytes
OW_BLOCK_OFF = bytes.fromhex("002442C8A8142C170E2442C8A8142C17")  # 16 bytes

# Park Editor active-loop writes
OW_LOOP_AVOIDCRASH1_ADDRESS = 0x455FB267
OW_LOOP_AVOIDCRASH1_DATA = bytes.fromhex("0130027D20")
OW_LOOP_AVOIDCRASH2_ADDRESS = 0x455FB2F6
OW_LOOP_AVOIDCRASH2_DATA = bytes.fromhex("B4E0")
OW_LOOP_REMOVECEILING_ADDRESS = 0x455FC781
OW_LOOP_REMOVECEILING_DATA = bytes.fromhex("375B10414A1CAC")
OW_LOOP4_ADDRESS = 0x455FC9AA
OW_LOOP4_DATA = bytes([0x00])
OW_LOOP5_INT_ADDRESS = 0x455FB264
OW_LOOP6_INT_ADDRESS = 0x455FC9E8
OW_LOOP7_INT_ADDRESS = 0x455FB260

# Object Dropper idle-loop writes (fires while Object Dropper is on and Park
# Editor is off - distinct addresses from the Park Editor loop above)
OW_DROPPER_IDLE1_ADDRESS = 0x455FC790
OW_DROPPER_IDLE2_ADDRESS = 0x455FC9A8

# Forced, not user-adjustable from this tab (unlike the standalone tool's
# spinbox) - real hardware over PS3MAPI, so this cycles ONE write per tick
# rather than the original PC tool's 30ms-apart burst. 500ms to match the
# standalone tool's own default write interval.
OW_WRITE_INTERVAL_MS = 500

# Cursor Speed, Merge Glitch, Snapping, P.E.C Zoom Out - same four controls
# as the standalone tool's Tab 1/Tab 2, ported over 1:1 (were missing from
# this subtab entirely; only the enable/saving buttons had been ported).
OW_TRACKBAR_ADDRESS = 0x455FC9F0
OW_SNAPPING_ADDRESS = 0x455FC760
OW_MERGE_GLITCH_ADDRESS = 0x300409F7
OW_PEC_ZOOM_ADDRESS = 0x30A2CB48
OW_PEC_ZOOM_ON_DATA = bytes([68, 121, 192, 0])


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("RGB")
    _build_rgb(subtabs.tab("RGB"), win, state)

    subtabs.add("EDITOR BORDER")
    _build_editor_border(subtabs.tab("EDITOR BORDER"), state)

    subtabs.add("OPEN WORLD")
    _build_open_world(subtabs.tab("OPEN WORLD"), win, state)

    return subtabs


def _build_open_world(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(0, 0, 0, 0)

    inner_tabs = MetroTabControl(
        tab, width=750, height=310,
        bar_height=30, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(inner_tabs)

    inner_tabs.add("PARK EDITOR")
    inner_tabs.add("OBJECT DROPPER")

    # Nested tab control - refit the window on inner-tab switches too, same
    # idea as app.py's _refit_on_switch for the outer tab bars.
    _original_inner_set = inner_tabs.set

    def _inner_set(name):
        _original_inner_set(name)
        win.fit_to_content()

    inner_tabs.set = _inner_set

    # Shared across both inner tabs: Park Editor and Object Dropper are
    # mutually exclusive, same rule the standalone tool enforced.
    # merge_glitch lives here (not local to the Park Editor subtab) because
    # on_tick below needs to see live whether it's checked.
    ow_state = {"park_editor": False, "object_dropper": False, "saving": False,
                "merge_glitch": False}
    cycle = {"park_editor_idx": 0, "dropper_idx": 0}

    park_editor_actions = [
        (OW_LOOP_AVOIDCRASH1_ADDRESS, OW_LOOP_AVOIDCRASH1_DATA),
        (OW_LOOP_AVOIDCRASH2_ADDRESS, OW_LOOP_AVOIDCRASH2_DATA),
        (OW_LOOP_REMOVECEILING_ADDRESS, OW_LOOP_REMOVECEILING_DATA),
        (OW_LOOP4_ADDRESS, OW_LOOP4_DATA),
        (OW_LOOP5_INT_ADDRESS, struct.pack(">i", 1)),
        (OW_LOOP6_INT_ADDRESS, struct.pack(">i", 1)),
        (OW_LOOP7_INT_ADDRESS, struct.pack(">i", 1)),
    ]
    dropper_actions = [
        (OW_INIT2_ADDRESS, bytes([0x00])),
        (OW_DROPPER_IDLE1_ADDRESS, bytes([0x00])),
        (OW_INIT1_ADDRESS, bytes([0x00])),
        (OW_DROPPER_IDLE2_ADDRESS, bytes([0x00])),
    ]

    timer = QTimer(win)
    timer.setInterval(OW_WRITE_INTERVAL_MS)

    def on_tick():
        if not state.is_ready():
            return
        try:
            if ow_state["park_editor"]:
                # Merge Glitch, while checked, rides along in the cycle as an
                # extra continuous write (matches the standalone tool's
                # actions.append((..., 1)) - it only writes 0x01 while the
                # checkbox is on; turning it off is a separate one-shot 0xFF
                # write, handled in _build_ow_park_editor).
                actions = park_editor_actions
                if ow_state["merge_glitch"]:
                    actions = park_editor_actions + [(OW_MERGE_GLITCH_ADDRESS, bytes([0x01]))]
                addr, data = actions[cycle["park_editor_idx"] % len(actions)]
                cycle["park_editor_idx"] += 1
                state.ps3.Process.Memory.Set(state.pid, addr, data)
            elif ow_state["object_dropper"]:
                addr, data = dropper_actions[cycle["dropper_idx"] % len(dropper_actions)]
                cycle["dropper_idx"] += 1
                state.ps3.Process.Memory.Set(state.pid, addr, data)
        except Exception:
            pass  # background tick - a one-off failure just gets retried next tick

    timer.timeout.connect(on_tick)
    timer.start()

    _build_ow_park_editor(inner_tabs.tab("PARK EDITOR"), state, ow_state)
    _build_ow_object_dropper(inner_tabs.tab("OBJECT DROPPER"), state, ow_state)

    return inner_tabs


def _build_ow_park_editor(tab, state, ow_state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Park Editor")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    info_lbl = MetroLabel(
        group,
        text="Enables the Park Editor's continuous anti-crash / ceiling-removal "
             "writes. Mutually exclusive with Object Dropper.",
    )
    _wrap_label(info_lbl, 240)
    # wrapped text gets clipped by whatever's below it
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setWordWrap(True)
    group.add(info_lbl)

    enable_btn = MetroButton(group, text="Enable Park Editor", width=240, height=32)
    group.add(enable_btn)

    saving_btn = MetroButton(group, text="Enable Park Saving", width=240, height=32)
    group.add(saving_btn)

    save_warning_lbl = MetroLabel(group, text=SAVE_CRASH_WARNING)
    save_warning_lbl.setStyleSheet(f"color: {MetroColorStyle.RED['accent']}; border: none; background: transparent;")
    save_warning_lbl.setWordWrap(True)
    save_warning_lbl.setAlignment(Qt.AlignCenter)
    _wrap_label(save_warning_lbl, 240)
    group.add(save_warning_lbl)

    speed_lbl = MetroLabel(group, text="Cursor Speed")
    speed_lbl.setAlignment(Qt.AlignCenter)
    group.add(speed_lbl)

    speed_value_lbl = MetroLabel(group, text="1")
    speed_value_lbl.setAlignment(Qt.AlignCenter)
    group.add(speed_value_lbl)

    speed_slider = MetroSlider(group, minimum=1, maximum=10, value=1, width=240)
    group.add(speed_slider)

    merge_row = QWidget(group)
    merge_row_layout = QHBoxLayout(merge_row)
    merge_row_layout.setContentsMargins(0, 0, 0, 0)
    merge_lbl = MetroLabel(merge_row, text="Merge Glitch")
    merge_switch = MetroSwitch(merge_row)
    merge_row_layout.addWidget(merge_lbl)
    merge_row_layout.addStretch(1)
    merge_row_layout.addWidget(merge_switch)
    group.add(merge_row)

    snap_row = QWidget(group)
    snap_row_layout = QHBoxLayout(snap_row)
    snap_row_layout.setContentsMargins(0, 0, 0, 0)
    snap_lbl = MetroLabel(snap_row, text="Snapping")
    snap_switch = MetroSwitch(snap_row)
    snap_row_layout.addWidget(snap_lbl)
    snap_row_layout.addStretch(1)
    snap_row_layout.addWidget(snap_switch)
    group.add(snap_row)

    pec_row = QWidget(group)
    pec_row_layout = QHBoxLayout(pec_row)
    pec_row_layout.setContentsMargins(0, 0, 0, 0)
    pec_lbl = MetroLabel(pec_row, text="P.E.C Zoom Out")
    pec_switch = MetroSwitch(pec_row)
    pec_row_layout.addWidget(pec_lbl)
    pec_row_layout.addStretch(1)
    pec_row_layout.addWidget(pec_switch)
    group.add(pec_row)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_enable_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        if ow_state["object_dropper"]:
            status_lbl.setText("Disable Object Dropper first.")
            return
        turning_on = not ow_state["park_editor"]
        try:
            if turning_on:
                state.ps3.Process.Memory.Set(state.pid, OW_INIT1_ADDRESS, bytes([0x00]))
                _themed_info_box(
                    tab, "Info",
                    "Click OK once you've went to object dropper and backed out!",
                )
                state.ps3.Process.Memory.Set(state.pid, OW_INIT2_ADDRESS, bytes([0x00]))
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_A_ADDRESS, OW_BLOCK_ON)
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_B_ADDRESS, OW_BLOCK_ON)
                enable_btn.setText("Disable Park Editor")
                status_lbl.setText("Park Editor enabled.")
            else:
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_A_ADDRESS, OW_BLOCK_OFF)
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_B_ADDRESS, OW_BLOCK_OFF)
                enable_btn.setText("Enable Park Editor")
                status_lbl.setText("Park Editor disabled.")
            ow_state["park_editor"] = turning_on
        except Exception as e:
            status_lbl.setText(str(e))

    def on_saving_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        turning_on = not ow_state["saving"]
        try:
            if turning_on:
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_A_ADDRESS, OW_BLOCK_ON)
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_B_ADDRESS, OW_BLOCK_ON)
                saving_btn.setText("Disable Park Saving")
                status_lbl.setText("Park Saving enabled.")
                _themed_warning_box(tab, "Heads up", SAVE_CRASH_WARNING)
            else:
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_A_ADDRESS, OW_BLOCK_OFF)
                state.ps3.Process.Memory.Set(state.pid, OW_BLOCK_B_ADDRESS, OW_BLOCK_OFF)
                saving_btn.setText("Enable Park Saving")
                status_lbl.setText("Park Saving disabled.")
            ow_state["saving"] = turning_on
        except Exception as e:
            status_lbl.setText(str(e))

    def on_speed_changed(value):
        speed_value_lbl.setText(str(value))
        if not state.is_ready():
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, OW_TRACKBAR_ADDRESS, struct.pack(">f", float(value)))
        except Exception as e:
            status_lbl.setText(str(e))

    def on_merge_glitch_toggled(checked):
        ow_state["merge_glitch"] = checked
        log_note = ""
        # Turning it ON needs no write here - the background tick above
        # picks up ow_state["merge_glitch"] and writes 0x01 continuously
        # on its own. Turning it OFF is the one place this needs an
        # explicit one-shot write (0xFF), same as the standalone tool.
        if not checked:
            if not state.is_ready():
                status_lbl.setText("Connect and attach first.")
                return
            try:
                state.ps3.Process.Memory.Set(state.pid, OW_MERGE_GLITCH_ADDRESS, bytes([0xFF]))
            except Exception as e:
                status_lbl.setText(str(e))

    def on_snap_toggled(checked):
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, OW_SNAPPING_ADDRESS, bytes([1 if checked else 0]))
        except Exception as e:
            status_lbl.setText(str(e))

    def on_pec_toggled(checked):
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            if checked:
                state.ps3.Process.Memory.Set(state.pid, OW_PEC_ZOOM_ADDRESS, OW_PEC_ZOOM_ON_DATA)
            else:
                state.ps3.Process.Memory.Set(state.pid, OW_PEC_ZOOM_ADDRESS, struct.pack(">f", 40.0))
        except Exception as e:
            status_lbl.setText(str(e))

    enable_btn.clicked.connect(on_enable_clicked)
    saving_btn.clicked.connect(on_saving_clicked)
    speed_slider.valueChanged.connect(on_speed_changed)
    merge_switch.toggled_on.connect(on_merge_glitch_toggled)
    snap_switch.toggled_on.connect(on_snap_toggled)
    pec_switch.toggled_on.connect(on_pec_toggled)


def _build_ow_object_dropper(tab, state, ow_state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Object Dropper")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    info_lbl = MetroLabel(
        group,
        text="Mutually exclusive with Park Editor. After enabling, go into "
             "Object Dropper in-game and back out once before using it.",
    )
    _wrap_label(info_lbl, 240)
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setWordWrap(True)
    group.add(info_lbl)

    enable_btn = MetroButton(group, text="Enable Object Dropper Editor", width=240, height=32)
    group.add(enable_btn)

    speed_lbl = MetroLabel(group, text="Cursor Speed")
    speed_lbl.setAlignment(Qt.AlignCenter)
    group.add(speed_lbl)

    speed_value_lbl = MetroLabel(group, text="1")
    speed_value_lbl.setAlignment(Qt.AlignCenter)
    group.add(speed_value_lbl)

    speed_slider = MetroSlider(group, minimum=1, maximum=10, value=1, width=240)
    group.add(speed_slider)

    snap_row = QWidget(group)
    snap_row_layout = QHBoxLayout(snap_row)
    snap_row_layout.setContentsMargins(0, 0, 0, 0)
    snap_lbl = MetroLabel(snap_row, text="Snapping")
    snap_switch = MetroSwitch(snap_row)
    snap_row_layout.addWidget(snap_lbl)
    snap_row_layout.addStretch(1)
    snap_row_layout.addWidget(snap_switch)
    group.add(snap_row)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_speed_changed(value):
        speed_value_lbl.setText(str(value))
        if not state.is_ready():
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, OW_TRACKBAR_ADDRESS, struct.pack(">f", float(value)))
        except Exception as e:
            status_lbl.setText(str(e))

    def on_snap_toggled(checked):
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, OW_SNAPPING_ADDRESS, bytes([1 if checked else 0]))
        except Exception as e:
            status_lbl.setText(str(e))

    speed_slider.valueChanged.connect(on_speed_changed)
    snap_switch.toggled_on.connect(on_snap_toggled)

    def on_enable_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        if ow_state["park_editor"]:
            status_lbl.setText("Disable Park Editor first.")
            return
        turning_on = not ow_state["object_dropper"]
        ow_state["object_dropper"] = turning_on
        if turning_on:
            enable_btn.setText("Disable Object Dropper Editor")
            _themed_info_box(
                tab, "Info",
                "Click OK once you've went to object dropper and backed out!",
            )
            status_lbl.setText("Object Dropper enabled.")
        else:
            enable_btn.setText("Enable Object Dropper Editor")
            status_lbl.setText("Object Dropper disabled.")

    enable_btn.clicked.connect(on_enable_clicked)


def _build_rgb(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Park RGB")
    group.setFixedWidth(250)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    row_lbl = MetroLabel(group, text="Row")
    row_lbl.setAlignment(Qt.AlignCenter)
    group.add(row_lbl)

    row_dd = MetroDropdown(group, items=[str(i) for i in range(1, PARK_RGB_ROWS + 1)], width=200)
    group.add(row_dd)

    col_lbl = MetroLabel(group, text="Col")
    col_lbl.setAlignment(Qt.AlignCenter)
    group.add(col_lbl)

    col_dd = MetroDropdown(group, items=[str(i) for i in range(1, PARK_RGB_COLS + 1)], width=200)
    group.add(col_dd)

    grid_holder = QWidget(group)
    grid_holder.setStyleSheet("background: transparent;")
    grid = QGridLayout(grid_holder)
    grid.setContentsMargins(0, 4, 0, 4)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    boxes = {}
    for grid_row, channel in enumerate(("RED", "GREEN", "BLUE")):
        lbl = MetroLabel(grid_holder, text=channel)
        box = MetroTextBox(grid_holder, width=90, height=26)
        box.setPlaceholderText("float")
        grid.addWidget(lbl, grid_row, 0, alignment=Qt.AlignLeft | Qt.AlignVCenter)
        grid.addWidget(box, grid_row, 1, alignment=Qt.AlignRight)
        boxes[channel] = box
    group.add(grid_holder)

    picker_btn = MetroButton(group, text="PICK COLOR", width=200)
    group.add(picker_btn)

    get_btn = MetroButton(group, text="GET RGB", width=200)
    group.add(get_btn)

    set_btn = MetroButton(group, text="SET RGB", width=200)
    group.add(set_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_picker_clicked():
        try:
            current = tuple(float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE"))
        except ValueError:
            current = (0.0, 0.0, 0.0)

        def apply_rgb(r, g, b):
            boxes["RED"].setText(f"{r:.4f}")
            boxes["GREEN"].setText(f"{g:.4f}")
            boxes["BLUE"].setText(f"{b:.4f}")

        open_color_picker(win, current, apply_rgb, title="Park RGB Color Picker")

    def on_get_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        row_index = int(row_dd.currentText()) - 1
        col_index = int(col_dd.currentText()) - 1

        try:
            addr = park_rgb_address(row_index, col_index)
            raw = bytes(state.ps3.Process.Memory.Get(state.pid, addr, 12))
            values = struct.unpack(">fff", raw)
            for channel, value in zip(("RED", "GREEN", "BLUE"), values):
                boxes[channel].setText(f"{value:.4f}")
            status_lbl.setText(f"Loaded RGB from R{row_index + 1} C{col_index + 1}.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_set_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return

        row_index = int(row_dd.currentText()) - 1
        col_index = int(col_dd.currentText()) - 1

        try:
            values = {c: float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE")}
        except ValueError:
            status_lbl.setText("RGB values must be numbers.")
            return

        try:
            addr = park_rgb_address(row_index, col_index)
            buf = b"".join(struct.pack(">f", values[c]) for c in ("RED", "GREEN", "BLUE"))
            state.ps3.Process.Memory.Set(state.pid, addr, buf)
            status_lbl.setText(f"Applied RGB to R{row_index + 1} C{col_index + 1}.")
        except Exception as e:
            status_lbl.setText(str(e))

    picker_btn.clicked.connect(on_picker_clicked)
    get_btn.clicked.connect(on_get_clicked)
    set_btn.clicked.connect(on_set_clicked)


def _build_editor_border(tab, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="Editor Border")
    group.setFixedWidth(280)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    info_lbl = MetroLabel(
        group,
        text="Click Disable Camera Border every time you open the park editor. "
             "Only click Disable Border while out of the editor - if you're "
             "already in the editor, click it then reopen the editor.",
    )
    _wrap_label(info_lbl, 240)
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setWordWrap(True)
    group.add(info_lbl)

    disable_border_btn = MetroButton(group, text="Disable Border", width=240, height=32)
    group.add(disable_border_btn)

    disable_camera_border_btn = MetroButton(group, text="Disable Camera Border", width=240, height=32)
    group.add(disable_camera_border_btn)

    no_black_screen_btn = MetroButton(group, text="No Black Screen", width=240, height=32)
    group.add(no_black_screen_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def on_disable_border_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            current = bytes(state.ps3.Process.Memory.Get(state.pid, DISABLE_BORDER_ADDRESS, 16))
            for map_name, signature in NORMAL_MAP_SIGNATURES.items():
                if current == signature:
                    status_lbl.setText(f"In {map_name} (a normal map) - Disable Border refused.")
                    return
            state.ps3.Process.Memory.Set(state.pid, DISABLE_BORDER_ADDRESS, DISABLE_BORDER_DATA)
            status_lbl.setText("Border disabled. You can open the park editor now.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_disable_camera_border_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, DISABLE_CAMERA_BORDER_ADDRESS, DISABLE_CAMERA_BORDER_DATA)
            status_lbl.setText("Camera border disabled.")
        except Exception as e:
            status_lbl.setText(str(e))

    # Reuses VISUALS_TOGGLES's "No Black Screen" writes directly (same
    # address/bytes, not a copy) so this button and the VISUALS>TOGGLEABLES
    # one are always reading/writing the exact same state.
    no_black_screen_writes = VISUALS_TOGGLES["No Black Screen"]["writes"]

    def _no_black_screen_is_on():
        first = no_black_screen_writes[0]
        current = bytes(state.ps3.Process.Memory.Get(state.pid, first["address"], len(first["on"])))
        return current == first["on"]

    def on_no_black_screen_clicked():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        try:
            turning_on = not _no_black_screen_is_on()
            for w in no_black_screen_writes:
                data = w["on"] if turning_on else w["off"]
                state.ps3.Process.Memory.Set(state.pid, w["address"], data)
            set_bold_everywhere("No Black Screen", turning_on)
            status_lbl.setText(f"No Black Screen {'ON' if turning_on else 'OFF'}.")
        except Exception as e:
            status_lbl.setText(str(e))

    disable_border_btn.clicked.connect(on_disable_border_clicked)
    disable_camera_border_btn.clicked.connect(on_disable_camera_border_clicked)
    no_black_screen_btn.clicked.connect(on_no_black_screen_clicked)

    register_synced_button("No Black Screen", no_black_screen_btn)

    def _refresh_no_black_screen_bold():
        # Silent, same "leave it as-is on a bad read" rule as
        # toggleables_tab.py's own refresh - covers the case where this
        # button is what's on-screen first and VISUALS>TOGGLEABLES hasn't
        # been built/attached-through yet.
        try:
            set_bold_everywhere("No Black Screen", _no_black_screen_is_on())
        except Exception:
            pass

    on_attach_refresh(state, group, _refresh_no_black_screen_bold)
