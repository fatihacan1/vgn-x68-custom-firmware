import unittest,zlib
from pathlib import Path
from x68.firmware import inspect_custom_firmware,data_packets,end_packet

STOCK=Path(__file__).resolve().parents[1]/'firmware-library/stock-v0113.bin'
@unittest.skipUnless(STOCK.exists(),'Local verified stock binary is required')
class CustomFirmwareTests(unittest.TestCase):
 def setUp(self):self.stock=STOCK.read_bytes()
 def custom(self):
  data=bytearray(self.stock);data[0x11000]^=1;data[-4:]=(zlib.crc32(data[:-4])^0xffffffff).to_bytes(4,'little');return bytes(data)
 def test_unknown_code_is_not_reviewed_and_needs_explicit_encoding_option(self):
  payload=self.custom();record=inspect_custom_firmware(payload,self.stock)
  self.assertFalse(record['reviewed']);self.assertFalse(record['compatibility_proven'])
  with self.assertRaises(ValueError):list(data_packets(payload,self.stock))
  packets=list(data_packets(payload,self.stock,allow_unreviewed=True));self.assertEqual(len(packets),4936)
  self.assertEqual(len(end_packet(payload,self.stock,allow_unreviewed=True)),64)
 def test_invalid_size_header_and_crc_are_refused(self):
  for payload in [self.stock[:-1],b'x'+self.stock[1:],self.stock[:-4]+bytes(4)]:
   with self.assertRaises(ValueError):inspect_custom_firmware(payload,self.stock)
