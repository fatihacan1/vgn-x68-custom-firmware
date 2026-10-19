import hashlib,tempfile,unittest
from pathlib import Path
from x68 import firmware_source as fs

LIB=Path(__file__).resolve().parents[1]/'firmware-library'
STOCK=LIB/'stock-v0113.bin'

class PatchFormatTests(unittest.TestCase):
 def test_patch_refuses_any_other_base(self):
  with self.assertRaises(ValueError):fs.apply_patch(bytes(fs.V0113_SIZE),'lavender-quest-0.6.0')
 def test_payload_search_rejects_lookalikes(self):
  fake=bytes(100)+bytes(0x20)+b'KNLT'+bytes(fs.V0113_SIZE)
  with self.assertRaises(ValueError):fs.find_payload(fake)
 def test_patches_ship_no_large_vendor_runs(self):
  # Patches carry only changed bytes; every build stays far below the 236,916-byte image.
  import json
  for name in ('lavender-quest-0.9.0','lavender-quest-0.8.0','lavender-quest-0.6.0','lavender-quest-0.5.1'):
   patch=json.loads((fs.PATCHES/f'{name}.json').read_text())
   self.assertLess(sum(len(r[1])//2 for r in patch['runs']),fs.V0113_SIZE//3)

@unittest.skipUnless(STOCK.exists(),'Local verified stock binary is required')
class LocalBuildTests(unittest.TestCase):
 def test_patched_builds_match_reviewed_images(self):
  stock=STOCK.read_bytes()
  for name,file in (('lavender-quest-0.9.0','lavender-quest-090.bin'),('lavender-quest-0.8.0','lavender-quest-080.bin'),('lavender-quest-0.6.0','lavender-quest-060.bin'),('lavender-quest-0.5.1','lavender-quest.bin')):
   self.assertEqual(fs.apply_patch(stock,name),(LIB/file).read_bytes())
 def test_payload_found_inside_wrapper_and_cached(self):
  stock=STOCK.read_bytes();wrapper=b'MZ'+bytes(51993)+stock+b'tail'
  with tempfile.TemporaryDirectory() as tmp:
   (Path(tmp)/'updater.exe').write_bytes(wrapper)
   self.assertEqual(fs.import_file(Path(tmp),Path(tmp)/'updater.exe'),stock)
   self.assertEqual(fs.stock(Path(tmp),download=False),stock)
