import os
import subprocess
import sys
import time

from app_paths import base_dir

HERE = base_dir()
# frozen (.exe) build: relaunch the exe itself; running from source: relaunch app.py
FROZEN = getattr(sys, "frozen", False)
APP = sys.executable if FROZEN else os.path.join(HERE, "app.py")


def _wait_for_exit(pid, timeout=5.0):
    # poll until pid is gone or we time out
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

    # launch a fresh instance and let this helper process exit
    cmd = [APP] if FROZEN else [sys.executable, APP]
    subprocess.Popen(cmd, cwd=HERE)

if __name__ == "__main__":
    main()
