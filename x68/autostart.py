"""Opt-in, current-user Windows login startup. No administrator access."""
import sys
import subprocess
from pathlib import Path

KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'VGN X68 Custom Firmware'

def enabled():
    if sys.platform != 'win32':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            winreg.QueryValueEx(key, NAME)
        return True
    except FileNotFoundError:
        return False

def configure(enable):
    if sys.platform != 'win32':
        raise OSError('Automatic startup is currently supported on Windows.')
    import winreg
    exe = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        args = [str(exe)]
    else:
        pythonw = exe.with_name('pythonw.exe')
        args = [str(pythonw if pythonw.exists() else exe), str(Path(__file__).resolve().parents[1] / 'app.py')]
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        if enable:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, subprocess.list2cmdline(args))
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
