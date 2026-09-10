"""
restart.py
==========
Tiny standalone relauncher for app.py. The SETTINGS tab spawns this as its own
detached process, then app.py exits - so the old window is fully gone before the
fresh one comes up. This avoids re-exec'ing inside the still-running Qt event
loop (which was fragile), and cleanly rebuilds the whole UI in whatever layout
mode settings.json now holds.

It waits briefly for the parent (the old app.py) to exit, then launches a new
`python app.py` in the same folder and quits itself.

Usage (spawned by settings_tab, not run by hand):
    python restart.py <parent_pid>

The parent_pid is optional; if given, we poll until that process is gone (up to
a short timeout) before relaunching, so the two windows never overlap.
"""

import os
import subprocess
import sys
import time

from app_paths import base_dir

HERE = base_dir()
# Frozen build: relaunch the .exe itself (sys.executable *is* the app, there
# is no separate app.py to hand to a Python interpreter). Running from
# source: fall back to the old "python app.py" behaviour.
FROZEN = getattr(sys, "frozen", False)
APP = sys.executable if FROZEN else os.path.join(HERE, "app.py")


def _wait_for_exit(pid, timeout=5.0):
    """Poll until the given PID is gone, or timeout seconds elapse.

    Uses os.kill(pid, 0) which raises OSError once the process no longer
    exists (or we can no longer signal it) - either way it's safe to relaunch.
    """
    if pid <= 0:
        return
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return  # parent gone
        time.sleep(0.05)


def main():
    parent_pid = 0
    if len(sys.argv) > 1:
        try:
            parent_pid = int(sys.argv[1])
        except ValueError:
            parent_pid = 0

    _wait_for_exit(parent_pid)

    # Launch a fresh instance and let this helper exit. Detached so it doesn't
    # stay tied to this short-lived launcher process. Frozen: APP already *is*
    # the exe, so just run it directly rather than handing it to itself as an
    # interpreter argument.
    cmd = [APP] if FROZEN else [sys.executable, APP]
    subprocess.Popen(cmd, cwd=HERE)


if __name__ == "__main__":
    main()
