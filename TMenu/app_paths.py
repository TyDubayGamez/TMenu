"""
app_paths.py
============
One shared helper for "the folder the app lives in".

Every module that needs to find a JSON file sitting next to the app used to
compute that with `os.path.dirname(os.path.abspath(__file__))`. That works
fine running from source (python app.py), but breaks once the app is frozen
into a single-file PyInstaller exe: `__file__` for a frozen module points
into the temporary `_MEIPASS` folder PyInstaller unpacks itself into at
startup, which is a fresh throwaway directory every single run - not the
folder the .exe actually sits in. Settings/theme/challenge files "next to
the exe" would silently stop persisting.

`base_dir()` is the fix: frozen builds resolve to the real folder holding
the .exe (via sys.executable), everything else falls back to the old
__file__-based behaviour unchanged. Every module that previously rolled its
own HERE/THEME_FILE/etc. via __file__ should import base_dir() from here
instead, so there's exactly one place this logic lives.
"""

import os
import sys

from PySide6.QtWidgets import QFileDialog


def base_dir() -> str:
    """Folder the running app should treat as 'next to me'.

    - Frozen (PyInstaller) build: the folder containing the .exe.
    - Running from source: the folder containing app.py (this repo).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts) -> str:
    """Path to a resource bundled *inside* the exe (e.g. icon.ico), not one
    sitting next to it on disk - use base_dir() for the latter.

    PyInstaller onefile builds unpack anything added via --add-data into a
    fresh temporary `_MEIPASS` folder at startup (a different one every
    run), so a bundled resource has to be looked up there when frozen.
    Running from source just resolves relative to this repo's folder, same
    as base_dir() does, since there's no bundle to unpack.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def export_dir(kind: str) -> str:
    """Folder a given kind of export (theme/challenge/config/binds/recipes/
    etc.) should land in - a subfolder of base_dir() named after `kind`,
    created on demand if it doesn't exist yet.

    Every export button in the app funnels through this (via
    export_save_path() below) instead of writing wherever it feels like, so
    everything a given export produces ends up sorted into its own folder
    next to the exe rather than scattered loose next to it.
    """
    path = os.path.join(base_dir(), kind)
    os.makedirs(path, exist_ok=True)
    return path


def export_save_path(parent, kind: str, default_filename: str, title: str, file_filter: str) -> str:
    """Shared "Save As" prompt for every export button in the app.

    Ensures <base_dir>/<kind>/ exists, then opens the normal OS Save dialog
    pre-aimed at <base_dir>/<kind>/<default_filename> - so it always starts
    out in the right folder with a sensible name already filled in, and the
    user can rename that filename (or, since it's a regular OS dialog,
    choose a different folder entirely) before confirming. Nothing is
    written by this function itself - it only returns the path the user
    picked, or "" if they cancelled, and the caller does the actual write.

    Note on "forcing" the folder: a native OS Save dialog can be *aimed* at
    a folder (which is what this does - every export always opens there by
    default) but can't be hard-locked to it without replacing it with a
    custom in-app dialog, which would behave less familiarly than the
    system one. If a stricter "can't leave this folder" behavior turns out
    to matter in practice, that's a follow-up worth doing deliberately.
    """
    folder = export_dir(kind)
    default_path = os.path.join(folder, default_filename)
    path, _ = QFileDialog.getSaveFileName(parent, title, default_path, file_filter)
    return path
