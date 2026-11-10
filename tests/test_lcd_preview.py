"""Live LCD preview: the Python port draws exactly what the firmware's renderer draws."""
import unittest
from datetime import datetime
from pathlib import Path
from PIL import Image
from x68 import firmware_source, lcd_preview

ROOT = Path(__file__).resolve().parents[1]


class LcdPreviewTests(unittest.TestCase):
    def test_every_lavender_build_has_a_preview(self):
        for name in firmware_source.BUILDS.values():
            if name:
                self.assertIn(name, lcd_preview.FEATURES)

    def test_matches_the_reference_frame_rendered_from_the_c_source(self):
        # assets/pixel/lcd-preview.png comes from tools/build_native_screen.py (host build of native_screen.c):
        # 01:17:42 on 20/10, 12-hour mode, battery 42 %, Windows mode, unlocked, first animation phase.
        reference = Image.open(ROOT / 'assets/pixel/lcd-preview.png').convert('RGB').tobytes()
        try:
            stock = firmware_source.stock(ROOT / 'firmware-cache', download=False)
        except (OSError, ValueError):
            stock = None
        for source in ([None, stock] if stock else [None]):
            bg = lcd_preview.background(firmware_source.PATCHES / 'lavender-quest-0.9.2.json', source)
            frame = lcd_preview.render('lavender-quest-0.9.2', bg, datetime(2026, 10, 20, 1, 17, 42), twelve=True, battery=42, phase=0)
            mine = lcd_preview.to_rgb(frame)
            different = sum(1 for i in range(0, len(mine), 3) if max(abs(mine[i + k] - reference[i + k]) for k in range(3)) > 8)
            if source:
                self.assertEqual(different, 0)  # with the official payload cached the preview is pixel-exact
            else:
                self.assertLessEqual(different, 100)  # 100 background bytes equal stock; those pixels come from a neighbour

    def test_builds_draw_their_own_header_and_clock(self):
        moment = datetime(2026, 11, 10, 13, 5, 30)
        frames = {}
        for build in lcd_preview.FEATURES:
            bg = lcd_preview.background(firmware_source.PATCHES / f'{build}.json')
            frames[build] = lcd_preview.render(build, bg, moment, twelve=True, mac=True, locked=True)
        self.assertEqual(frames['lavender-quest-0.5.1'], frames['lavender-quest-0.6.0'])
        self.assertNotEqual(frames['lavender-quest-0.6.0'], frames['lavender-quest-0.8.0'])  # 12-hour clock
        self.assertNotEqual(frames['lavender-quest-0.8.0'], frames['lavender-quest-0.9.0'])  # WIN/MAC text
        self.assertNotEqual(frames['lavender-quest-0.9.0'], frames['lavender-quest-0.9.1'])  # badges
        self.assertNotEqual(frames['lavender-quest-0.9.1'], frames['lavender-quest-0.9.2'])  # logo colours, no rail

    def test_lock_and_mode_change_the_frame(self):
        bg = lcd_preview.background(firmware_source.PATCHES / 'lavender-quest-0.9.2.json')
        moment = datetime(2026, 11, 10, 9, 0, 0)
        states = {lcd_preview.render('lavender-quest-0.9.2', bg, moment, mac=m, locked=l) for m in (False, True) for l in (False, True)}
        self.assertEqual(len(states), 4)


if __name__ == '__main__':
    unittest.main()
