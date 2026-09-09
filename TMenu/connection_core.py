def do_connect_and_attach(state, ip, settings=None):
    # blocking call, run this off the GUI thread. returns (ok, message)
    if not ip:
        return False, "No IP address to connect to."

    try:
        # connecting again when already connected is a no-op, so retrying
        # after a failed attach is safe
        state.ps3.ConnectTarget(ip)
        state.ip = ip
        state.connected = True
        if settings is not None and settings.last_ip != ip:
            settings.last_ip = ip
            settings.save()

        # find the running game process
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
