"""
color_picker.py
================
A reusable RGB color-picker popup window, styled to match TsUI (built on
top of MetroForm / Metro* widgets from TsUI_qt.py) but kept in its own
module so any tab that deals in Skate 3's float RGB channels can pop it up
without duplicating the UI. Used by EDIT SKATER's Colors group and PARK's
RGB group.

--- The Skate 3 color model ------------------------------------------------

Skate 3 stores each R/G/B channel as a float where 0.0 = a byte value of 0
and 1.0 = a byte value of 255 (so byte 10 == 10/255 == 0.0392...). This tool
also lets the value go past 1.0 (or below 0.0) since the game doesn't
actually clamp there - that's the "brightness multiplier" idea in this
picker: 1.0 = a channel exactly at its normal 0-255 byte range, values above
1.0 push it brighter than a normal byte value can express, and the picker
exposes that as a single 0-30 multiplier that scales all three channels
together (not a separate multiplier per channel).

So this picker really has two independent controls:
  - a base COLOR, picked directly via an embedded color-picker widget (hue/
    saturation/value square, sliders, hex/RGB spin boxes, eyedropper - all
    of Qt's own color dialog, just living inline in this window instead of
    popping up as its own separate native dialog)
  - a single BRIGHTNESS multiplier (0-30 on the bar, unlimited if typed)
    that scales all three of that base color's channels by the same amount

final_channel = (base_color_channel / 255) * brightness

--- Reusable entry point ----------------------------------------------------

    from color_picker import open_color_picker

    def apply(r, g, b):
        boxes["RED"].setText(f"{r:.4f}")
        boxes["GREEN"].setText(f"{g:.4f}")
        boxes["BLUE"].setText(f"{b:.4f}")

    def on_pick_clicked():
        try:
            current = tuple(float(boxes[c].text().strip()) for c in ("RED", "GREEN", "BLUE"))
        except ValueError:
            current = (0.0, 0.0, 0.0)
        open_color_picker(win, current, apply, title="Skater Color Picker")

`win` is any already-built MetroForm (its .metro_style/.theme are reused so
the popup matches the parent window's active theme). `current` is whatever
is already sitting in the RGB boxes - the popup reads its starting color and
brightness back out of those three floats automatically, so reopening the
picker always starts from what's already filled in. Clicking OK calls
`on_accept(r, g, b)` with the new floats and closes the popup; clicking
CANCEL (or the window's own close button) just closes it without calling
anything, leaving the boxes exactly as they were.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QColorDialog

from TsUI_qt import (
    MetroForm, MetroButton, MetroLabel, MetroTextBox, MetroGroupBox, MetroSlider,
)

POPUP_SIZE = (460, 780)

BRIGHTNESS_MIN = 0.0
BRIGHTNESS_MAX = 30.0
BRIGHTNESS_SLIDER_SCALE = 100  # slider is int-only, so 0-30.00 becomes an int 0-3000


def _decompose(r, g, b):
    """
    Turn three raw float channels (as they're stored/typed in the RGB
    boxes) into (QColor base_color, brightness) so the picker can open
    already lined up with whatever's currently filled in.

    Brightness is taken as the largest of the three channels (clamped to
    non-negative) - the base color is then whatever's left after dividing
    that back out, so the brightest channel always maps back to a clean
    255-equivalent starting point in the color picker. From there the user
    is free to change the base color's own value/lightness too (the
    embedded picker doesn't pin that) - Brightness just multiplies whatever
    they land on.
    """
    peak = max(0.0, r, g, b)
    if peak <= 1e-6:
        return QColor(255, 255, 255), 0.0

    nr = max(0.0, min(1.0, r / peak))
    ng = max(0.0, min(1.0, g / peak))
    nb = max(0.0, min(1.0, b / peak))
    return QColor(round(nr * 255), round(ng * 255), round(nb * 255)), peak


def _recompose(color, brightness):
    """(base QColor, brightness) -> final (r, g, b) floats to write back."""
    return color.redF() * brightness, color.greenF() * brightness, color.blueF() * brightness


class RGBColorPickerDialog(MetroForm):
    """
    The popup itself. Prefer open_color_picker() below over constructing
    this directly - it handles wiring the accepted_rgb signal up to a plain
    callback, which is what every caller actually wants.
    """

    accepted_rgb = Signal(float, float, float)

    def __init__(self, parent, initial_rgb=(0.0, 0.0, 0.0), title="Color Picker",
                 style=None, theme=None):
        style = style or getattr(parent, "metro_style", None)
        theme = theme or getattr(parent, "theme", None)
        super().__init__(title, heading=title, size=POPUP_SIZE,
                          style=style, theme=theme, resizable=False, parent=parent)
        self.setWindowModality(Qt.ApplicationModal)

        initial_color, self._brightness = _decompose(*initial_rgb)

        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)

        # -- base color picker -----------------------------------------
        # This IS the color picker - Qt's own hue/sat/value square, the
        # vertical value slider, hex/RGB spin boxes, and eyedropper, all
        # embedded directly in this window instead of popping up separately.
        # NoButtons drops its own built-in OK/Cancel (this window has its
        # own at the bottom); DontUseNativeDialog + adding it straight into
        # a layout is what turns it from a top-level OS dialog (its own
        # window frame/title bar, system light/dark styling that doesn't
        # match the rest of this tool) into a plain embedded widget that
        # picks up this window's own dark styling below.
        color_group = MetroGroupBox(self.body, title="Color")
        layout.addWidget(color_group)

        self.color_dialog = QColorDialog(color_group)
        self.color_dialog.setWindowFlags(Qt.Widget)  # force embedded, not a top-level window
        self.color_dialog.setOption(QColorDialog.NoButtons, True)
        self.color_dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        self.color_dialog.setCurrentColor(initial_color)
        self.color_dialog.setStyleSheet(self._color_dialog_qss())
        color_group.add(self.color_dialog)

        # -- brightness multiplier ------------------------------------------
        brightness_group = MetroGroupBox(self.body, title="Brightness Multiplier")
        layout.addWidget(brightness_group)

        note = MetroLabel(
            brightness_group,
            text="Bar covers 0-30. Type a value in the box to go above 30 or below 0.",
        )
        note.setWordWrap(True)
        brightness_group.add(note)

        self.brightness_slider = MetroSlider(
            brightness_group,
            minimum=int(BRIGHTNESS_MIN * BRIGHTNESS_SLIDER_SCALE),
            maximum=int(BRIGHTNESS_MAX * BRIGHTNESS_SLIDER_SCALE),
            value=self._brightness_to_slider(self._brightness),
            width=400, height=22,
        )
        brightness_group.add(self.brightness_slider)

        self.brightness_box = MetroTextBox(brightness_group, width=400, height=26)
        self.brightness_box.setText(f"{self._brightness:.4f}")
        brightness_group.add(self.brightness_box)

        # -- result preview ---------------------------------------------
        result_group = MetroGroupBox(self.body, title="Result")
        layout.addWidget(result_group)

        self._result_readout = MetroLabel(result_group, text="")
        self._result_readout.setAlignment(Qt.AlignCenter)
        self._result_readout.setWordWrap(True)
        result_group.add(self._result_readout)

        # -- OK / CANCEL ------------------------------------------------
        btn_row = QWidget(self.body)
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(12)
        ok_btn = MetroButton(btn_row, text="OK", width=194, height=40,
                              style=self.metro_style, theme=self.theme)
        cancel_btn = MetroButton(btn_row, text="CANCEL", width=194, height=40,
                                  style=self.metro_style, theme=self.theme)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addWidget(btn_row)

        # -- wiring -------------------------------------------------------
        self.color_dialog.currentColorChanged.connect(self._on_color_changed)
        self.brightness_slider.valueChanged.connect(self._on_brightness_slider_changed)
        self.brightness_box.editingFinished.connect(self._on_brightness_box_edited)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.close)

        self._refresh()

    # -- styling -----------------------------------------------------------
    def _color_dialog_qss(self):
        """
        Qt's built-in color dialog defaults to the OS's own light/dark
        styling, which doesn't know anything about this tool's dark Metro
        theme - left alone, its labels/spin boxes render in whatever the
        system default text color is against whatever background this
        window happens to hand it, which is how you end up with unreadable
        black-on-black text. This forces every field, label, and button
        inside it over to the same theme colors as the rest of the popup.
        """
        theme = self.theme
        return f"""
            QColorDialog {{
                background-color: {theme['bg']};
            }}
            QWidget {{
                background-color: {theme['bg']};
                color: {theme['text']};
            }}
            QLabel {{
                color: {theme['text']};
                background: transparent;
            }}
            QLineEdit, QSpinBox {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                padding: 2px 4px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border: 1px solid {theme['border_strong']};
            }}
            QPushButton {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme['border_strong']};
                color: {theme['bg']};
            }}
        """

    def _brightness_to_slider(self, brightness):
        clamped = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, brightness))
        return int(round(clamped * BRIGHTNESS_SLIDER_SCALE))

    # -- event handlers -----------------------------------------------------
    def _on_color_changed(self, _color):
        self._refresh()

    def _on_brightness_slider_changed(self, value):
        self._brightness = value / BRIGHTNESS_SLIDER_SCALE
        self.brightness_box.setText(f"{self._brightness:.4f}")
        self._refresh()

    def _on_brightness_box_edited(self):
        text = self.brightness_box.text().strip()
        try:
            value = float(text)
        except ValueError:
            self.brightness_box.setText(f"{self._brightness:.4f}")
            return
        self._brightness = value
        # Slider only ever reflects 0-30 - a typed value outside that range
        # just pins the handle to whichever end it's past, without touching
        # the value actually stored in self._brightness.
        self.brightness_slider.setValue(self._brightness_to_slider(value))
        self._refresh()

    def _on_ok(self):
        r, g, b = _recompose(self.color_dialog.currentColor(), self._brightness)
        self.accepted_rgb.emit(r, g, b)
        self.close()

    # -- redraw -------------------------------------------------------------
    def _refresh(self):
        final_r, final_g, final_b = _recompose(self.color_dialog.currentColor(), self._brightness)
        over_range = any(v < 0 or v > 1.0 for v in (final_r, final_g, final_b))
        note = "  (past 0-255 range)" if over_range else ""
        self._result_readout.setText(
            f"R: {final_r:.4f}   G: {final_g:.4f}   B: {final_b:.4f}{note}"
        )


def open_color_picker(parent, initial_rgb, on_accept, title="Color Picker", style=None, theme=None):
    """
    Open the color picker popup.

    parent: the MetroForm (or any widget with .metro_style/.theme) the
        popup's look should match.
    initial_rgb: (r, g, b) tuple of the raw floats currently sitting in the
        caller's RGB boxes - the popup opens already lined up with these.
    on_accept: called as on_accept(r, g, b) with the new floats when the
        user clicks OK. Never called if they click CANCEL or close the
        window - the caller doesn't need to do anything in that case, the
        existing boxes are simply left untouched.

    Returns the dialog instance (rarely needed - it's already shown and
    wired up by the time this returns).
    """
    dlg = RGBColorPickerDialog(parent, initial_rgb=initial_rgb, title=title, style=style, theme=theme)
    dlg.accepted_rgb.connect(on_accept)
    dlg.show()
    return dlg
