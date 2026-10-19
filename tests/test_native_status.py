"""Evidence for native Fn state addresses, against the exact stock image."""
from pathlib import Path
import unittest

from tools.inspect_battery_firmware import gp_byte_offset
from x68.firmware import validate_v0113

STOCK=Path(__file__).resolve().parents[1]/'firmware-cache/stock-v0113.bin'

@unittest.skipUnless(STOCK.exists(),'Local verified stock binary is required')
class NativeStatusEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.data=STOCK.read_bytes();validate_v0113(self.data)
 def test_fn_a_and_s_dispatch_to_the_live_os_parameter(self):
  d=self.data
  self.assertEqual(d[0x1cd1c:0x1cd24],bytes.fromhex('31 a0 43 00 32 a0 43 ff'))
  self.assertEqual(int.from_bytes(d[0x1cb84+0x43*4:0x1cb88+0x43*4],'little'),0x20011ec4)
  self.assertEqual(d[0x11ecc:0x11ed4],bytes.fromhex('8b 97 1f d5 03 c7 b7 01'))
  self.assertEqual(0x80800+gp_byte_offset(int.from_bytes(d[0x11ecc:0x11ed0],'little'))+0x1b,0x8056b)
  self.assertEqual(d[0x11eec:0x11ef0],bytes.fromhex('a3 8d c7 01')) # sb t3,1B(a5)
 def test_fn_win_toggles_the_live_lock_parameter(self):
  d=self.data
  self.assertEqual(d[0x1cd54:0x1cd58],bytes.fromhex('51 a0 04 00'))
  self.assertEqual(int.from_bytes(d[0x1cb94:0x1cb98],'little'),0x20012200)
  self.assertEqual(d[0x1220c:0x12214],bytes.fromhex('8b 97 1f d5 03 c7 57 01'))
  self.assertEqual(0x80800+gp_byte_offset(int.from_bytes(d[0x1220c:0x12210],'little'))+0x15,0x80565)
  self.assertEqual(d[0x12218:0x1221c],bytes.fromhex('a3 8a 07 00')) # sb zero,15(a5)
  self.assertEqual(d[0x12418:0x1241e],bytes.fromhex('7d 57 a3 8a e7 00')) # li a4,-1; sb a4,15(a5)
