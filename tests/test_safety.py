"""Safety guards: risky device writes need an explicit, informed confirmation."""
import sys, tkinter as tk, unittest
from unittest.mock import Mock, patch
from x68 import safety
from x68.desktop import Studio


class SafetyModuleTests(unittest.TestCase):
    def test_non_windows_is_a_no_op(self):
        with patch.object(sys, 'platform', 'linux'):
            self.assertFalse(safety.on_battery_power())
            self.assertFalse(safety.keep_awake(True))


class SafetyGuardTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.app = Studio(self.root, smoke=True)
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.app.submit = Mock()
        # The root is withdrawn, so dialogs are unviewable; never let a modal wait hang the suite.
        self.root.report_callback_exception = lambda *error: self.close_dialogs()
        self.root.after(5000, self.close_dialogs)

    def close_dialogs(self):
        for widget in self.root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.flashing = False
            self.app.close()

    def test_install_refuses_without_a_usb_connection(self):
        a = self.app; a.confirm_checklist = Mock(return_value=True); a.inventory = None
        a.install()
        a.submit.assert_not_called(); a.confirm_checklist.assert_not_called()
        self.assertIn('USB', a.status.get())

    def test_install_refuses_over_the_wireless_receiver(self):
        a = self.app; a.confirm_checklist = Mock(return_value=True); a.inventory = {'transport': 'wireless'}
        a.install()
        a.submit.assert_not_called(); a.confirm_checklist.assert_not_called()
        self.assertIn('USB cable', a.status.get())

    def test_install_stops_when_the_checklist_is_cancelled(self):
        a = self.app; a.confirm_checklist = Mock(return_value=False); a.inventory = {'transport': 'usb'}; a.version = {'reported_crc': '14961BE6'}
        a.install()
        a.confirm_checklist.assert_called_once()
        self.assertEqual(len(a.confirm_checklist.call_args.args[2]), 4)
        a.submit.assert_not_called(); self.assertFalse(a.flashing)

    def test_install_is_blocked_on_unrecognised_keyboard_firmware(self):
        a = self.app; a.confirm_checklist = Mock(return_value=True); a.inventory = {'transport': 'usb'}
        a.version = {'reported_crc': '475FA496'}
        a.install()
        a.confirm_checklist.assert_not_called(); a.submit.assert_not_called()
        self.assertIn('475FA496', a.status.get()); self.assertIn('blocked', a.status.get())

    def test_v0112_keyboard_is_told_to_update_to_v0113_first(self):
        a = self.app; a.confirm_checklist = Mock(return_value=True)
        a.inventory = {'transport': 'usb', 'usb_release_hex': '0112'}; a.version = {'reported_crc': '475FA496'}
        a.install()
        a.confirm_checklist.assert_not_called(); a.submit.assert_not_called()
        self.assertIn('V0112', a.status.get()); self.assertIn('V0113', a.status.get())
        a.show_version({'reported_crc': '475FA496'})
        self.assertIn('V0112', a.firmware_note.get())

    def test_install_needs_the_installed_version_first(self):
        a = self.app; a.confirm_checklist = Mock(return_value=True); a.inventory = {'transport': 'usb'}; a.version = None
        a.install()
        a.confirm_checklist.assert_not_called(); a.submit.assert_not_called()

    def test_unrecognised_version_explains_on_the_firmware_page(self):
        a = self.app; a.inventory = {'transport': 'usb'}
        a.show_version({'reported_crc': '475FA496'})
        self.assertIn('blocked', a.firmware_note.get())

    def test_checklist_confirm_stays_disabled_until_every_box_is_ticked(self):
        a = self.app; seen = {}

        def interact():
            dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
            body = dialog.winfo_children()[0]
            boxes = [w for w in body.winfo_children() if isinstance(w, tk.Checkbutton)]
            go = [w for w in body.winfo_children() if isinstance(w, tk.Frame)][-1].winfo_children()[-1]
            seen['before'] = go['state']
            for box in boxes[:-1]:
                box.invoke()
            seen['partial'] = go['state']
            boxes[-1].invoke()
            seen['after'] = go['state']
            go.invoke()

        self.root.after(50, interact)
        self.assertTrue(a.confirm_checklist('Install firmware', 'intro', ['a', 'b', 'c'], 'Install'))
        self.assertEqual((seen['before'], seen['partial'], seen['after']), ('disabled', 'disabled', 'normal'))

    def test_closing_the_checklist_window_cancels(self):
        def close_window():
            dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel))
            self.assertTrue(dialog.bind('<Escape>'))
            dialog.tk.call(dialog.protocol('WM_DELETE_WINDOW'))
        self.root.after(50, close_window)
        self.assertFalse(self.app.confirm_checklist('Install firmware', 'intro', ['a'], 'Install'))

    def test_unreviewed_option_switches_back_off_when_declined(self):
        a = self.app; a.allow_unreviewed.set(True)
        with patch('x68.desktop.messagebox.askyesno', return_value=False) as ask:
            a.unreviewed_toggled()
        ask.assert_called_once(); self.assertFalse(a.allow_unreviewed.get())

    def test_restore_asks_before_overwriting_settings(self):
        a = self.app
        with patch('x68.desktop.filedialog.askopenfilename', return_value='backup.json'), \
             patch('x68.desktop.messagebox.askokcancel', return_value=False) as ask:
            a.restore()
        ask.assert_called_once(); a.submit.assert_not_called()

    def test_closing_during_a_transfer_is_refused(self):
        a = self.app; a.flashing = True
        a.close()
        self.assertFalse(a.closed); self.assertIn('Wait', a.status.get())

    def test_lithium_warning_only_with_jump_start_steps(self):
        a = self.app
        a.show_battery_warning(True); self.assertEqual(a.battery_warning.winfo_manager(), 'pack')
        a.show_battery_warning(False); self.assertEqual(a.battery_warning.winfo_manager(), '')


if __name__ == '__main__':
    unittest.main()
