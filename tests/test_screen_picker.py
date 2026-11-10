"""Screen picker: shows the active screen mode and only switches to the image when one was uploaded."""
import tkinter as tk, unittest
from unittest.mock import Mock


def block(mode, frames):
    data = bytearray(64); data[33] = mode; data[34] = frames
    return {'lighting': {'mode': 1, 'brightness': 4, 'speed': 2, 'color': '#b9a6ea', 'rainbow_raw': 0,
                         'raw_hex': data.hex(' ')}, 'keys': [], 'macros': []}


class ScreenPickerTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        from x68.desktop import Studio
        self.app = Studio(self.root, smoke=True)
        for timer in self.root.tk.call('after', 'info'):
            self.root.after_cancel(timer)
        self.app.submit = Mock()
        self.app.version = {'reported_crc': '5B2F5C6D'}  # Lavender Quest 0.9.2

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.close()

    def test_active_mode_is_shown_after_reading_settings(self):
        a = self.app; a.settings = block(4, 3); a.show_screen_mode()
        self.assertIn('screen 4', a.screen_mode_note.get())
        a.settings = block(2, 3); a.show_screen_mode()
        self.assertIn('clock scene', a.screen_mode_note.get())

    def test_image_button_needs_an_uploaded_image(self):
        a = self.app; a.settings = block(0, 0)
        a.change_screen(4)
        a.submit.assert_not_called(); self.assertIn('Upload', a.status.get())
        a.settings = block(0, 2)
        a.change_screen(4)
        a.submit.assert_called_once()

    def test_clock_button_always_allowed_on_lavender(self):
        a = self.app; a.settings = block(4, 0)
        a.change_screen(0)
        a.submit.assert_called_once()


    def test_each_screen_has_its_own_fit_and_changing_it_reconverts(self):
        from PIL import Image
        from x68.media import PreparedMedia
        a = self.app; a.save_preferences = Mock(); a.screen_slots = [None] * 4  # ignore choices saved on this PC
        a.screen_media_ready(1, PreparedMedia('sample.png', [Image.new('RGB', (160, 96))], 100, 1, 100, 'Crop'))
        a.submit.reset_mock()
        a.slot_fit[0].set('Fit'); a.submit.assert_not_called()  # empty screen: nothing to convert
        a.slot_fit[1].set('Stretch'); a.submit.assert_called_once()
        self.assertEqual(a.submit.call_args.args[0], 'Converting image')

if __name__ == '__main__':
    unittest.main()
