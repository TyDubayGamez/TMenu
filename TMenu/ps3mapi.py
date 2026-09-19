"""
ps3mapi.py
==========
A compact, pure-Python port of PS3ManagerAPI (PS3MAPI.dll) - the .NET client
library that talks to the "PS3MAPI" server built into webMAN-MOD on a PS3.

Original library: a Windows Forms .NET DLL using a text/FTP-style TCP
protocol (commands like "PS3 GETFWVERSION", "MEMORY GET ...", "PASV", etc.)
plus a binary data-socket for memory read/write, exactly like classic FTP
PORT/PASV transfers.

This module re-implements every command from the original DLL, but as one
small, dependency-free file. GUI bits (ConnectDialog/AttachDialog/LogDialog,
which were WinForms popups) are replaced with simple optional console
prompts so the library works headless - everything else maps 1:1 to the
original API surface.

Quick start
-----------
    import ps3mapi

    ps3 = ps3mapi.PS3MAPI()
    ps3.ConnectTarget("192.168.1.50")        # or ConnectTarget(port=7887)
    ps3.AttachProcess(0x00010001)            # or AttachProcess() to pick interactively

    print(ps3.PS3.GetFirmwareVersion_Str())
    ps3.PS3.Notify("Hello from Python!")

    data = ps3.Process.Memory.Get(ps3.Process.Process_Pid, 0x00000000, 16)
    ps3.Process.Memory.Set(ps3.Process.Process_Pid, 0x00000000, b"\\x00" * 16)

    ps3.DisconnectTarget()

Or, as a context manager:

    with ps3mapi.PS3MAPI() as ps3:
        ps3.ConnectTarget("192.168.1.50")
        ps3.PS3.RingBuzzer(ps3mapi.BuzzerMode.Single)
"""

from __future__ import annotations

import re
import socket

__all__ = [
    "PS3MAPI", "PS3MAPIError", "ResponseCode",
    "PowerFlags", "BuzzerMode", "LedColor", "LedMode", "Syscall8Mode",
]

PS3M_API_PC_LIB_VERSION = 288       # matches the original DLL's reported version
PS3M_API_SERVER_MINVERSION = 288    # minimum compatible webMAN-MOD PS3MAPI server


class PS3MAPIError(Exception):
    """Raised for any PS3MAPI protocol/transport error (mirrors the C# Exception)."""


class ResponseCode:
    """FTP-like numeric response codes used by the PS3MAPI server."""
    DataConnectionAlreadyOpen = 125
    MemoryStatusOK = 150
    CommandOK = 200
    PS3MAPIConnected = 220
    PS3MAPIConnectedOK = 230
    RequestSuccessful = 226
    EnteringPassiveMode = 227
    MemoryActionCompleted = 250
    MemoryActionPended = 350


# ---- enums (plain int constants, same values as the original C# enums) ----

class PowerFlags:
    ShutDown, QuickReboot, SoftReboot, HardReboot = range(4)


class BuzzerMode:
    Single, Double, Triple = range(1, 4)


class LedColor:
    Red, Green, Yellow = range(3)


class LedMode:
    Off, On, BlinkFast, BlinkSlow = range(4)


class Syscall8Mode:
    Enabled, Only_CobraMambaAndPS3MAPI_Enabled, Only_PS3MAPI_Enabled, FakeDisabled, Disabled = range(5)


def _ver_str(value: int) -> str:
    """Render a packed version int the same way the DLL did: 0x0120 -> '1.2.0'."""
    h = format(value, "04X")
    return f"{h[1]}.{h[2]}.{h[3]}"


# --------------------------------------------------------------------------
# Low level connection / protocol handler
# --------------------------------------------------------------------------

class _Connection:
    """Owns the sockets and implements the FTP-style text protocol."""

    def __init__(self):
        self.sock: socket.socket | None = None
        self.data_sock: socket.socket | None = None
        self.ip = ""
        self.port = 7887
        self.timeout = 5.0   # seconds
        self.bucket = ""
        self.log = ""
        self.response_code = 0
        self.response = ""

    @property
    def is_connected(self) -> bool:
        return self.sock is not None

    # -- connection lifecycle --------------------------------------------

    def connect(self, ip: str | None = None, port: int | None = None) -> None:
        if ip is not None:
            self.ip = ip
        if port is not None:
            self.port = port
        if self.sock is not None:
            return  # already connected
        if not self.ip:
            raise PS3MAPIError("Unable to connect - no server specified.")

        sock = socket.create_connection((self.ip, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)
        self.sock = sock

        self._read_response()
        if self.response_code != ResponseCode.PS3MAPIConnected:
            self._fail()
        self._read_response()
        if self.response_code != ResponseCode.PS3MAPIConnectedOK:
            self._fail()

        min_ver = self.cmd_int("SERVER GETMINVERSION")
        if min_ver < PS3M_API_SERVER_MINVERSION:
            self.disconnect()
            raise PS3MAPIError("PS3M_API SERVER (webMAN-MOD) OUTDATED! PLEASE UPDATE.")
        if min_ver > PS3M_API_SERVER_MINVERSION:
            self.disconnect()
            raise PS3MAPIError("PS3M_API PC_LIB (ps3mapi.py) OUTDATED! PLEASE UPDATE.")

    def disconnect(self) -> None:
        self._close_data_socket()
        if self.sock is not None:
            try:
                self.send_command("DISCONNECT")
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    # -- raw protocol ------------------------------------------------------

    def send_command(self, command: str) -> None:
        self.log += f"COMMAND: {command}\n"
        self.connect()  # ensures a live session, reconnecting with the last ip/port if needed
        self.sock.sendall((command + "\r\n").encode("ascii"))
        self._read_response()

    def _read_line(self) -> str:
        while "\n" not in self.bucket:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                raise PS3MAPIError("Timed out waiting on server to respond.")
            if not chunk:
                raise PS3MAPIError("Connection closed by server.")
            self.bucket += chunk.decode("ascii", errors="replace")
        line, self.bucket = self.bucket.split("\n", 1)
        return line

    def _read_response(self) -> None:
        messages = ""
        while True:
            line = self._read_line()
            if re.match(r"^[0-9]+ ", line):
                break
            messages += re.sub(r"^[0-9]+-", "", line) + "\n"
        self.response = line[4:].replace("\r", "").replace("\n", "")
        self.response_code = int(line[:3])
        self.log += f"RESPONSE CODE: {self.response_code}\nRESPONSE MSG: {self.response}\n\n"

    def _fail(self):
        msg = f"[{self.response_code}] {self.response}"
        self.disconnect()
        raise PS3MAPIError(msg)

    def _check_ok(self) -> None:
        if self.response_code not in (ResponseCode.CommandOK, ResponseCode.RequestSuccessful):
            self._fail()

    def cmd(self, text: str) -> str:
        """Send a command, assert a generic-OK response, return the response text."""
        self.send_command(text)
        self._check_ok()
        return self.response

    def cmd_int(self, text: str, base: int = 10) -> int:
        return int(self.cmd(text), base)

    # -- binary / data-socket transfers (PASV-style, used for memory R/W) --

    def _set_binary_mode(self, binary: bool) -> None:
        self.send_command("TYPE I" if binary else "TYPE A")
        self._check_ok()

    def _open_data_socket(self) -> None:
        self.connect()
        self.send_command("PASV")
        if self.response_code != ResponseCode.EnteringPassiveMode:
            self._fail()
        m = re.search(r"\((.*)\)", self.response)
        parts = m.group(1).split(",") if m else []
        if len(parts) < 6:
            self._fail()
        port = (int(parts[4]) << 8) + int(parts[5])
        self._close_data_socket()
        # NB: matches the original behaviour of ignoring the IP octets PASV
        # returns and just reusing the server address already connected to.
        self.data_sock = socket.create_connection((self.ip, port), timeout=self.timeout)
        self.data_sock.settimeout(self.timeout)

    def _close_data_socket(self) -> None:
        if self.data_sock is not None:
            try:
                self.data_sock.close()
            except Exception:
                pass
            self.data_sock = None

    def memory_get(self, pid: int, address: int, length: int) -> bytes:
        self._set_binary_mode(True)
        self._open_data_socket()
        self.send_command(f"MEMORY GET {pid} {address:016X} {length}")
        if self.response_code not in (ResponseCode.DataConnectionAlreadyOpen, ResponseCode.MemoryStatusOK):
            self._close_data_socket()
            raise PS3MAPIError(self.response)
        data = bytearray()
        try:
            while len(data) < length:
                chunk = self.data_sock.recv(length - len(data))
                if not chunk:
                    break
                data.extend(chunk)
        finally:
            self._close_data_socket()
            self._read_response()
        if self.response_code not in (ResponseCode.RequestSuccessful, ResponseCode.MemoryActionCompleted):
            self._set_binary_mode(False)
            raise PS3MAPIError(self.response)
        self._set_binary_mode(False)
        return bytes(data)

    def memory_set(self, pid: int, address: int, data: bytes) -> None:
        self._set_binary_mode(True)
        self._open_data_socket()
        self.send_command(f"MEMORY SET {pid} {address:016X}")
        if self.response_code not in (ResponseCode.DataConnectionAlreadyOpen, ResponseCode.MemoryStatusOK):
            self._close_data_socket()
            raise PS3MAPIError(self.response)
        try:
            self.data_sock.sendall(bytes(data))
        finally:
            self._close_data_socket()
            self._read_response()
        if self.response_code not in (ResponseCode.RequestSuccessful, ResponseCode.MemoryActionCompleted):
            self._set_binary_mode(False)
            raise PS3MAPIError(self.response)
        self._set_binary_mode(False)


# --------------------------------------------------------------------------
# High level command groups (mirror PS3MAPI.SERVER_CMD / CORE_CMD / etc.)
# --------------------------------------------------------------------------

class _ServerCmd:
    def __init__(self, conn: _Connection):
        self._c = conn

    @property
    def Timeout(self) -> int:
        """Socket timeout, in milliseconds (matches the original property)."""
        return int(self._c.timeout * 1000)

    @Timeout.setter
    def Timeout(self, ms: int) -> None:
        self._c.timeout = ms / 1000.0
        if self._c.sock:
            self._c.sock.settimeout(self._c.timeout)

    def GetVersion(self) -> int:
        return self._c.cmd_int("SERVER GETVERSION")

    def GetVersion_Str(self) -> str:
        return _ver_str(self.GetVersion())

    def GetMinVersion(self) -> int:
        return self._c.cmd_int("SERVER GETMINVERSION")


class _CoreCmd:
    def __init__(self, conn: _Connection):
        self._c = conn

    def GetVersion(self) -> int:
        return self._c.cmd_int("CORE GETVERSION")

    def GetVersion_Str(self) -> str:
        return _ver_str(self.GetVersion())

    def GetMinVersion(self) -> int:
        return self._c.cmd_int("CORE GETMINVERSION")


class _PS3Cmd:
    _POWER_CMDS = {
        PowerFlags.ShutDown: "PS3 SHUTDOWN",
        PowerFlags.QuickReboot: "PS3 REBOOT",
        PowerFlags.SoftReboot: "PS3 SOFTREBOOT",
        PowerFlags.HardReboot: "PS3 HARDREBOOT",
    }

    def __init__(self, conn: _Connection):
        self._c = conn

    def GetFirmwareVersion(self) -> int:
        return self._c.cmd_int("PS3 GETFWVERSION")

    def GetFirmwareVersion_Str(self) -> str:
        return _ver_str(self.GetFirmwareVersion())

    def GetFirmwareType(self) -> str:
        return self._c.cmd("PS3 GETFWTYPE")

    def Power(self, flag: int) -> None:
        """flag: one of PowerFlags.* - disconnects automatically on success."""
        self._c.send_command(self._POWER_CMDS[flag])
        self._c._check_ok()
        self._c.disconnect()

    def Notify(self, msg: str) -> None:
        self._c.cmd(f"PS3 NOTIFY  {msg}")

    def RingBuzzer(self, mode: int) -> None:
        """mode: one of BuzzerMode.*"""
        self._c.cmd(f"PS3 BUZZER{mode}")

    def Led(self, color: int, mode: int) -> None:
        """color: LedColor.*, mode: LedMode.*"""
        self._c.cmd(f"PS3 LED {int(color)} {int(mode)}")

    def GetTemperature(self) -> tuple[int, int]:
        """Returns (cpu, rsx) temperatures."""
        cpu, rsx = self._c.cmd("PS3 GETTEMP").split("|")
        return int(cpu), int(rsx)

    def DisableSyscall(self, num: int) -> None:
        self._c.cmd(f"PS3 DISABLESYSCALL {num}")

    def CheckSyscall(self, num: int) -> bool:
        return self._c.cmd_int(f"PS3 CHECKSYSCALL {num}") == 0

    def PartialDisableSyscall8(self, mode: int) -> None:
        """mode: one of Syscall8Mode.* (Enabled / Only_* / FakeDisabled)"""
        self._c.cmd(f"PS3 PDISABLESYSCALL8 {int(mode)}")

    def PartialCheckSyscall8(self) -> int:
        v = self._c.cmd_int("PS3 PCHECKSYSCALL8")
        return {
            0: Syscall8Mode.Enabled,
            1: Syscall8Mode.Only_CobraMambaAndPS3MAPI_Enabled,
            2: Syscall8Mode.Only_PS3MAPI_Enabled,
        }.get(v, Syscall8Mode.FakeDisabled)

    def RemoveHook(self) -> None:
        self._c.cmd("PS3 REMOVEHOOK")

    def ClearHistory(self, include_directory: bool = True) -> None:
        self._c.cmd("PS3 DELHISTORY+D" if include_directory else "PS3 DELHISTORY")

    def GetPSID(self) -> str:
        return self._c.cmd("PS3 GETPSID")

    def SetPSID(self, psid: str) -> None:
        self._c.cmd(f"PS3 SETPSID {psid[0:16]} {psid[16:32]}")

    def GetIDPS(self) -> str:
        return self._c.cmd("PS3 GETIDPS")

    def SetIDPS(self, idps: str) -> None:
        self._c.cmd(f"PS3 SETIDPS {idps[0:16]} {idps[16:32]}")


class _MemoryCmd:
    def __init__(self, conn: _Connection):
        self._c = conn

    def Get(self, pid: int, address: int, length: int) -> bytes:
        """Read `length` bytes from `pid`'s memory at `address`."""
        return self._c.memory_get(pid, address, length)

    def Set(self, pid: int, address: int, data: bytes) -> None:
        """Write `data` bytes into `pid`'s memory at `address`."""
        self._c.memory_set(pid, address, data)


class _ModulesCmd:
    def __init__(self, conn: _Connection):
        self._c = conn

    def GetPrxIdModules(self, pid: int) -> list[int]:
        resp = self._c.cmd(f"MODULE GETALLPRXID {pid}")
        return [int(x) for x in resp.split("|") if x.strip() not in ("", "0")]

    def GetName(self, pid: int, prxid: int) -> str:
        return self._c.cmd(f"MODULE GETNAME {pid} {prxid}")

    def GetFilename(self, pid: int, prxid: int) -> str:
        return self._c.cmd(f"MODULE GETFILENAME {pid} {prxid}")

    def Load(self, pid: int, path: str) -> None:
        self._c.cmd(f"MODULE LOAD {pid} {path}")

    def Unload(self, pid: int, prxid: int) -> None:
        self._c.cmd(f"MODULE UNLOAD {pid} {prxid}")


class _ProcessCmd:
    def __init__(self, conn: _Connection):
        self._c = conn
        self.Memory = _MemoryCmd(conn)
        self.Modules = _ModulesCmd(conn)
        self.Process_Pid = 0

    def GetPidProcesses(self) -> list[int]:
        resp = self._c.cmd("PROCESS GETALLPID")
        return [int(x) for x in resp.split("|") if x.strip() not in ("", "0")]

    def GetName(self, pid: int) -> str:
        return self._c.cmd(f"PROCESS GETNAME {pid}")


class _VSHPluginsCmd:
    def __init__(self, conn: _Connection):
        self._c = conn

    def Load(self, slot: int, path: str) -> None:
        self._c.cmd(f"MODULE LOADVSHPLUG {slot} {path}")

    def Unload(self, slot: int) -> None:
        self._c.cmd(f"MODULE UNLOADVSHPLUGS {slot}")

    def GetInfoBySlot(self, slot: int) -> tuple[str, str]:
        """Returns (name, path)."""
        name, path = self._c.cmd(f"MODULE GETVSHPLUGINFO {slot}").split("|")
        return name, path


# --------------------------------------------------------------------------
# Top level facade - this is what you actually `import` and use.
# --------------------------------------------------------------------------

class PS3MAPI:
    """Drop-in equivalent of the original PS3MAPI C# class.

    Sub-objects mirror the original API 1:1:
        .Server, .Core, .PS3, .Process (.Process.Memory / .Process.Modules), .VSH_Plugin
    """

    def __init__(self):
        self._conn = _Connection()
        self.Server = _ServerCmd(self._conn)
        self.Core = _CoreCmd(self._conn)
        self.PS3 = _PS3Cmd(self._conn)
        self.Process = _ProcessCmd(self._conn)
        self.VSH_Plugin = _VSHPluginsCmd(self._conn)
        self.PS3M_API_PC_LIB_VERSION = PS3M_API_PC_LIB_VERSION

    def GetLibVersion_Str(self) -> str:
        return _ver_str(self.PS3M_API_PC_LIB_VERSION)

    @property
    def IsConnected(self) -> bool:
        return self._conn.is_connected

    @property
    def IsAttached(self) -> bool:
        return self.Process.Process_Pid != 0

    @property
    def Log(self) -> str:
        return self._conn.log

    def ConnectTarget(self, ip: str | None = None, port: int = 7887) -> bool:
        """Connect to the PS3MAPI server. If `ip` is omitted, prompts on the console
        (replacement for the original WinForms ConnectDialog)."""
        if ip is None:
            ip = input("PS3 IP address: ").strip()
            p = input(f"Port [{port}]: ").strip()
            if p:
                port = int(p)
        self._conn.connect(ip, port)
        return True

    def AttachProcess(self, pid: int | None = None) -> bool:
        """Attach to a running process by PID. If `pid` is omitted, lists
        running processes and prompts for a choice on the console
        (replacement for the original WinForms AttachDialog)."""
        if pid is None:
            pids = self.Process.GetPidProcesses()
            if not pids:
                raise PS3MAPIError("No processes found on target.")
            names = [self.Process.GetName(p) for p in pids]
            for i, (p, n) in enumerate(zip(pids, names)):
                print(f"[{i}] {p:#010x}  {n}")
            choice = int(input("Select process index to attach: ").strip())
            pid = pids[choice]
        self.Process.Process_Pid = pid
        return True

    def DisconnectTarget(self) -> None:
        try:
            self._conn.disconnect()
        except Exception:
            pass

    def ShowLog(self) -> None:
        """No GUI in this port - just prints the accumulated protocol log."""
        print(self.Log)

    # context-manager convenience: `with PS3MAPI() as ps3: ...`
    def __enter__(self) -> "PS3MAPI":
        return self

    def __exit__(self, *exc) -> None:
        self.DisconnectTarget()