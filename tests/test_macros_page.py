"""Macros page: examples are valid, errors are explained, the key picker and battery chart behave."""
import tkinter as tk, unittest
from unittest.mock import Mock, patch
from x68.desktop import MACRO_EXAMPLES, Studio
from x68.settings import PHYSICAL_KEY_INDICES, encode_key, keymap_entries, compile_macro
from x68.battery import decode_battery


class MacroPageTests(unittest.TestCase):
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

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.close()

    def connect(self, macros=()):
        mapping = bytearray(384)
        for name, index in PHYSICAL_KEY_INDICES.items():
            mapping[index * 3:index * 3 + 3] = encode_key(name)
        self.app.show_settings({'lighting': None, 'keys': keymap_entries(bytes(mapping)), 'macros': list(macros)})
        self.app.submit.reset_mock()  # show_settings starts a version read; only count what the test does

    def test_every_example_compiles(self):
        for name, script in MACRO_EXAMPLES:
            self.assertTrue(compile_macro(script), name)

    def test_example_fills_the_editor_and_is_checked(self):
        a = self.app; a.use_example('WIN+D')
        self.assertEqual(a.editor.get('1.0', 'end').strip(), 'WIN+D'); self.assertIn('valid', a.macro_check.get())

    def test_mistakes_are_explained_with_the_line_number(self):
        a = self.app
        a.editor.delete('1.0', 'end'); a.editor.insert('1.0', 'CTRL+C\nCTLR+V'); a.check_macro()
        self.assertIn('Line 2', a.macro_check.get()); self.assertIn('CTLR', a.macro_check.get())
        a.editor.delete('1.0', 'end'); a.editor.insert('1.0', 'WAIT abc'); a.check_macro()
        self.assertIn('WAIT 100', a.macro_check.get())

    def test_key_picker_lists_keys_and_picks_a_free_slot(self):
        a = self.app
        self.connect([{'slot': 1, 'events': 4, 'block_hex': compile_macro('CTRL+C').hex()}])
        self.assertIn('Ins', a.macro_choices)
        self.assertIn('Shift (right)', a.macro_choices)
        a.macro_key.set('Ins'); a.pick_macro_key()
        self.assertEqual(a.selected, a.lookup('INSERT'))
        self.assertEqual(a.slot.get(), 2)
        self.assertIn('Ins', a.macro_save_button['text']); self.assertIn('INSERT', a.macro_key_note.get())

    def test_save_needs_a_key_and_a_valid_macro(self):
        a = self.app; self.connect(); a.selected = None
        a.save_macro(); a.submit.assert_not_called(); self.assertIn('step 3', a.macro_note.get())
        a.macro_key.set('Ins'); a.pick_macro_key()
        a.editor.delete('1.0', 'end'); a.editor.insert('1.0', 'NOPE'); a.save_macro()
        a.submit.assert_not_called()
        a.use_example('CTRL+C'); a.save_macro()
        a.submit.assert_called_once()

    def test_save_asks_first_outside_tests(self):
        a = self.app; self.connect(); a.macro_key.set('Ins'); a.pick_macro_key(); a.smoke = False
        with patch('x68.desktop.messagebox.askokcancel', return_value=False) as ask:
            a.save_macro()
        ask.assert_called_once(); a.submit.assert_not_called(); a.smoke = True


class BatteryChartTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.app = Studio(self.root, smoke=True)
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.close()

    def texts(self):
        c = self.app.chart
        return [c.itemcget(item, 'text') for item in c.find_all() if c.type(item) == 'text']

    def test_empty_chart_explains_what_to_do(self):
        self.app.draw_chart()
        self.assertTrue(any('No readings yet' in text for text in self.texts()))

    def test_level_chart_has_scale_line_and_times(self):
        a = self.app
        for minute in range(3):
            a.history.record(sample={'observed_at': f'2026-11-10T12:0{minute}:00+03:00', 'transport': 'available', **decode_battery(bytes([0, 1, 0, 0, 0, 0]))})
        a.draw_chart()
        texts = self.texts()
        self.assertIn('100 %', texts); self.assertIn('0 %', texts)
        self.assertIn('12:00:00', texts); self.assertIn('12:02:00', texts)
        self.assertTrue(any(a.chart.type(item) == 'line' for item in a.chart.find_all()))


if __name__ == '__main__':
    unittest.main()
