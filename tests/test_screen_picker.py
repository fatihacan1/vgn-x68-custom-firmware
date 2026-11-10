"""Screen picker: shows the active screen mode and only switches to the image when one was uploaded."""
import tkinter as tk, unittest
from pathlib import Path
from unittest.mock import Mock, patch
from x68.firmware import MULTI_SCREEN_CRC


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

    def gif(self, folder, name, frames):
        from PIL import Image
        path = Path(folder) / name
        images = [Image.new('RGB', (160, 96), (i * 40, 0, 0)) for i in range(frames)]
        images[0].save(path, save_all=True, append_images=images[1:], duration=100, loop=0)
        return str(path)

    def test_multi_build_shows_one_upload_system(self):
        a = self.app; a.version = {'reported_crc': MULTI_SCREEN_CRC}; a.refresh_screen_rows()
        self.assertEqual(a.single_upload.winfo_manager(), ''); self.assertEqual(a.show_image_button.winfo_manager(), '')
        self.assertIn('0 is the clock', a.screen_modes_note.get())
        a.version = {'reported_crc': '5B2F5C6D'}; a.refresh_screen_rows()
        self.assertEqual(a.single_upload.winfo_manager(), 'pack'); self.assertEqual(a.show_image_button.winfo_manager(), 'pack')

    def test_full_frame_budget_is_shared_out_on_request(self):
        import tempfile
        from x68.media import convert_media
        a = self.app; a.save_preferences = Mock(); a.screen_slots = [None] * 4
        a.submit = lambda name, work, done: done(work())
        with tempfile.TemporaryDirectory() as folder:
            a.screen_slots[0] = convert_media(self.gif(folder, 'a.gif', 4), 'Crop', max_frames=4)
            a.screen_slots[1] = convert_media(self.gif(folder, 'b.gif', 4), 'Crop', max_frames=4)
            new = self.gif(folder, 'c.gif', 4)
            with patch('x68.desktop.messagebox.askyesno', return_value=True) as ask, patch('x68.desktop.filedialog.askopenfilename', return_value=new):
                a.choose_screen_media(2)
            ask.assert_called_once()
            self.assertEqual([len(m.frames) for m in a.screen_slots[:3]], [3, 3, 2])
            self.assertLessEqual(a.screen_frames_used(), 8)

    def test_declining_the_share_changes_nothing(self):
        from x68.media import PreparedMedia
        from PIL import Image
        a = self.app; a.save_preferences = Mock(); full = PreparedMedia('x.gif', [Image.new('RGB', (160, 96))] * 8, 100, 8, 800, 'Crop')
        a.screen_slots = [full, None, None, None]
        with patch('x68.desktop.messagebox.askyesno', return_value=False), patch('x68.desktop.filedialog.askopenfilename') as pick:
            a.choose_screen_media(1)
        pick.assert_not_called(); self.assertIs(a.screen_slots[0], full)

    def test_preview_follows_the_screen_on_the_keyboard(self):
        from x68.media import PreparedMedia
        from PIL import Image
        a = self.app; a.version = {'reported_crc': MULTI_SCREEN_CRC}
        media = PreparedMedia('x.gif', [Image.new('RGB', (160, 96))], 100, 1, 100, 'Crop'); a.screen_slots = [None, media, None, None]
        a.settings = block(2, 1); self.assertEqual(a.live_screen_media(), (1, media))
        a.settings = block(3, 1); self.assertIsNone(a.live_screen_media())
        a.settings = block(0, 1); self.assertIsNone(a.live_screen_media())

if __name__ == '__main__':
    unittest.main()
