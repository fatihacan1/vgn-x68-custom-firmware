"""Host-side safeguards for long device writes (firmware install, LCD media upload).

Windows only; elsewhere these are no-ops so the app behaves exactly as before.
"""
from __future__ import annotations

import sys

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def on_battery_power() -> bool:
    """True when Windows reports the computer is running on battery (AC unplugged)."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class SystemPowerStatus(ctypes.Structure):
            _fields_ = [('ac_line', wintypes.BYTE), ('battery_flag', wintypes.BYTE),
                        ('battery_percent', wintypes.BYTE), ('system_status', wintypes.BYTE),
                        ('battery_life', wintypes.DWORD), ('battery_full_life', wintypes.DWORD)]

        status = SystemPowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return False
        return status.ac_line == 0  # 0 = offline (battery), 1 = online, 255 = unknown
    except Exception:
        return False


def keep_awake(enabled: bool) -> bool:
    """Ask Windows not to sleep while a device write runs. Call again with False when it ends."""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if enabled else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False
