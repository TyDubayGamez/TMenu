"""
TsUI (Qt edition) - "MetroFramework for Python", rebuilt on PySide6.

Same idea as the customtkinter version, same names, same call shapes -
swap your import and most code keeps working. The move to Qt buys us three
things the tk version had to hand-roll:

 - QSS (Qt stylesheets) for real hover/pressed/checked states instead of
   manually swapping colors in Python.
 - A native title-on-border group box (QGroupBox already draws its title
   overlapping the top border - no more placing a label on top by hand).
 - QPropertyAnimation for a smoothly sliding tab underline and switch knob.

Install:
    pip install PySide6

Usage mirrors the tk version:

    from TsUI_qt import MetroForm, MetroButton, MetroGroupBox, MetroColorStyle

    app = MetroForm.app()                      # create the QApplication once
    win = MetroForm("My Tool", size=(750, 460), style=MetroColorStyle.PURPLE)

    box = MetroGroupBox(win.body, title="Connection")
    btn = MetroButton(box, text="CONNECT")
    box.add(btn)

    win.show()
    app.exec()

See the __main__ block at the bottom for a full reproduction of the
CONNECTION tab from the reference screenshot.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, Signal, QRect, QSize
from PySide6.QtGui import QFont, QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QLineEdit,
    QTextEdit, QGroupBox, QVBoxLayout, QHBoxLayout, QSizePolicy, QSizeGrip,
    QComboBox, QGridLayout, QLayout, QScrollArea, QSlider,
)


# ---------------------------------------------------------------------------
# Color / theme styles - identical values to the tk version
# ---------------------------------------------------------------------------

class MetroColorStyle:
    PURPLE = {"accent": "#7c4199", "hover": "#5a2f70"}
    RED = {"accent": "#C0392B", "hover": "#7B2A20"}
    BLUE = {"accent": "#1F6FEB", "hover": "#1857B8"}
    GREEN = {"accent": "#2E9E4F", "hover": "#237A3D"}
    ORANGE = {"accent": "#D97706", "hover": "#B36305"}
    TEAL = {"accent": "#0F9E9E", "hover": "#0C7A7A"}


class MetroThemeStyle:
    DARK = {
        "bg": "#111111",
        "panel": "#111111",
        "field": "#222222",
        "text": "#cccccc",
        "text_dim": "#aaaaaa",
        "border": "#444444",
        "border_strong": "#999999",
    }
    LIGHT = {
        "bg": "#FAFAFA",
        "panel": "#FFFFFF",
        "field": "#FFFFFF",
        "text": "#1a1a1a",
        "text_dim": "#6a6a6a",
        "border": "#B5B5B5",
        "border_strong": "#8a8a8a",
    }


FONT_TITLE = ("Segoe UI", 9)
FONT_LABEL = ("Segoe UI", 10)
FONT_BTN = ("Segoe UI", 8)
FONT_TAB = ("Segoe UI", 10)
FONT_GLYPH = ("Segoe UI", 10)
FONT_HEADING = ("Segoe UI", 20)

RADIUS = 0  # Metro/flat design: no rounded corners, anywhere


def _font(spec, bold=False):
    f = QFont(spec[0], spec[1])
    if bold or "Semibold" in spec[0]:
        f.setBold(True)
    return f


# ---------------------------------------------------------------------------
# Theme overrides - optional theme.json, same folder as this file
# ---------------------------------------------------------------------------
# Everything above this point (MetroColorStyle, MetroThemeStyle, the FONT_*
# tuples, RADIUS) is the hardcoded, always-available default set - nothing
# below ever edits those. Instead, every widget class further down reads
# from the ACTIVE_* copies below, which start out identical to the hardcoded
# defaults and then get selectively overwritten by theme.json if one exists
# next to this file. No theme.json (or one missing some keys, or one that's
# just broken/unreadable) means those particular pieces simply keep using
# the hardcoded defaults - there's no scenario where the app fails to start
# or loses its built-in look because of a bad or missing theme file.
#
# Fonts are read from whatever's installed on the user's machine - a
# "family" name is just handed to Qt and it resolves it locally, same as
# any other font selection. If you'd rather ship a specific font file with
# the tool (or point at one already sitting on disk) instead of relying on
# it being installed, a font entry can also give a "path" to a .ttf/.otf
# file; that file gets registered with Qt at load time and its family name
# is used automatically, no separate install step needed.

import json
import os

from PySide6.QtGui import QFontDatabase

from app_paths import base_dir

THEME_FILE = os.path.join(base_dir(), "theme.json")

_FONT_KEYS = {
    "title": FONT_TITLE,
    "label": FONT_LABEL,
    "button": FONT_BTN,
    "tab": FONT_TAB,
    "glyph": FONT_GLYPH,
    "heading": FONT_HEADING,
}

ACTIVE_STYLE = dict(MetroColorStyle.PURPLE)
ACTIVE_THEME = dict(MetroThemeStyle.DARK)
ACTIVE_RADIUS = RADIUS
ACTIVE_FONTS = dict(_FONT_KEYS)

_registered_font_files = {}  # path -> family name, so a repeated path isn't reloaded


def _register_font_file(path):
    """Load a .ttf/.otf from disk into Qt's font database, return its family name (or None)."""
    if path in _registered_font_files:
        return _registered_font_files[path]
    if not os.path.isfile(path):
        return None
    font_id = QFontDatabase.addApplicationFont(path)
    if font_id == -1:
        return None
    families = QFontDatabase.applicationFontFamilies(font_id)
    family = families[0] if families else None
    _registered_font_files[path] = family
    return family


def load_theme(path=None):
    """
    (Re)build ACTIVE_STYLE / ACTIVE_THEME / ACTIVE_FONTS / ACTIVE_RADIUS from
    theme.json. Always starts back from the hardcoded defaults first, so a
    key removed from the file (or the file removed entirely) correctly falls
    back rather than leaving a stale override from a previous load in place.

    Called once automatically at import time, below. Safe to call again by
    hand later (e.g. wiring up a "reload theme" button) if that's ever
    wanted - just re-create any widgets afterward, since QSS is baked in at
    construction time rather than read live.

    Returns True if a theme.json was found and applied, False if the
    hardcoded defaults are in effect (no file, or the file couldn't be
    parsed).
    """
    global ACTIVE_STYLE, ACTIVE_THEME, ACTIVE_RADIUS, ACTIVE_FONTS

    ACTIVE_STYLE = dict(MetroColorStyle.PURPLE)
    ACTIVE_THEME = dict(MetroThemeStyle.DARK)
    ACTIVE_RADIUS = RADIUS
    ACTIVE_FONTS = dict(_FONT_KEYS)

    theme_path = path or THEME_FILE
    if not os.path.isfile(theme_path):
        return False

    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False  # malformed/unreadable - keep the hardcoded defaults rather than crash

    if isinstance(data.get("style"), dict):
        ACTIVE_STYLE.update({k: v for k, v in data["style"].items() if k in ACTIVE_STYLE})

    if isinstance(data.get("theme"), dict):
        ACTIVE_THEME.update({k: v for k, v in data["theme"].items() if k in ACTIVE_THEME})

    if "radius" in data:
        try:
            ACTIVE_RADIUS = int(data["radius"])
        except (TypeError, ValueError):
            pass

    if isinstance(data.get("fonts"), dict):
        for key, spec in data["fonts"].items():
            if key not in ACTIVE_FONTS or not isinstance(spec, dict):
                continue
            default_family, default_size = ACTIVE_FONTS[key]
            family = spec.get("family") or default_family
            font_path = spec.get("path")
            if font_path:
                loaded_family = _register_font_file(font_path)
                if loaded_family:
                    family = loaded_family
            size = spec.get("size")
            size = size if isinstance(size, int) else default_size
            ACTIVE_FONTS[key] = (family, size)

    return True


load_theme()  # picks up theme.json next to this file at import time, if one exists


def write_default_theme_json(path=None):
    """
    Write a theme.json containing the hardcoded defaults (MetroColorStyle.
    PURPLE, MetroThemeStyle.DARK, the FONT_* tuples, RADIUS) in the same
    schema load_theme() reads - style/theme/fonts/radius. Loading the file
    this produces should look identical to having no theme.json at all;
    it's meant as a starting point to edit from rather than something that
    changes anything by itself.

    Returns True on success, False if the file couldn't be written
    (permissions/disk/etc - never raises).
    """
    data = {
        "style": dict(MetroColorStyle.PURPLE),
        "theme": dict(MetroThemeStyle.DARK),
        "fonts": {key: {"family": family, "size": size} for key, (family, size) in _FONT_KEYS.items()},
        "radius": RADIUS,
    }
    theme_path = path or THEME_FILE
    try:
        with open(theme_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# MetroForm - frameless window: thin accent strip, glyph controls, draggable
# ---------------------------------------------------------------------------

class MetroForm(QWidget):
    """
    Frameless top-level window. Build your UI inside `self.body`.
    Call MetroForm.app() once at program start to get the QApplication.

    `icon`: path to an .ico/.png (or a QIcon) to use as the window's icon -
    shown in the taskbar/alt-tab, since a frameless window has no native
    title bar for Windows to pull one from otherwise. Also applied to the
    QApplication, so it covers every window built.

    `maximizable`: set False to leave the maximize glyph out of the title
    bar entirely (just minimize/close) - for windows like TMenu's that
    auto-fit their own size and don't want the user fighting that.
    """

    @staticmethod
    def app():
        existing = QApplication.instance()
        return existing or QApplication([])

    def __init__(self, title="", heading="", size=(750, 460),
                 style=None, theme=None, resizable=False, min_size=(320, 220),
                 icon=None, maximizable=True, parent=None):
        super().__init__(parent)
        self.metro_style = style or ACTIVE_STYLE
        self.theme = theme or ACTIVE_THEME
        self._maximizable = maximizable

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle(title)  # taskbar/alt-tab title only, not shown in the bar

        # `icon` can be a path (str) to an .ico/.png or an already-built
        # QIcon. Frameless windows (Qt.FramelessWindowHint) draw no native
        # title bar, so Windows has nothing to pull a taskbar/alt-tab icon
        # from unless one is set explicitly here - the exe's own icon
        # (baked in at build time via PyInstaller's --icon) only covers
        # Explorer/shortcuts, not this. Also set on the QApplication so
        # every window (this one, popups, dialogs) shares it, not just the
        # first one built.
        if icon:
            qicon = icon if isinstance(icon, QIcon) else QIcon(icon)
            self.setWindowIcon(qicon)
            app_instance = QApplication.instance()
            if app_instance is not None:
                app_instance.setWindowIcon(qicon)

        self.resize(*size)
        self.setStyleSheet(f"background-color: {self.theme['bg']};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        strip = QFrame()
        strip.setFixedHeight(3)
        strip.setStyleSheet(f"background-color: {self.metro_style['accent']}; border: none;")
        outer.addWidget(strip)

        outer.addWidget(self._build_controlbar())

        # Large heading above the body/tabs - e.g. win = MetroForm(heading="My Tool")
        # or call win.set_heading("My Tool") any time after construction.
        self._heading_label = QLabel(heading)
        self._heading_label.setFont(_font(ACTIVE_FONTS["heading"]))
        self._heading_label.setStyleSheet(
            f"color: {self.theme['text']}; border: none; padding: 6px 0px 4px 0px;"
        )
        self._heading_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._heading_label.setVisible(bool(heading))
        outer.addWidget(self._heading_label)

        self.body = QWidget()
        self.body.setStyleSheet(f"background-color: {self.theme['bg']};")
        outer.addWidget(self.body, stretch=1)

        self._drag_pos = None

        # Bottom-right resize grip - only added when resizable=True
        self._grip = None
        if resizable:
            self.setMinimumSize(*min_size)
            self._grip = QSizeGrip(self)
            self._grip.setFixedSize(16, 16)
            self._grip.setStyleSheet("background: transparent;")

    def set_heading(self, text):
        """Set (or clear, with "") the large title shown above the body."""
        self._heading_label.setText(text)
        self._heading_label.setVisible(bool(text))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._grip is not None:
            self._grip.move(self.width() - self._grip.width(),
                             self.height() - self._grip.height())
            self._grip.raise_()

    # -- title bar -----------------------------------------------------
    def _build_controlbar(self):
        bar = QFrame()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"background-color: {self.theme['bg']}; border: none;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 4, 0)
        lay.setSpacing(0)

        lay.addStretch(1)

        glyph_style = f"""
            QPushButton {{
                background: transparent; border: none; color: {self.theme['text']};
                width: 30px; height: 24px; font-size: 12px;
            }}
            QPushButton:hover {{ background-color: %s; }}
        """
        min_btn = QPushButton("\u2013")
        min_btn.setStyleSheet(glyph_style % self.theme["panel"])
        min_btn.clicked.connect(self.showMinimized)

        close_btn = QPushButton("\u2715")
        close_btn.setStyleSheet(glyph_style % "#3a1414")
        close_btn.clicked.connect(self.close)

        buttons = [min_btn]
        if self._maximizable:
            max_btn = QPushButton("\u25a1")
            max_btn.setStyleSheet(glyph_style % self.theme["panel"])
            max_btn.clicked.connect(self._toggle_max)
            buttons.append(max_btn)
        buttons.append(close_btn)

        for b in buttons:
            b.setFixedSize(30, 24)
            b.setCursor(Qt.PointingHandCursor)
            lay.addWidget(b)

        bar.mousePressEvent = self._start_move
        bar.mouseMoveEvent = self._do_move
        self._maximized = False
        return bar

    def _toggle_max(self):
        if self._maximized:
            self.showNormal()
        else:
            self.showMaximized()
        self._maximized = not self._maximized

    def _start_move(self, event):
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _do_move(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)


# ---------------------------------------------------------------------------
# MetroButton - flat/outlined, neutral grey highlight on hover, plus a
# persistent "selected" state (checkable) for things like an ATTACH toggle
# ---------------------------------------------------------------------------

class MetroButton(QPushButton):
    def __init__(self, master=None, text="BUTTON", style=None, theme=None,
                 width=180, height=42, command=None, selected=False, **kwargs):
        super().__init__(text, master)
        style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFixedSize(width, height)
        self.setFont(_font(ACTIVE_FONTS["button"]))
        self.setCursor(Qt.PointingHandCursor)
        # Not checkable by default: the highlight is purely a hover/press
        # effect and disappears the instant the mouse leaves. Only becomes a
        # real toggle (via select()/deselect()) if you explicitly opt in.
        self.setCheckable(selected)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: {ACTIVE_RADIUS}px;
            }}
            QPushButton:hover {{
                background-color: {theme['border_strong']};
                color: {theme['bg']};
            }}
            QPushButton:pressed {{
                background-color: {theme['border_strong']};
                color: {theme['bg']};
            }}
            QPushButton:checked {{
                background-color: {theme['border_strong']};
                color: {theme['bg']};
            }}
        """)
        if command is not None:
            self.clicked.connect(command)
        if selected:
            self.setChecked(True)

    def select(self):
        """Lock in the highlighted look (turns the button checkable if it wasn't already)."""
        self.setCheckable(True)
        self.setChecked(True)

    def deselect(self):
        self.setChecked(False)

    def toggle_selected(self):
        self.setCheckable(True)
        self.setChecked(not self.isChecked())


def set_widget_bold(widget, bold: bool):
    """Flip a widget's current font bold on/off without touching anything
    else about it (size, family, italics, etc). Used to mark a toggle
    button as currently ON at a glance - see toggleables_tab.py's
    build_toggle_group - without needing a whole second QSS state."""
    f = widget.font()
    f.setBold(bool(bold))
    widget.setFont(f)


# ---------------------------------------------------------------------------
# MetroLabel / MetroTextBox / MetroTextArea
# ---------------------------------------------------------------------------

class MetroLabel(QLabel):
    def __init__(self, master=None, text="", theme=None, **kwargs):
        super().__init__(text, master)
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFont(_font(ACTIVE_FONTS["label"]))
        self.setStyleSheet(f"color: {theme['text']}; border: none; background: transparent;")


class MetroTextBox(QLineEdit):
    def __init__(self, master=None, theme=None, width=200, height=26, **kwargs):
        super().__init__(master)
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFixedSize(width, height)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: {ACTIVE_RADIUS}px;
                padding: 0 6px;
            }}
            QLineEdit:focus {{ border: 1px solid {theme['border_strong']}; }}
        """)


class MetroTextArea(QTextEdit):
    def __init__(self, master=None, theme=None, width=230, height=60, **kwargs):
        super().__init__(master)
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFixedSize(width, height)
        self.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: {ACTIVE_RADIUS}px;
            }}
        """)


# ---------------------------------------------------------------------------
# MetroPanel - plain flat-bordered container (no title)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MetroDropdown - flat combo box matching the field/border styling, with a
# similarly-styled popup list (accent highlight on hover/selection)
# ---------------------------------------------------------------------------

class MetroDropdown(QComboBox):
    def __init__(self, master=None, items=None, style=None, theme=None,
                 width=200, height=28, editable=False, command=None, **kwargs):
        super().__init__(master)
        style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFixedSize(width, height)
        self.setFont(_font(ACTIVE_FONTS["label"]))
        self.setEditable(editable)
        self.setCursor(Qt.PointingHandCursor)

        if items:
            self.addItems(items)

        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border']};
                border-radius: {ACTIVE_RADIUS}px;
                padding: 0 10px;
            }}
            QComboBox:hover {{
                border: 1px solid {theme['border_strong']};
            }}
            QComboBox:on {{
                border: 1px solid {style['accent']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {theme['text_dim']};
                width: 0px;
                height: 0px;
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme['field']};
                color: {theme['text']};
                border: 1px solid {theme['border_strong']};
                outline: none;
                selection-background-color: {style['accent']};
                selection-color: {theme['bg']};
                padding: 2px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 24px;
                padding: 0 8px;
            }}
        """)

        if command is not None:
            self.currentTextChanged.connect(command)


class SearchableDropdown(QWidget):
    """A search box + a dropdown, filtered by name. Shared by any tab that
    needs to pick one entry out of a long (key, name) list - e.g. ONLINE's
    challenge/map picker, TRICKS' trick pickers."""

    def __init__(self, master, entries, placeholder="Search...", width=260):
        """entries: list of (key_str, name_str)"""
        super().__init__(master)
        self._all_entries = sorted(entries, key=lambda e: e[1].lower())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.search_box = MetroTextBox(self, width=width, height=26)
        self.search_box.setPlaceholderText(placeholder)
        self.search_box.textChanged.connect(self._refresh)
        layout.addWidget(self.search_box)

        self.dropdown = MetroDropdown(self, width=width, height=28)
        layout.addWidget(self.dropdown)

        self._refresh("")

    def _refresh(self, search_text):
        needle = search_text.strip().lower()
        matches = [(key, name) for key, name in self._all_entries if needle in name.lower()]
        self.dropdown.blockSignals(True)
        self.dropdown.clear()
        for key, name in matches:
            self.dropdown.addItem(f"{name}  [{key}]", userData=key)
        self.dropdown.blockSignals(False)

    def selected_key(self):
        return self.dropdown.currentData()

    def set_selected_key(self, key):
        for i in range(self.dropdown.count()):
            if self.dropdown.itemData(i) == key:
                self.dropdown.setCurrentIndex(i)
                return True
        return False


class PlainKeyDropdown(QWidget):
    """Same key/name interface as SearchableDropdown, no search box - for
    short lists where a search field is just extra clutter."""

    def __init__(self, master, entries, width=260):
        """entries: list of (key_str, name_str)"""
        super().__init__(master)
        entries = sorted(entries, key=lambda e: e[1].lower())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.dropdown = MetroDropdown(self, width=width, height=28)
        for key, name in entries:
            self.dropdown.addItem(name, userData=key)
        layout.addWidget(self.dropdown)

    def selected_key(self):
        return self.dropdown.currentData()

    def set_selected_key(self, key):
        for i in range(self.dropdown.count()):
            if self.dropdown.itemData(i) == key:
                self.dropdown.setCurrentIndex(i)
                return True
        return False


def labeled_row(parent, label_text, widget):
    """A small label stacked above a widget - the ONLINE/TRICKS tabs' usual
    'field name over its control' layout."""
    row = QWidget(parent)
    lay = QVBoxLayout(row)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(MetroLabel(row, text=label_text))
    lay.addWidget(widget)
    return row


class MetroPanel(QFrame):
    def __init__(self, master=None, theme=None, **kwargs):
        super().__init__(master)
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.theme = theme
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {theme['panel']};
                border: 1px solid {theme['border_strong']};
                border-radius: {ACTIVE_RADIUS}px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(10)

    def add(self, widget):
        self._layout.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# MetroGroupBox - QGroupBox already renders its title overlapping the top
# border natively, which is exactly the look we hand-rolled in the tk
# version. All we do is style it flat and give it the same .add() helper.
# ---------------------------------------------------------------------------

class MetroGroupBox(QGroupBox):
    def __init__(self, master=None, title="", style=None, theme=None, **kwargs):
        super().__init__(title.upper(), master)
        style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.theme = theme
        self.metro_style = style
        self.setFont(_font(ACTIVE_FONTS["label"]))
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {theme['panel']};
                border: 1px solid {theme['border_strong']};
                border-radius: {ACTIVE_RADIUS}px;
                margin-top: 10px;
                color: {theme['text_dim']};
                font-weight: normal;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 6px;
                background-color: {theme['bg']};
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 20, 16, 16)
        self._layout.setSpacing(10)

    def add(self, widget):
        self._layout.addWidget(widget)
        return widget


# ---------------------------------------------------------------------------
# MetroTabControl - plain text tabs with a moving underline indicator,
# animated with QPropertyAnimation instead of snapping instantly
# ---------------------------------------------------------------------------

class FlowLayout(QLayout):
    """
    Left-to-right layout that wraps to a new row only when the next widget
    would run past the available width - like text wrapping, but for
    widgets. Used for flat-mode subtab planes instead of QGridLayout.

    The key difference from a grid: each row's height is just the tallest
    widget placed IN that row. A grid forces every row to match its tallest
    cell across the *entire* column (so a short widget sharing a column with
    a tall one gets stuck inside a cell as tall as that other widget, with
    all the leftover space showing as dead gap underneath it) - a flow
    layout has no columns to keep in sync, so nothing pads out to match a
    neighbor it isn't actually sharing a row with. That's what gives this
    the "packed like a puzzle" look instead of a lot of empty space.

    This is the standard Qt FlowLayout pattern (same one Qt's own C++
    examples ship), just implemented directly here in Python.
    """

    def __init__(self, parent=None, margin=0, h_spacing=12, v_spacing=12):
        super().__init__(parent)
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x, y = effective.x(), effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing

            # Wrap once the next widget would run past the right edge -
            # unless it's the only thing on this row (line_height == 0),
            # in which case there's nothing to gain by wrapping anyway.
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))

            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom


class MasonryLayout(QLayout):
    """
    Pinterest-style column packing: the plane is divided into fixed-width
    columns, and each widget is dropped into whichever column (or, for wide
    widgets, whichever run of *adjacent* columns) is currently shortest.

    This is the real fix for the gap FlowLayout still leaves: a row layout
    only ever compares a widget against whatever's immediately next to it in
    reading order, so a short widget next to a tall one still wastes all the
    space below it - nothing *later* in the list is ever allowed to go back
    and fill that space in. Masonry has no notion of "rows" at all, so a
    later short widget can drop straight into a column that a short sibling
    left mostly empty two items ago, instead of being forced onto a brand
    new line.

    A widget wider than one column spans however many adjacent columns its
    own sizeHint width needs (rounded to the nearest whole column) - that's
    Placement isn't strict registration order - see _do_layout for why.
    """

    def __init__(self, parent=None, margin=0, col_width=270, h_spacing=20, v_spacing=20):
        super().__init__(parent)
        self._col_width = col_width
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self._items = []
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        step = self._col_width + self._h_spacing

        num_cols = max(1, (effective.width() + self._h_spacing) // step)
        heights = [0] * num_cols  # current bottom y (relative to effective.top()) per column

        # span doesn't change once computed, so work it out once per item
        # rather than every time it's re-considered below.
        pending = []
        for item in self._items:
            hint = item.sizeHint()
            span = max(1, min(num_cols, round((hint.width() + self._h_spacing) / step)))
            pending.append([item, hint, span])

        # Placing strictly in registration order is what causes stranded
        # gaps: once a wide item forces every column it spans to jump to the
        # same height, whatever a shorter column was sitting on before that
        # is gone for good - nothing placed *after* can ever reach back and
        # fill space that's now behind a taller neighbor.
        #
        # So instead, at each step, every REMAINING item is checked for
        # where it would land right now, and whichever one would end up
        # lowest (i.e. fits some existing gap best) goes next - not
        # necessarily whichever was added first. In practice this means
        # small items naturally get pulled forward to plug short columns
        # while a big item is still pending, instead of that big item
        # steamrolling through and sealing the gap off first. Ties (equal
        # resulting height) keep registration order, so this only reorders
        # things when doing so actually saves space.
        while pending:
            best_idx = best_start = best_result = None
            for idx, (item, hint, span) in enumerate(pending):
                start, height_here = 0, None
                for candidate_start in range(0, num_cols - span + 1):
                    candidate = max(heights[candidate_start:candidate_start + span])
                    if height_here is None or candidate < height_here:
                        start, height_here = candidate_start, candidate
                result = height_here + hint.height()
                if best_result is None or result < best_result:
                    best_idx, best_start, best_result = idx, start, result

            item, hint, span = pending.pop(best_idx)
            gap_top = heights[best_start]
            y = effective.y() + gap_top + (self._v_spacing if gap_top > 0 else 0)
            x = effective.x() + best_start * step

            if not test_only:
                width = span * self._col_width + (span - 1) * self._h_spacing
                item.setGeometry(QRect(x, y, width, hint.height()))

            new_bottom = (y - effective.y()) + hint.height()
            for c in range(best_start, best_start + span):
                heights[c] = new_bottom

        return (max(heights) if heights else 0) + bottom


def show_subtab_gallery(win, title, size=(950, 700)):
    """
    Opens a secondary, FIXED-size window that shows every subtab of a tab
    all at once - the "uncompacted" view. This is deliberately its own
    separate, bounded rectangle rather than trying to inline-expand the main
    window: there's no reasonable window size that's guaranteed to fit
    "every subtab, fully expanded" for every tab, so instead of growing the
    main window to chase that (which either has to cover most of the screen
    for a tab with a lot of subtabs, or overflow it), this pops up a modest,
    fixed-size window with a scroll area - content that doesn't fit within
    `size` just scrolls, the window itself never grows past it.

    Reuses MetroTabControl's existing flat/MasonryLayout packing (see that
    class) for the actual "everything on one packed plane" layout - this
    function is just "put that inside a scroll area, inside its own small
    window" instead of inline in the main one.

    Returns (gallery_window, tabs) - `tabs` is a fresh MetroTabControl
    (compact=False) with nothing added yet; call .add()/.add_multi() on it
    and build content into the frames it hands back, exactly like setting
    up any other subtab set. The caller owns rebuilding this from scratch
    each time it's opened (cheap - it's just widget construction), so
    there's no stale-state to worry about between opens.
    """
    gallery = MetroForm(title, heading=title, size=size,
                         style=win.metro_style, theme=win.theme, resizable=False)

    body_layout = QVBoxLayout(gallery.body)
    body_layout.setContentsMargins(0, 0, 0, 0)

    scroll = QScrollArea(gallery.body)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"QScrollArea {{ background-color: {win.theme['bg']}; border: none; }}")
    body_layout.addWidget(scroll)

    tabs = MetroTabControl(
        scroll, width=size[0] - 40, height=size[1] - 120,
        style=win.metro_style, theme=win.theme, compact=False,
    )
    scroll.setWidget(tabs)

    gallery.show()
    return gallery, tabs


class MetroTabControl(QWidget):
    """
    Tabbed control with a moving underline. Two layout modes:

      - compact (default): one subtab visible at a time behind a tab bar,
        the classic behaviour.
      - flat (compact=False): the tab bar is hidden and every tab's frame is
        shown stacked on one large plane, so nothing has to be clicked
        through. Handy on large monitors. .set()/.tab()/.add() all still
        work the same so builders don't have to care which mode is active.

    add(name) registers a subtab with one content frame. add_multi(name,
    count) registers one with `count` independent frames - use that instead
    whenever a subtab is really several side-by-side groups (see its
    docstring for why that distinction matters in flat mode specifically).
    """

    def __init__(self, master=None, style=None, theme=None, width=700, height=350,
                 bar_height=34, font=None, spacing=18, left_margin=12,
                 compact=True, plane_spacing=24, **kwargs):
        super().__init__(master)
        self.metro_style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        self.theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self._tab_font = font or ACTIVE_FONTS["tab"]
        self._compact = compact
        self.resize(width, height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background-color: {self.theme['bg']};")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._tabbar = QWidget()
        self._tabbar.setFixedHeight(bar_height)
        self._tabbar_layout = QHBoxLayout(self._tabbar)
        self._tabbar_layout.setContentsMargins(left_margin, 4, 0, 4)
        self._tabbar_layout.setSpacing(spacing)
        self._tabbar_layout.addStretch(1)  # right-side flex so buttons hug left
        outer.addWidget(self._tabbar)

        # divider: full-width grey line, underline drawn on top of it
        self._divider = QFrame(self)
        self._divider.setFixedHeight(1)
        self._divider.setStyleSheet(f"background-color: {self.theme['border']}; border: none;")
        outer.addWidget(self._divider)

        self._underline = QFrame(self)
        self._underline.setFixedHeight(2)
        self._underline.setStyleSheet(f"background-color: {self.metro_style['accent']}; border: none;")
        self._underline.setParent(self)  # floats above the divider via raise_()

        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {self.theme['bg']};")
        # Compact mode stacks frames vertically (only one visible at a time).
        # Flat mode packs every frame into a MasonryLayout - each frame drops
        # into whichever column is currently shortest, so a short frame later
        # in the list can backfill space a short frame earlier left empty
        # under a tall neighbor, instead of every frame being stuck in strict
        # reading-order rows. See MasonryLayout above for why that (instead
        # of a grid, or even a plain row-wrapping flow layout) is what avoids
        # dead gaps.
        self._plane_spacing = plane_spacing
        if compact:
            self._content_layout = QVBoxLayout(self._content)
            self._content_layout.setContentsMargins(0, 0, 0, 0)
            self._content_layout.setSpacing(0)
        else:
            self._content_layout = MasonryLayout(
                self._content, margin=0, h_spacing=plane_spacing, v_spacing=plane_spacing,
            )
        outer.addWidget(self._content, stretch=1)

        # Flat mode has no tab bar / underline - everything is on one plane.
        if not self._compact:
            self._tabbar.hide()
            self._divider.hide()
            self._underline.hide()

        self._tabs = {}
        self._order = []
        self._active = None
        self._anim = QPropertyAnimation(self._underline, b"geometry")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _register_tab_button(self, name, shown_widget):
        """Shared by add()/add_multi(): the tab-bar button and bookkeeping
        don't care whether `shown_widget` is a single content frame or a
        panel wrapping several - .set()/.show()/.hide() just need one
        QWidget to act on either way."""
        btn = QPushButton(name)
        btn.setFont(_font(self._tab_font))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {self.theme['text_dim']}; padding: 4px 0px;
            }}
            QPushButton:hover {{ color: {self.theme['text']}; }}
        """)
        btn.clicked.connect(lambda _, n=name: self.set(n))
        self._tabbar_layout.insertWidget(len(self._order), btn)

        self._tabs[name] = {"button": btn, "frame": shown_widget}
        self._order.append(name)
        if self._active is None:
            self._active = name  # track a nominal active tab even in flat mode
            if self._compact:
                self.set(name)

    def add(self, name):
        frame = QWidget()
        frame.setStyleSheet(f"background-color: {self.theme['bg']};")
        # Flat mode: the frame stays visible, packed in with every other
        # frame by the MasonryLayout. Compact mode: hidden until selected.
        if self._compact:
            frame.hide()
        self._content_layout.addWidget(frame)
        self._register_tab_button(name, frame)
        return frame

    def add_multi(self, name, count):
        """
        Like add(), but for a subtab that's actually `count` independent
        content groups meant to be shown together (e.g. RGB's "Colors" and
        "RGB Swapping" groups) rather than one single frame.

        Compact mode packs the `count` frames side by side in one row
        inside a single panel, shown/hidden together and selected via the
        tab bar exactly like any other subtab - looks identical to before.

        Flat mode instead adds each of the `count` frames straight to the
        outer MasonryLayout as fully independent items. That's the part
        that actually matters: previously a subtab with two side-by-side
        groups of different heights was ONE box to the masonry packer, sized
        to whichever group was taller - the shorter group's leftover space
        was dead, unreachable by anything else on the plane. As independent
        items, the shorter one's column can get backfilled by whatever's
        placed after it, same as any other box.
        """
        frames = []
        if self._compact:
            panel = QWidget()
            panel.setStyleSheet(f"background-color: {self.theme['bg']};")
            panel.hide()
            panel_layout = QHBoxLayout(panel)
            panel_layout.setContentsMargins(0, 0, 0, 0)
            panel_layout.setSpacing(self._plane_spacing)
            panel_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
            for _ in range(count):
                f = QWidget()
                f.setStyleSheet(f"background-color: {self.theme['bg']};")
                panel_layout.addWidget(f, alignment=Qt.AlignTop)
                frames.append(f)
            self._content_layout.addWidget(panel)
            self._register_tab_button(name, panel)
        else:
            for _ in range(count):
                f = QWidget()
                f.setStyleSheet(f"background-color: {self.theme['bg']};")
                self._content_layout.addWidget(f)
                frames.append(f)
            # Flat mode has no visible tab bar to select from, but a button
            # is still registered for bookkeeping consistency (._order,
            # ._tabs) - frames[0] is just a nominal handle, never shown/hidden.
            self._register_tab_button(name, frames[0])
        return frames

    def tab(self, name):
        return self._tabs[name]["frame"]

    def set(self, name):
        if self._active is not None:
            self._tabs[self._active]["button"].setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {self.theme['text_dim']}; padding: 4px 0px;
                }}
                QPushButton:hover {{ color: {self.theme['text']}; }}
            """)
            self._tabs[self._active]["frame"].hide()

        self._active = name
        # Active tab is indicated by the moving underline only - the label
        # itself just becomes the brighter neutral text color, never the
        # accent color.
        self._tabs[name]["button"].setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {self.theme['text']}; padding: 4px 0px;
            }}
        """)
        self._tabs[name]["frame"].show()
        self._update_underline(animate=True)

    def _update_underline(self, animate=True):
        # Flat mode hides the tab bar / divider / underline entirely - every
        # frame is shown stacked on one plane, so there's no underline to
        # position. Bail out before touching any of those hidden widgets.
        if not self._compact:
            return
        # Force layout to run first - at construction time (before the window
        # is shown) child widgets haven't been positioned yet, so reading
        # .x()/.y() too early gives 0 and the underline ends up misplaced
        # (e.g. rendered above the tab row instead of under it).
        self._tabbar.layout().activate()
        self.layout().activate()

        btn = self._tabs[self._active]["button"]
        x = btn.x()
        w = btn.sizeHint().width()  # fixed to the label's natural width, never stretches
        y = self._divider.y()
        target = QRect(x, y, w, 2)
        if not animate or self._underline.geometry().width() == 0:
            self._underline.setGeometry(target)
        else:
            self._anim.stop()
            self._anim.setStartValue(self._underline.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        self._underline.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._active is not None:
            self._update_underline(animate=False)

    def showEvent(self, event):
        super().showEvent(event)
        if self._active is not None:
            self._update_underline(animate=False)


# ---------------------------------------------------------------------------
# MetroSwitch - Qt has no native toggle switch, so this is a small custom
# checkable button styled + animated to look like one
# ---------------------------------------------------------------------------

class MetroSwitch(QPushButton):
    toggled_on = Signal(bool)

    def __init__(self, master=None, text="", style=None, theme=None, **kwargs):
        super().__init__(master)
        style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self._accent = style["accent"]
        self._off_color = theme["border"]
        self._label_text = text

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(44, 22)
        self.setStyleSheet(self._qss(False))
        self.toggled.connect(lambda checked: (
            self.setStyleSheet(self._qss(checked)), self.toggled_on.emit(checked)
        ))

        if text:
            self._label = QLabel(text, master)
            self._label.setFont(_font(ACTIVE_FONTS["label"]))
            self._label.setStyleSheet(f"color: {theme['text']}; border: none;")

    def _qss(self, on):
        bg = self._accent if on else self._off_color
        return f"""
            QPushButton {{
                background-color: {bg};
                border-radius: 11px;
                border: none;
            }}
        """


# ---------------------------------------------------------------------------
# MetroSlider - flat horizontal QSlider wrapper matching the field/border
# styling. The groove background can be overridden with any valid QSS
# "background" value (a plain color, or a qlineargradient(...) stop string)
# via track_style / set_track_style - that's what lets a hue bar show a
# rainbow gradient, a saturation bar show white-to-hue, etc, while a plain
# MetroSlider() with no track_style just looks like a normal flat slider.
# ---------------------------------------------------------------------------

class MetroSlider(QWidget):
    """
    A thin QWidget wrapper around QSlider (Qt has no flat "Metro" slider of
    its own) so it can sit in a layout alongside the rest of TsUI the same
    way every other Metro* widget does, while still exposing the handful of
    QSlider methods callers actually need (value/setValue/setRange) plus a
    valueChanged signal.

    track_style accepts anything valid as a QSS "background" value - a flat
    color like theme['field'], or a gradient string such as
    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f00, stop:1 #00f)".
    Pass a fresh one to set_track_style() any time the gradient itself needs
    to change (e.g. a saturation bar's white-to-hue endpoint moving as the
    hue slider next to it changes).
    """

    valueChanged = Signal(int)

    def __init__(self, master=None, minimum=0, maximum=100, value=0,
                 style=None, theme=None, width=220, height=22,
                 track_style=None, **kwargs):
        super().__init__(master)
        self._style = style or getattr(master, "metro_style", None) or ACTIVE_STYLE
        self._theme = theme or getattr(master, "theme", None) or ACTIVE_THEME
        self.setFixedSize(width, height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setMinimum(minimum)
        self.slider.setMaximum(maximum)
        self.slider.setValue(value)
        self.slider.setFixedHeight(height)
        self.slider.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.slider)

        self._track_style = track_style
        self._apply_qss()

        self.slider.valueChanged.connect(self.valueChanged.emit)

    def _apply_qss(self):
        theme = self._theme
        groove_bg = self._track_style or theme["field"]
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 8px;
                background: {groove_bg};
                border: 1px solid {theme['border']};
                border-radius: {ACTIVE_RADIUS}px;
            }}
            QSlider::handle:horizontal {{
                background: {theme['text']};
                border: 1px solid {theme['border_strong']};
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: transparent;
            }}
            QSlider::add-page:horizontal {{
                background: transparent;
            }}
        """)

    def set_track_style(self, css_background):
        """Swap the groove's QSS "background" value (color or gradient) in place."""
        self._track_style = css_background
        self._apply_qss()

    def value(self):
        return self.slider.value()

    def setValue(self, v):
        self.slider.blockSignals(True)
        self.slider.setValue(v)
        self.slider.blockSignals(False)

    def setRange(self, minimum, maximum):
        self.slider.setRange(minimum, maximum)