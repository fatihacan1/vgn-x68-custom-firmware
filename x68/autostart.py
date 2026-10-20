"""Opt-in, current-user login startup on Windows and macOS."""
import sys
import subprocess
import plistlib
from pathlib import Path

KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'VGN X68 Custom Firmware'
LABEL = 'com.vgn-x68.custom-firmware'

def _agent_path():
    return Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')

def _mac_arguments():
    exe = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        for parent in exe.parents:
            if parent.suffix == '.app':
                # Launch the bundle through Launch Services, preserving its privacy identity.
                return ['/usr/bin/open', '-a', str(parent)]
        raise OSError('Install the app in Applications before enabling login startup.')
    return [str(exe), str(Path(__file__).resolve().parents[1] / 'app.py')]

def enabled():
    if sys.platform == 'darwin':
        try:
            with _agent_path().open('rb') as stream:
                agent = plistlib.load(stream)
            return isinstance(agent,dict) and agent.get('Label') == LABEL and agent.get('RunAtLoad') is True
        except (OSError, ValueError, plistlib.InvalidFileException):
            return False
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
    if sys.platform == 'darwin':
        path = _agent_path()
        if enable:
            agent = {'Label': LABEL, 'ProgramArguments': _mac_arguments(), 'RunAtLoad': True}
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.plist.tmp')
            try:
                with temporary.open('wb') as stream:
                    plistlib.dump(agent, stream)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        else:
            path.unlink(missing_ok=True)
        # LaunchAgents are loaded at the next login; enabling must not start a duplicate now.
        return
    if sys.platform != 'win32':
        raise OSError('Automatic startup is supported on Windows and macOS.')
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
