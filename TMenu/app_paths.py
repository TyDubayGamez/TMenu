import os
import sys

from PySide6.QtWidgets import QFileDialog


def base_dir() -> str:
    # folder next to the .exe (frozen build) or next to app.py (running from source)
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(*parts) -> str:
    # path to a resource bundled inside the exe (e.g. icon.ico), not one
    # sitting next to it on disk - use base_dir() for that instead
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def export_dir(kind: str) -> str:
    # subfolder of base_dir() named after `kind` (theme/challenge/config/etc),
    # created if it doesn't exist yet
    path = os.path.join(base_dir(), kind)
    os.makedirs(path, exist_ok=True)
    return path


def export_save_path(parent, kind: str, default_filename: str, title: str, file_filter: str) -> str:
    # shared "Save As" dialog for every export button, pre-aimed at
    # <base_dir>/<kind>/<default_filename>. Returns "" if the user cancels.
    folder = export_dir(kind)
    default_path = os.path.join(folder, default_filename)
    path, _ = QFileDialog.getSaveFileName(parent, title, default_path, file_filter)
    return path
