"""
skaterp_import_dialog.py
========================
The popup shown after a skater.p has been picked in EDIT SKATER > RECIPES.

    SAVE SKATER   dropdown of the skaters found in the save
    TO SLOT       Skater 1-5 on the PS3
    IMPORT SELECTED   one save skater -> one slot
    IMPORT ALL        save skater N -> slot N, for every skater found

The dialog itself never touches the PS3. It builds a list of (slot, recipe)
pairs and hands it to `import_fn`, which does the writing (off the GUI thread)
and reports back through `show_result(ok, message)`.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from TsUI_qt import MetroForm, MetroGroupBox, MetroLabel, MetroButton, MetroDropdown

DIALOG_SIZE = (340, 440)
FIELD_W = 260


def _label(parent, text, wrap=True, center=True):
    lbl = MetroLabel(parent, text=text)
    lbl.setWordWrap(wrap)
    if center:
        lbl.setAlignment(Qt.AlignCenter)
    return lbl


class SkaterPImportDialog(MetroForm):

    def __init__(self, parent, sp, export_folder, default_slot, import_fn, slots=5):
        super().__init__("Import Skater.p", heading="Import Skater.p", size=DIALOG_SIZE,
                         style=getattr(parent, "metro_style", None),
                         theme=getattr(parent, "theme", None),
                         resizable=False, maximizable=False, parent=parent)
        self.setWindowModality(Qt.ApplicationModal)
        self._sp = sp
        self._import_fn = import_fn

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 6, 16, 14)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        n = len(sp.skaters)
        info = f"{sp.save_name}\n{n} skater{'s' if n != 1 else ''} found"
        layout.addWidget(_label(self.body, info))
        if export_folder:
            layout.addWidget(_label(self.body, "Recipes saved to:\n" + export_folder))

        # -- one skater -> one slot ------------------------------------
        one = MetroGroupBox(self.body, title="Import Skater")
        layout.addWidget(one)
        self.skater_dd = MetroDropdown(
            one, items=[f"Save skater {i}  ({r.assets} assets)" for i, r in enumerate(sp.skaters, 1)],
            width=FIELD_W)
        one.add(self.skater_dd)
        self.slot_dd = MetroDropdown(one, items=[f"To Skater {i}" for i in range(1, slots + 1)], width=FIELD_W)
        self.slot_dd.setCurrentIndex(max(0, min(slots - 1, default_slot - 1)))
        one.add(self.slot_dd)
        self.one_btn = MetroButton(one, text="IMPORT SELECTED", width=FIELD_W, height=30)
        one.add(self.one_btn)

        # -- everything -------------------------------------------------
        every = MetroGroupBox(self.body, title="Import All")
        layout.addWidget(every)
        self.all_btn = MetroButton(every, text=f"IMPORT ALL {n} TO SLOTS 1-{n}" if n > 1 else "IMPORT ALL",
                                   width=FIELD_W, height=30)
        every.add(self.all_btn)

        self.status = _label(self.body, "")
        layout.addWidget(self.status)

        self.one_btn.clicked.connect(self._on_one)
        self.all_btn.clicked.connect(self._on_all)

    # -- actions ---------------------------------------------------------

    def _on_one(self):
        recipe = self._sp.skaters[self.skater_dd.currentIndex()]
        slot = self.slot_dd.currentIndex() + 1
        self._start([(slot, recipe)])

    def _on_all(self):
        self._start([(i, r) for i, r in enumerate(self._sp.skaters, 1)])

    def _start(self, pairs):
        self.status.setText("Importing...")
        self._set_busy(True)
        if not self._import_fn(pairs):          # refused before starting (not connected, ...)
            self._set_busy(False)

    def _set_busy(self, busy):
        for w in (self.one_btn, self.all_btn):
            w.setEnabled(not busy)

    def show_result(self, ok, message):
        self.status.setText(message)
        self._set_busy(False)
