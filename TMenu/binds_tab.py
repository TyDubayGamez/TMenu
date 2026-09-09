import math
import threading

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QFileDialog

from TsUI_qt import MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroDropdown
from app_paths import export_dir, export_save_path

from binds_data import BIND_GROUPS, get_item

CONTENT_WIDTH = 380


class _StatusBridge(QObject):
    fire = Signal(str)


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()


def _format_value(value) -> str:
    return f"{value:g}"


def build(parent_tab, win, state, runtime):
    layout = QVBoxLayout(parent_tab)
    layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
    layout.setContentsMargins(0, 20, 0, 0)

    group = MetroGroupBox(parent_tab, title="Keyboard Binds")
    group.setFixedWidth(CONTENT_WIDTH + 40)
    layout.addWidget(group, alignment=Qt.AlignHCenter)

    status_lbl = MetroLabel(group, text="")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setWordWrap(True)

    # the actual memory read/write is a blocking network call, so fire
    # handlers run it on their own background thread and use this bridge
    # to send the resulting status text back to the GUI thread
    status_bridge = _StatusBridge(group)
    status_bridge.fire.connect(status_lbl.setText)

    def _fire_async(work):
        # runs work() on a background thread so firing a bind never blocks the GUI
        def worker():
            try:
                msg = work()
            except Exception as e:
                msg = str(e)
            status_bridge.fire.emit(msg)
        threading.Thread(target=worker, daemon=True).start()

    # category / action dropdowns
    category_dd = MetroDropdown(group, items=[g["label"] for g in BIND_GROUPS], width=CONTENT_WIDTH)
    group.add(category_dd)

    action_dd = MetroDropdown(group, items=[], width=CONTENT_WIDTH)
    group.add(action_dd)

    content_holder = QWidget(group)
    content_holder.setStyleSheet("background: transparent;")
    content_layout = QVBoxLayout(content_holder)
    content_layout.setContentsMargins(0, 8, 0, 0)
    content_layout.setSpacing(8)
    group.add(content_holder)

    group.add(status_lbl)

    # shared fire-registration helpers

    def make_toggle_fire_handler(item):
        def _on_fire():
            def work():
                ok, msg = item["fire"](state)
                return msg
            _fire_async(work)
        return _on_fire

    def make_value_fire_handler(item, value):
        def _on_fire():
            def work():
                if not state.is_ready():
                    return "Connect and attach first."
                try:
                    default = item.get("default")
                    target = value
                    # pressing the hotkey again while already at `value`
                    # resets to the field's default instead of rewriting it
                    if default is not None and "get" in item:
                        current = item["get"](state)
                        if math.isclose(current, value, rel_tol=1e-4, abs_tol=1e-4):
                            target = default
                    item["set"](state, target)
                    if target == default:
                        return f"{item['label']} reset to default ({_format_value(target)})."
                    return f"{item['label']} set to {_format_value(target)}."
                except Exception as e:
                    return str(e)
            _fire_async(work)
        return _on_fire

    def register_saved_binds():
        # registers every saved keyboard bind with the router - called at
        # build time, and again after IMPORT since that replaces the config
        for action_id, hotkey in runtime.config.toggle_binds.items():
            group_key, _, item_key = action_id.partition(":")
            _grp, item = get_item(group_key, item_key)
            if item is not None:
                runtime.keyboard_router.set_bind(action_id, hotkey, make_toggle_fire_handler(item))

        for action_id, rows in runtime.config.value_binds.items():
            group_key, _, item_key = action_id.partition(":")
            _grp, item = get_item(group_key, item_key)
            if item is None:
                continue
            for row in rows:
                router_id = f"{action_id}:value:{row['hotkey']}"
                runtime.keyboard_router.set_bind(
                    router_id, row["hotkey"], make_value_fire_handler(item, row["value"])
                )

    # toggle-kind content

    def build_toggle_content(group_key, item_key, item):
        action_id = f"{group_key}:{item_key}"

        row = QWidget(content_holder)
        row.setStyleSheet("background: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        set_btn = MetroButton(row, text="Set Bind", width=250, height=32)
        clear_btn = MetroButton(row, text="Clear", width=100, height=32)
        row_layout.addWidget(set_btn)
        row_layout.addWidget(clear_btn)
        content_layout.addWidget(row)

        def refresh_label():
            hotkey = runtime.config.toggle_binds.get(action_id)
            set_btn.setText(hotkey if hotkey else "Set Bind")

        def on_set_clicked():
            set_btn.setEnabled(False)
            set_btn.setText("Press a key...")

            def on_captured(hotkey):
                set_btn.setEnabled(True)
                if not hotkey:
                    status_lbl.setText("Capture cancelled.")
                    refresh_label()
                    return
                runtime.config.toggle_binds[action_id] = hotkey
                runtime.config.save()
                runtime.keyboard_router.set_bind(action_id, hotkey, make_toggle_fire_handler(item))
                refresh_label()
                status_lbl.setText(f"{item['label']} bound to {hotkey}.")

            runtime.keyboard_router.capture_next_key(on_captured)

        def on_clear_clicked():
            runtime.config.toggle_binds.pop(action_id, None)
            runtime.config.save()
            runtime.keyboard_router.clear_bind(action_id)
            refresh_label()
            status_lbl.setText(f"{item['label']} bind cleared.")

        set_btn.clicked.connect(on_set_clicked)
        clear_btn.clicked.connect(on_clear_clicked)
        refresh_label()

    # value-kind content

    def build_value_content(group_key, item_key, item):
        action_id = f"{group_key}:{item_key}"
        default = item.get("default")

        default_lbl = MetroLabel(
            content_holder,
            text=(f"Default: {_format_value(default)}  (a value hotkey fires again -> resets to this)"
                  if default is not None else "No known default - value hotkeys never reset."),
        )
        default_lbl.setAlignment(Qt.AlignCenter)
        default_lbl.setWordWrap(True)
        content_layout.addWidget(default_lbl)

        existing_holder = QWidget(content_holder)
        existing_holder.setStyleSheet("background: transparent;")
        existing_layout = QVBoxLayout(existing_holder)
        existing_layout.setContentsMargins(0, 0, 0, 0)
        existing_layout.setSpacing(4)
        content_layout.addWidget(existing_holder)

        def entry():
            return runtime.config.value_binds.setdefault(action_id, [])

        def refresh_existing():
            _clear_layout(existing_layout)
            rows = entry()
            if not rows:
                empty_lbl = MetroLabel(existing_holder, text="No value binds yet.")
                empty_lbl.setAlignment(Qt.AlignCenter)
                existing_layout.addWidget(empty_lbl)
                return
            for row in list(rows):
                row_widget = QWidget(existing_holder)
                row_widget.setStyleSheet("background: transparent;")
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(8)

                lbl = MetroLabel(row_widget, text=f"{_format_value(row['value'])}  ->  {row['hotkey']}")
                remove_btn = MetroButton(row_widget, text="Remove", width=90, height=26)
                row_layout.addWidget(lbl)
                row_layout.addStretch(1)
                row_layout.addWidget(remove_btn)
                existing_layout.addWidget(row_widget)

                def on_remove(_checked=False, row=row):
                    router_id = f"{action_id}:value:{row['hotkey']}"
                    runtime.keyboard_router.clear_bind(router_id)
                    rows[:] = [r for r in rows if r is not row]
                    runtime.config.save()
                    refresh_existing()
                    status_lbl.setText(f"Removed {item['label']} bind {row['hotkey']}.")

                remove_btn.clicked.connect(on_remove)

        # add a new value bind
        add_row = QWidget(content_holder)
        add_row.setStyleSheet("background: transparent;")
        add_row_layout = QHBoxLayout(add_row)
        add_row_layout.setContentsMargins(0, 0, 0, 0)
        add_row_layout.setSpacing(8)

        value_box = MetroTextBox(add_row, width=200, height=30)
        value_box.setPlaceholderText("value")
        add_btn = MetroButton(add_row, text="Add Bind", width=150, height=30)
        add_row_layout.addWidget(value_box)
        add_row_layout.addWidget(add_btn)
        content_layout.addWidget(add_row)

        def on_add_clicked():
            text = value_box.text().strip()
            if not text:
                status_lbl.setText(f"{item['label']} needs a value to bind.")
                return
            try:
                value = float(text)
            except ValueError:
                status_lbl.setText(f"{item['label']} bind value must be a number.")
                return

            add_btn.setEnabled(False)
            add_btn.setText("Press a key...")

            def on_captured(hotkey):
                add_btn.setEnabled(True)
                add_btn.setText("Add Bind")
                if not hotkey:
                    status_lbl.setText("Capture cancelled.")
                    return
                rows = entry()
                rows[:] = [r for r in rows if r["hotkey"] != hotkey]  # a re-used hotkey replaces, not stacks
                rows.append({"hotkey": hotkey, "value": value})
                runtime.config.save()
                router_id = f"{action_id}:value:{hotkey}"
                runtime.keyboard_router.set_bind(router_id, hotkey, make_value_fire_handler(item, value))
                value_box.clear()
                refresh_existing()
                status_lbl.setText(f"{item['label']} bound to {hotkey} -> {_format_value(value)}.")

            runtime.keyboard_router.capture_next_key(on_captured)

        add_btn.clicked.connect(on_add_clicked)

        refresh_existing()

    # wiring the two dropdowns together

    def rebuild_content():
        _clear_layout(content_layout)
        group_idx = category_dd.currentIndex()
        if group_idx < 0 or group_idx >= len(BIND_GROUPS):
            return
        bind_group = BIND_GROUPS[group_idx]
        item_keys = list(bind_group["items"].keys())
        action_idx = action_dd.currentIndex()
        if action_idx < 0 or action_idx >= len(item_keys):
            return
        item_key = item_keys[action_idx]
        item = bind_group["items"][item_key]

        if bind_group["kind"] == "toggle":
            build_toggle_content(bind_group["key"], item_key, item)
        else:
            build_value_content(bind_group["key"], item_key, item)

    def on_category_changed(_index):
        bind_group = BIND_GROUPS[category_dd.currentIndex()]
        action_dd.blockSignals(True)
        action_dd.clear()
        action_dd.addItems([it["label"] for it in bind_group["items"].values()])
        action_dd.blockSignals(False)
        rebuild_content()

    category_dd.currentIndexChanged.connect(on_category_changed)
    action_dd.currentIndexChanged.connect(rebuild_content)

    # Import/Export

    def do_export():
        path = export_save_path(
            group, "binds", "binds.json", "Export Binds", "Binds Config (*.json)"
        )
        if not path:
            return  # user cancelled the save dialog
        ok = runtime.config.export_to(path)
        status_lbl.setText("Binds exported." if ok else "Export failed.")

    def do_import():
        path, _ = QFileDialog.getOpenFileName(
            group, "Import Binds", export_dir("binds"), "Binds Config (*.json)"
        )
        if not path:
            return
        ok = runtime.config.import_from(path)
        if not ok:
            status_lbl.setText("Import failed.")
            return
        runtime.keyboard_router.clear_all()
        register_saved_binds()
        rebuild_content()
        status_lbl.setText("Binds imported.")

    io_row = QWidget(group)
    io_row.setStyleSheet("background: transparent;")
    io_row_layout = QHBoxLayout(io_row)
    io_row_layout.setContentsMargins(0, 0, 0, 0)
    io_row_layout.setSpacing(8)
    import_btn = MetroButton(io_row, text="IMPORT", width=(CONTENT_WIDTH - 8) // 2)
    export_btn = MetroButton(io_row, text="EXPORT", width=(CONTENT_WIDTH - 8) // 2)
    io_row_layout.addWidget(import_btn)
    io_row_layout.addWidget(export_btn)
    import_btn.clicked.connect(do_import)
    export_btn.clicked.connect(do_export)

    group.add(io_row)

    # initial state
    register_saved_binds()
    on_category_changed(0)
