import ps3mapi


class AppState:
    def __init__(self):
        self.ps3 = ps3mapi.PS3MAPI()
        self.ip = ""
        self.connected = False
        self.attached = False
        self.attached_name = ""
        self.on_attach = []  # callbacks to run right after a successful attach

    @property
    def pid(self) -> int:
        return self.ps3.Process.Process_Pid

    def is_ready(self) -> bool:
        # safe to read/write memory once both connected and attached
        return self.connected and self.attached

    def notify_attached(self):
        # run every callback, skip errors so one bad callback doesn't stop the rest
        for cb in list(self.on_attach):
            try:
                cb()
            except Exception:
                pass
