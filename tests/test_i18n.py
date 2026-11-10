"""Turkish catalogue coverage: every display string passed to t() has a translation."""
import ast, json, string, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from x68 import i18n

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / 'x68/desktop.py', ROOT / 'x68/battery_health.py']


def literals(node):
    """String constants reachable from a t() argument, including both sides of a conditional."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.IfExp):
        yield from literals(node.body)
        yield from literals(node.orelse)
    elif isinstance(node, ast.BinOp):
        yield from literals(node.left)
        yield from literals(node.right)


def used_strings():
    found = set()
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
            # t('...'), plus operation names given to submit(), which are shown via t(name).
            if name in ('t', 'submit'):
                found.update(literals(node.args[0]))
    return found


def fields(text):
    return {field for _, field, _, _ in string.Formatter().parse(text) if field}


class CatalogueTests(unittest.TestCase):
    def test_every_display_string_has_a_turkish_entry(self):
        from x68.desktop import EFFECTS, PAGES
        from x68.battery_health import VERDICTS
        wanted = used_strings() | set(EFFECTS) | set(PAGES)
        for _, _, headline, steps in VERDICTS:
            wanted |= {headline, *steps}
        missing = sorted(text for text in wanted if text not in i18n.TR)
        self.assertEqual(missing, [])

    def test_placeholders_match(self):
        for english, turkish in i18n.TR.items():
            self.assertEqual(fields(english), fields(turkish), english)

    def test_turkish_upper_case_keeps_dotted_i(self):
        self.assertEqual(i18n.upper('Bilgi', 'tr'), 'BİLGİ')
        self.assertEqual(i18n.upper('Işık', 'tr'), 'IŞIK')
        self.assertEqual(i18n.upper('Lighting', 'en'), 'LIGHTING')
        self.assertEqual(i18n.pixel_caps('BİLGİ'), 'BILGI')

    def test_unknown_text_falls_back_to_english(self):
        self.assertEqual(i18n.t('Not in the catalogue', 'tr'), 'Not in the catalogue')
        self.assertEqual(i18n.t('Lighting', 'en'), 'Lighting')

    def test_saved_preference_wins_over_system_language(self):
        previous = i18n.LANG
        try:
            with tempfile.TemporaryDirectory() as folder, patch.object(i18n, 'system_language', return_value='en'):
                prefs = Path(folder) / 'preferences.json'
                prefs.write_text(json.dumps({'language': 'tr'}), encoding='utf-8')
                self.assertEqual(i18n.load(prefs), 'tr')
                prefs.write_text(json.dumps({'language': 'xx'}), encoding='utf-8')
                self.assertEqual(i18n.load(prefs), 'en')
                self.assertEqual(i18n.load(Path(folder) / 'missing.json'), 'en')
        finally:
            i18n.LANG = previous


if __name__ == '__main__':
    unittest.main()
