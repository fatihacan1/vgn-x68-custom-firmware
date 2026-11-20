"""Lighting preview: every effect animates, follows the light settings, and the send summary is accurate."""
import tkinter as tk, unittest
from unittest.mock import Mock
from x68 import effects
from x68.desktop import EFFECTS, PREVIEW_KEYS, Studio

STATIC = {'Solid', 'Off', 'Custom table'}


def brightness_sum(frame):
    return sum(int(c[i:i + 2], 16) for c in frame.values() for i in (1, 3, 5))


class EffectFrameTests(unittest.TestCase):
    def test_every_effect_has_a_description_and_colours_every_key(self):
        for effect in EFFECTS:
            self.assertIn(effect, effects.DESCRIPTIONS)
            frame = effects.frame(effect, PREVIEW_KEYS, 1.0, '#b9a6ea', True)
            self.assertEqual(set(frame), {key for key, _, _ in PREVIEW_KEYS}, effect)
            self.assertTrue(all(len(c) == 7 and c.startswith('#') for c in frame.values()), effect)

    def test_animated_effects_change_over_time_and_static_ones_do_not(self):
        for effect in EFFECTS:
            for rainbow in (True, False):
                frames = [effects.frame(effect, PREVIEW_KEYS, t, '#b9a6ea', rainbow) for t in (0.4, 1.3, 2.9, 4.1)]
                moving = any(frames[0] != f for f in frames[1:])
                if effect in STATIC:
                    self.assertFalse(moving, (effect, rainbow))
                else:
                    self.assertTrue(moving, (effect, rainbow))

    def test_brightness_and_speed_change_the_preview(self):
        dim = effects.frame('Solid', PREVIEW_KEYS, 1.0, '#ffffff', False, brightness=0)
        full = effects.frame('Solid', PREVIEW_KEYS, 1.0, '#ffffff', False, brightness=4)
        self.assertLess(brightness_sum(dim), brightness_sum(full) / 4)
        slow = effects.frame('Wave', PREVIEW_KEYS, 2.0, '#ffffff', True, speed=0)
        fast = effects.frame('Wave', PREVIEW_KEYS, 2.0, '#ffffff', True, speed=4)
        self.assertNotEqual(slow, fast)

    def test_single_colour_mode_uses_the_chosen_colour(self):
        frame = effects.frame('Solid', PREVIEW_KEYS, 0, '#ff0000', False, brightness=4)
        self.assertEqual(set(frame.values()), {'#ff0000'})

    def test_off_is_dark(self):
        self.assertEqual(set(effects.frame('Off', PREVIEW_KEYS, 3, '#ffffff', True).values()), {'#3b304b'})


class SendSummaryTests(unittest.TestCase):
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

    def test_summary_lists_what_send_writes_and_what_differs(self):
        a = self.app
        a.settings = {'lighting': {'mode': EFFECTS.index('Wave') + 1, 'brightness': 4, 'speed': 2, 'color': '#b9a6ea', 'rainbow_raw': 1}, 'keys': [], 'macros': []}
        a.effect.set('Wave'); a.brightness.set(4); a.speed.set(2); a.color.set('#b9a6ea'); a.rainbow.set('Rainbow')
        self.assertIn('Same as the keyboard', a.lighting_summary.get())
        a.speed.set(4); a.color.set('#ff6f9c')
        summary = a.lighting_summary.get()
        self.assertIn('speed 4/4', summary); self.assertIn('#FF6F9C', summary)
        self.assertIn('speed, colour', summary)
        a.submit.assert_not_called()

    def test_key_draft_says_nothing_is_sent(self):
        a = self.app; a.preview_mode.set('Per-key design draft')
        self.assertIn('never sent', a.lighting_summary.get())

    def test_effect_description_follows_the_selection(self):
        a = self.app; a.effect.set('Rain')
        self.assertIn('Drops of light', a.effect_note.get())


if __name__ == '__main__':
    unittest.main()
