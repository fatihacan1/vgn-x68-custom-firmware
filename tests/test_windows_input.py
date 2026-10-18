import unittest

from x68.windows_input import normalize_path, reconcile_pressed


class DevicePathTests(unittest.TestCase):
    def test_actual_x68_hid_and_raw_input_paths_match(self):
        hid = r'\\?\HID#VID_320F&PID_5055&MI_01&Col01#8&23f1b54b&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}\KBD'
        raw = r'\\?\HID#VID_320F&PID_5055&MI_01&Col01#8&23f1b54b&0&0000#{884b96c3-56ef-11d1-bc8c-00a0c91405dd}'
        self.assertEqual(normalize_path(hid), normalize_path(raw))

    def test_actual_x68_boot_keyboard_paths_match(self):
        hid = r'\\?\HID#VID_320F&PID_5055&MI_00#8&10c1990d&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}\KBD'
        raw = r'\\?\HID#VID_320F&PID_5055&MI_00#8&10c1990d&0&0000#{884b96c3-56ef-11d1-bc8c-00a0c91405dd}'
        self.assertEqual(normalize_path(hid), normalize_path(raw))

    def test_other_keyboard_is_still_excluded(self):
        x68 = r'\\?\HID#VID_320F&PID_5055&MI_00#8&10c1990d&0&0000#{HID}'
        logitech = r'\\?\HID#VID_046D&PID_C548&MI_00#9&3b6bb3b1&0&0000#{KEYBOARD}'
        self.assertNotEqual(normalize_path(x68), normalize_path(logitech))

    def test_same_vid_pid_different_pnp_instance_is_excluded(self):
        first = r'\\?\HID#VID_320F&PID_5055&MI_00#8&10c1990d&0&0000#{HID}'
        other = r'\\?\HID#VID_320F&PID_5055&MI_00#8&DIFFERENT&0&0000#{KEYBOARD}'
        self.assertNotEqual(normalize_path(first), normalize_path(other))


class PressedDisplayTests(unittest.TestCase):
    def test_lost_focus_clears_alt_and_other_highlights(self):
        self.assertEqual(reconcile_pressed({'38', '1E'}, False, {}), set())

    def test_missed_alt_release_is_reconciled_with_windows(self):
        pressed = {'38', '1D', '1E'}
        result = reconcile_pressed(pressed, True, {'38': False, '1D': True})
        self.assertEqual(result, {'1D', '1E'})
        self.assertEqual(pressed, {'38', '1D', '1E'})

    def test_real_held_alt_stays_highlighted(self):
        self.assertEqual(reconcile_pressed({'38'}, True, {'38': True}), {'38'})

    def test_reconciliation_does_not_add_other_keyboard_modifiers(self):
        self.assertEqual(reconcile_pressed(set(), True, {'38': True}), set())

    def test_other_collection_is_not_conflated(self):
        first = r'\\?\HID#VID_320F&PID_5055&MI_01&COL01#8&23f1b54b&0&0000#{HID}'
        other = r'\\?\HID#VID_320F&PID_5055&MI_01&COL04#8&23f1b54b&0&0000#{KEYBOARD}'
        self.assertNotEqual(normalize_path(first), normalize_path(other))


if __name__ == '__main__':
    unittest.main()
