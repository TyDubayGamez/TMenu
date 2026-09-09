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
    # turns raw r/g/b floats into (QColor base_color, brightness):
    # brightness is the largest channel, base color is what's left after
    # dividing that back out
    peak = max(0.0, r, g, b)
    if peak <= 1e-6:
        return QColor(255, 255, 255), 0.0

    nr = max(0.0, min(1.0, r / peak))
    ng = max(0.0, min(1.0, g / peak))
    nb = max(0.0, min(1.0, b / peak))
    return QColor(round(nr * 255), round(ng * 255), round(nb * 255)), peak


def _recompose(color, brightness):
    # (base QColor, brightness) -> final (r, g, b) floats to write back
    return color.redF() * brightness, color.greenF() * brightness, color.blueF() * brightness


class RGBColorPickerDialog(MetroForm):
    # prefer open_color_picker() below over constructing this directly
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

        # base color picker - Qt's own color dialog, embedded as a plain
        # widget instead of popping up as its own OS window
        color_group = MetroGroupBox(self.body, title="Color")
        layout.addWidget(color_group)

        self.color_dialog = QColorDialog(color_group)
        self.color_dialog.setWindowFlags(Qt.Widget)  # force embedded, not a top-level window
        self.color_dialog.setOption(QColorDialog.NoButtons, True)
        self.color_dialog.setOption(QColorDialog.DontUseNativeDialog, True)
        self.color_dialog.setCurrentColor(initial_color)
        self.color_dialog.setStyleSheet(self._color_dialog_qss())
        color_group.add(self.color_dialog)

        # brightness multiplier
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

        # result preview
        result_group = MetroGroupBox(self.body, title="Result")
        layout.addWidget(result_group)

        self._result_readout = MetroLabel(result_group, text="")
        self._result_readout.setAlignment(Qt.AlignCenter)
        self._result_readout.setWordWrap(True)
        result_group.add(self._result_readout)

        # OK / CANCEL
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

        # wiring
        self.color_dialog.currentColorChanged.connect(self._on_color_changed)
        self.brightness_slider.valueChanged.connect(self._on_brightness_slider_changed)
        self.brightness_box.editingFinished.connect(self._on_brightness_box_edited)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn.clicked.connect(self.close)

        self._refresh()

    # styling
    def _color_dialog_qss(self):
        # forces the color dialog's fields/labels/buttons to use this
        # tool's dark theme colors instead of the OS default styling
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

    # event handlers
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
        # slider only shows 0-30, a typed value outside that just pins the handle
        self.brightness_slider.setValue(self._brightness_to_slider(value))
        self._refresh()

    def _on_ok(self):
        r, g, b = _recompose(self.color_dialog.currentColor(), self._brightness)
        self.accepted_rgb.emit(r, g, b)
        self.close()

    # redraw
    def _refresh(self):
        final_r, final_g, final_b = _recompose(self.color_dialog.currentColor(), self._brightness)
        over_range = any(v < 0 or v > 1.0 for v in (final_r, final_g, final_b))
        note = "  (past 0-255 range)" if over_range else ""
        self._result_readout.setText(
            f"R: {final_r:.4f}   G: {final_g:.4f}   B: {final_b:.4f}{note}"
        )


def open_color_picker(parent, initial_rgb, on_accept, title="Color Picker", style=None, theme=None):
    # opens the color picker popup. initial_rgb is the (r, g, b) the popup
    # opens lined up with; on_accept(r, g, b) is called only if OK is clicked
    dlg = RGBColorPickerDialog(parent, initial_rgb=initial_rgb, title=title, style=style, theme=theme)
    dlg.accepted_rgb.connect(on_accept)
    dlg.show()
    return dlg
