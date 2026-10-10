"""
connection_core.py
===================
The "connect, then find EBOOT.BIN and attach" logic used by connection_tab.py's
CONNECT button. Kept as its own module (rather than inline in
connection_tab.py) since it's plain PS3MAPI-and-`state` logic with no Qt
widgets involved - do_connect_and_attach() is deliberately UI-free.
"""


def do_connect_and_attach(state, ip, settings=None):
    """
    Blocking - call this off the GUI thread. Returns (ok, message).

    On success: updates state.connected/attached/attached_name/ip, saves
    `ip` to settings.last_ip if given and different, and fires
    state.notify_attached().

    On a partial result (connected, but EBOOT.BIN isn't running yet):
    state.connected is left True; state.attached is left False - the
    caller (the user pressing CONNECT again) is expected to retry the
    attach once the game is up.

    On a full failure (e.g. target unreachable): state.connected/attached
    are both left False.
    """
    if not ip:
        return False, "No IP address to connect to."

    try:
        # Connecting is a no-op if a session is already up (ps3mapi's
        # connect() just returns), so pressing CONNECT again after a
        # successful connect-but-failed-attach safely retries the attach
        # without re-dialing the socket.
        state.ps3.ConnectTarget(ip)
        state.ip = ip
        state.connected = True
        if settings is not None and settings.last_ip != ip:
            settings.last_ip = ip
            settings.save()

        pids = state.ps3.Process.GetPidProcesses()
        eboot_pid = None
        for pid in pids:
            name = state.ps3.Process.GetName(pid)
            if "EBOOT.BIN" in name.upper():
                eboot_pid = pid
                break

        if eboot_pid is None:
            state.attached = False
            return False, (
                f"Connected to {ip}, but EBOOT.BIN not found. "
                "Open Skate 3, then press CONNECT again to attach."
            )

        state.ps3.AttachProcess(eboot_pid)
        state.attached = True
        state.attached_name = "EBOOT.BIN"
        state.notify_attached()
        return True, f"Attached to EBOOT.BIN ({eboot_pid:#010x})"
    except Exception as e:
        state.connected = False
        state.attached = False
        return False, str(e)
