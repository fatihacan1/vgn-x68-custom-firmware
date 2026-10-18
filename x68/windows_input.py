"""Focused-window Windows Raw Input. Never hooks other apps' keystrokes."""
from __future__ import annotations

import ctypes as C
import os
import queue
from ctypes import wintypes as W

MODIFIER_VKEYS = {"38": 0xA4, "E0:38": 0xA5, "1D": 0xA2, "E0:1D": 0xA3,
                  "2A": 0xA0, "36": 0xA1, "E0:5B": 0x5B, "E0:5C": 0x5C}


def reconcile_pressed(pressed: set[str], foreground: bool, modifier_states: dict[str, bool]) -> set[str]:
    """Visual state only: never invent a raw key-up or alter event counts."""
    if not foreground:
        return set()
    return {key for key in pressed if modifier_states.get(key, True)}


def normalize_path(path: str) -> str:
    """Match the physical HID collection, not its Windows interface class.

    hidapi uses GUID_DEVINTERFACE_HID (4D1E55B2...), whereas Raw Input names
    keyboard collections with GUID_DEVINTERFACE_KEYBOARD (884B96C3...).
    The prefix retains VID/PID, MI/COL and the complete PnP instance identity.
    """
    value = path.upper()
    value = value[:-4] if value.endswith("\\KBD") else value
    return value.split("#{", 1)[0]


class RawKeyboard:
    def __init__(self, root, paths: list[str], events: queue.Queue):
        if os.name != "nt":
            raise RuntimeError("The key tester needs Windows Raw Input.")
        self.events = events
        self.paths = {normalize_path(p) for p in paths}
        self.active = False
        self.sources = {}
        self.user32 = C.WinDLL("user32", use_last_error=True)
        self.hwnd = None
        self.previous = None
        self.callback = None
        self.registered = False
        self._configure()
        root.update_idletasks()
        self.hwnd = self.user32.GetAncestor(root.winfo_id(), 2)
        self.callback = self.WNDPROC(self._wndproc)
        C.set_last_error(0)
        self.previous = self.user32.SetWindowLongPtrW(self.hwnd, -4, C.cast(self.callback, C.c_void_p))
        if not self.previous:
            raise C.WinError(C.get_last_error())
        rid = self.RID(1, 6, 0, self.hwnd)  # no INPUTSINK: foreground only
        if not self.user32.RegisterRawInputDevices(C.byref(rid), 1, C.sizeof(rid)):
            error = C.get_last_error()
            self.user32.SetWindowLongPtrW(self.hwnd, -4, self.previous)
            self.previous = None
            raise C.WinError(error)
        self.registered = True

    def _configure(self):
        class RID(C.Structure):
            _fields_ = [("page", W.USHORT), ("usage", W.USHORT), ("flags", W.DWORD), ("target", W.HWND)]
        class HEADER(C.Structure):
            _fields_ = [("type", W.DWORD), ("size", W.DWORD), ("device", W.HANDLE), ("param", W.WPARAM)]
        class KEYBOARD(C.Structure):
            _fields_ = [("scan", W.USHORT), ("flags", W.USHORT), ("reserved", W.USHORT),
                        ("vk", W.USHORT), ("message", W.UINT), ("extra", W.ULONG)]
        self.RID, self.HEADER, self.KEYBOARD = RID, HEADER, KEYBOARD
        self.WNDPROC = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
        api = self.user32
        api.GetAncestor.argtypes = [W.HWND, W.UINT]
        api.GetAncestor.restype = W.HWND
        api.SetWindowLongPtrW.argtypes = [W.HWND, C.c_int, C.c_void_p]
        api.SetWindowLongPtrW.restype = C.c_void_p
        api.CallWindowProcW.argtypes = [C.c_void_p, W.HWND, W.UINT, W.WPARAM, W.LPARAM]
        api.CallWindowProcW.restype = C.c_ssize_t
        api.GetRawInputData.argtypes = [W.HANDLE, W.UINT, C.c_void_p, C.POINTER(W.UINT), W.UINT]
        api.GetRawInputData.restype = W.UINT
        api.GetRawInputDeviceInfoW.argtypes = [W.HANDLE, W.UINT, C.c_void_p, C.POINTER(W.UINT)]
        api.GetRawInputDeviceInfoW.restype = W.UINT
        api.RegisterRawInputDevices.argtypes = [C.POINTER(RID), W.UINT, W.UINT]
        api.RegisterRawInputDevices.restype = W.BOOL
        api.GetForegroundWindow.argtypes = []
        api.GetForegroundWindow.restype = W.HWND
        api.GetAsyncKeyState.argtypes = [C.c_int]
        api.GetAsyncKeyState.restype = C.c_short

    def visual_state(self):
        foreground = self.user32.GetForegroundWindow() == self.hwnd
        states = {key: bool(self.user32.GetAsyncKeyState(vk) & 0x8000)
                  for key, vk in MODIFIER_VKEYS.items()} if foreground else {}
        return foreground, states

    def _source_matches(self, handle) -> bool:
        if handle not in self.sources:
            length = W.UINT()
            self.user32.GetRawInputDeviceInfoW(handle, 0x20000007, None, C.byref(length))
            if not 0 < length.value < 4096:
                return False
            buffer = C.create_unicode_buffer(length.value + 1)
            result = self.user32.GetRawInputDeviceInfoW(handle, 0x20000007, buffer, C.byref(length))
            self.sources[handle] = result != 0xFFFFFFFF and normalize_path(buffer.value) in self.paths
        return self.sources[handle]

    def _wndproc(self, hwnd, message, wparam, lparam):
        try:
            if message == 0xFF and self.active:
                size = W.UINT()
                hs = C.sizeof(self.HEADER)
                self.user32.GetRawInputData(lparam, 0x10000003, None, C.byref(size), hs)
                if hs + C.sizeof(self.KEYBOARD) <= size.value < 65536:
                    buffer = C.create_string_buffer(size.value)
                    read = self.user32.GetRawInputData(lparam, 0x10000003, buffer, C.byref(size), hs)
                    if read == size.value:
                        header = self.HEADER.from_buffer_copy(buffer)
                        if header.type == 1 and self._source_matches(header.device):
                            key = self.KEYBOARD.from_buffer_copy(buffer, hs)
                            if key.scan != 255 and key.vk != 255:
                                self.events.put({"scan": key.scan, "extended": bool(key.flags & 2),
                                                 "released": bool(key.flags & 1), "vk": key.vk})
        except Exception as error:
            self.events.put({"error": str(error)})
        return self.user32.CallWindowProcW(self.previous, hwnd, message, wparam, lparam)

    def close(self):
        self.active = False
        if self.registered:
            rid = self.RID(1, 6, 1, None)  # RIDEV_REMOVE
            self.user32.RegisterRawInputDevices(C.byref(rid), 1, C.sizeof(rid))
            self.registered = False
        if self.previous:
            self.user32.SetWindowLongPtrW(self.hwnd, -4, self.previous)
            self.previous = None
