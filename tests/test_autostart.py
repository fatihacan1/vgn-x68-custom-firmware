"""Login-startup files are isolated from the real user's login configuration."""
import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from x68 import autostart


class MacStartupTests(unittest.TestCase):
    def test_enable_and_disable_bundle_startup_without_starting_duplicate_process(self):
        with tempfile.TemporaryDirectory() as folder:
            agent=Path(folder)/'LaunchAgents'/('com.vgn-x68.custom-firmware.plist')
            with patch.object(sys,'platform','darwin'),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable','/Applications/VGN X68 Custom Firmware.app/Contents/MacOS/VGN-X68-Custom-Firmware-0.9.2-macOS'),patch.object(autostart,'_agent_path',return_value=agent),patch.object(autostart.subprocess,'run') as run:
                self.assertFalse(autostart.enabled());autostart.configure(True)
                data=plistlib.loads(agent.read_bytes())
                self.assertEqual(data['ProgramArguments'],['/usr/bin/open','-a','/Applications/VGN X68 Custom Firmware.app'])
                self.assertTrue(data['RunAtLoad']);self.assertNotIn('KeepAlive',data)
                self.assertTrue(autostart.enabled());run.assert_not_called()
                autostart.configure(False);self.assertFalse(agent.exists());self.assertFalse(autostart.enabled())

    def test_invalid_plist_is_not_enabled(self):
        with tempfile.TemporaryDirectory() as folder:
            agent=Path(folder)/'broken.plist';agent.write_text('broken')
            with patch.object(sys,'platform','darwin'),patch.object(autostart,'_agent_path',return_value=agent):
                self.assertFalse(autostart.enabled())
