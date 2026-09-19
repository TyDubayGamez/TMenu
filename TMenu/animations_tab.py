"""
animations_tab.py
==================
Builds the top-level ANIMATIONS tab: FLIP TRICKS (the animation replacer)
and CACHE (status + manual clear), same MetroTabControl-as-subtabs pattern
every other tab uses.

See animations_data.py's module docstring for how the AOB scan/cache
actually works - this file is just the UI on top of it: two dropdowns
("Trick To Replace" / "Set To"), SWAP to perform the replacement, GET to
read back which trick is currently sitting at the left dropdown's cached
address, and RESET / RESET ALL to restore original AOB bytes. No GET ALL -
not needed, per spec.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from TsUI_qt import (
    MetroButton, MetroLabel, MetroGroupBox, MetroTabControl,
    SearchableDropdown, labeled_row,
)
from gui_refresh import on_attach_refresh

import animations_data as data

SUBTAB_FONT = ("Segoe UI", 9)


def build(parent_tab, win, state):
    layout = QVBoxLayout(parent_tab)
    layout.setContentsMargins(0, 0, 0, 0)

    subtabs = MetroTabControl(
        parent_tab, width=750, height=350,
        bar_height=26, font=SUBTAB_FONT, spacing=14, left_margin=12,
    )
    layout.addWidget(subtabs)

    subtabs.add("FLIP TRICKS")
    subtabs.add("CACHE")

    _build_flip_tricks(subtabs.tab("FLIP TRICKS"), win, state)
    _build_cache(subtabs.tab("CACHE"), win, state)

    # Boot scan: fires immediately if already attached, and again on every
    # future attach - see animations_data.ensure_cache's docstring for what
    # "boot" means here (cache file missing -> rescan, otherwise just load).
    on_attach_refresh(state, subtabs, lambda: data.ensure_cache(state))

    return subtabs


# ============================================================================
# FLIP TRICKS - the animation replacer
# ============================================================================

FIELD_WIDTH = 300


def _build_flip_tricks(tab, win, state):
    tricks = data.flip_tricks()                # [(name, aob_bytes), ...] + NULL, for GET's match pool
    real_tricks = [t for t in tricks if t[0] != data.NULL_LABEL]
    by_name = dict(tricks)

    # "Trick To Replace" only ever makes sense as a real, findable trick -
    # NULL has no cached address of its own, it's only ever a value you
    # SET something else to. "Set To" gets NULL appended so a trick can be
    # blanked out on purpose.
    from_entries = [(name, name) for name, _ in real_tricks]
    to_entries = [(name, name) for name, _ in tricks]

    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)
    layout.setSpacing(12)

    group = MetroGroupBox(tab, title="Animation Replacer")
    group.setFixedWidth(680)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    row = QWidget(group)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(24)

    from_dd = SearchableDropdown(row, from_entries, placeholder="Search trick...", width=FIELD_WIDTH)
    to_dd = SearchableDropdown(row, to_entries, placeholder="Search trick or NULL...", width=FIELD_WIDTH)

    row_layout.addWidget(labeled_row(row, "Trick To Replace", from_dd))
    row_layout.addWidget(labeled_row(row, "Set To", to_dd))
    group.add(row)

    swap_btn = MetroButton(group, text="SWAP", width=300, height=34)
    group.add(swap_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    btn_row = QWidget(group)
    btn_row_layout = QHBoxLayout(btn_row)
    btn_row_layout.setContentsMargins(0, 4, 0, 0)
    btn_row_layout.setSpacing(10)
    reset_all_btn = MetroButton(btn_row, text="RESET ALL", width=210, height=32)
    get_btn = MetroButton(btn_row, text="GET", width=210, height=32)
    reset_btn = MetroButton(btn_row, text="RESET", width=210, height=32)
    btn_row_layout.addWidget(reset_all_btn)
    btn_row_layout.addWidget(get_btn)
    btn_row_layout.addWidget(reset_btn)
    group.add(btn_row)

    def _set_dropdown(dd, name):
        """set_selected_key only matches against whatever's currently
        showing (SearchableDropdown filters its list by its own search
        box) - clear the search first so a match outside the current
        filter still gets picked."""
        if not dd.set_selected_key(name):
            dd.search_box.clear()
            dd.set_selected_key(name)

    def _addr_for(name):
        addr = data.current_cache().get(name)
        if addr is None:
            status_lbl.setText(
                f'"{name}" wasn\'t found in memory. Reattach to rescan, or '
                f"clear the cache under ANIMATIONS > CACHE first."
            )
        return addr

    def on_swap():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        from_name = from_dd.selected_key()
        to_name = to_dd.selected_key()
        if not from_name or not to_name:
            status_lbl.setText("Pick a trick on both sides first.")
            return
        addr = _addr_for(from_name)
        if addr is None:
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, addr, by_name[to_name])
            status_lbl.setText(f"{from_name} now plays {to_name}.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_get():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        from_name = from_dd.selected_key()
        if not from_name:
            status_lbl.setText("Pick a trick on the left first.")
            return
        addr = _addr_for(from_name)
        if addr is None:
            return
        try:
            current = bytes(state.ps3.Process.Memory.Get(state.pid, addr, len(by_name[from_name])))
        except Exception as e:
            status_lbl.setText(str(e))
            return
        match = next((n for n, b in tricks if b == current), None)
        if match is None:
            status_lbl.setText(f"{from_name} is currently something custom/unrecognized.")
            return
        _set_dropdown(to_dd, match)
        if match == data.NULL_LABEL:
            status_lbl.setText(f"{from_name} is currently NULL (blanked out).")
        else:
            status_lbl.setText(f"{from_name} currently plays {match}.")

    def on_reset():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        from_name = from_dd.selected_key()
        if not from_name:
            status_lbl.setText("Pick a trick on the left first.")
            return
        addr = _addr_for(from_name)
        if addr is None:
            return
        try:
            state.ps3.Process.Memory.Set(state.pid, addr, by_name[from_name])
            status_lbl.setText(f"{from_name} reset to its original animation.")
        except Exception as e:
            status_lbl.setText(str(e))

    def on_reset_all():
        if not state.is_ready():
            status_lbl.setText("Connect and attach first.")
            return
        cache = data.current_cache()
        ok, failed = 0, 0
        for name, aob in real_tricks:
            addr = cache.get(name)
            if addr is None:
                continue
            try:
                state.ps3.Process.Memory.Set(state.pid, addr, aob)
                ok += 1
            except Exception:
                failed += 1
        status_lbl.setText(f"Reset {ok} trick(s)." + (f" {failed} failed." if failed else ""))

    swap_btn.clicked.connect(on_swap)
    get_btn.clicked.connect(on_get)
    reset_btn.clicked.connect(on_reset)
    reset_all_btn.clicked.connect(on_reset_all)

    return group


# ============================================================================
# CACHE
# ============================================================================

def _build_cache(tab, win, state):
    layout = QVBoxLayout(tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(tab, title="AOB Cache")
    group.setFixedWidth(320)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    info_lbl = MetroLabel(group, text="")
    info_lbl.setAlignment(Qt.AlignCenter)
    info_lbl.setWordWrap(True)
    group.add(info_lbl)

    clear_btn = MetroButton(group, text="CLEAR CACHE", width=280, height=34)
    group.add(clear_btn)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)
    group.add(status_lbl)

    def _refresh_info():
        total = len(data.all_trick_patterns())
        found = len(data.current_cache())
        on_disk = os.path.isfile(data.cache_file_path())
        info_lbl.setText(f"{found}/{total} tricks cached ({'on disk' if on_disk else 'not built yet'}).")

    def on_clear():
        data.clear_cache()
        status_lbl.setText("Cache cleared. It will rescan the next time the tool attaches.")
        _refresh_info()

    clear_btn.clicked.connect(on_clear)

    on_attach_refresh(state, group, _refresh_info)

    return group
