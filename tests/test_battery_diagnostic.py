import unittest
from unittest.mock import Mock
from x68.battery_diagnostic import decode_snapshot,query_snapshot
from x68.protocol import ProtocolError
from x68.settings import settings_packet

def sample(count=1000,upper=4200,lower=3200):
 data=bytearray(48);data[:4]=b'XBD\x01';data[10:12]=bytes([4,1])
 for i in range(12,28,2):data[i:i+2]=count.to_bytes(2,'little')
 data[28:30]=(8192).to_bytes(2,'little');data[32:34]=upper.to_bytes(2,'little');data[34:36]=lower.to_bytes(2,'little');return data
class DiagnosticTests(unittest.TestCase):
 def test_exact_native_math_distinguishes_filter_from_under_threshold(self):
  value=decode_snapshot(sample())
  self.assertEqual(value['scaled_code_units'],4000);self.assertEqual(value['unfiltered_firmware_indicator'],80)
  self.assertEqual(value['cached_indicator'],0);self.assertIsNone(value['physical_voltage_mv']);self.assertFalse(value['charging_verified'])
 def test_full_override_applies_only_above_lower_threshold(self):
  data=sample(500);data[8]=2
  self.assertEqual(decode_snapshot(data)['unfiltered_firmware_indicator'],0)
  data=sample();data[8]=2;self.assertEqual(decode_snapshot(data)['unfiltered_firmware_indicator'],100)
 def test_zero_samples_are_not_fake_voltage_or_charge(self):
  result=decode_snapshot(sample(0));self.assertTrue(result['all_adc_samples_zero'])
  self.assertEqual(result['unfiltered_firmware_indicator'],0);self.assertIsNone(result['charging_current_ma'])
 def test_guard_rejects_other_firmware_without_any_io(self):
  settings=Mock()
  with self.assertRaises(ProtocolError):query_snapshot(settings,{'reported_crc':'14961BE6'})
  settings._device.assert_not_called()
 def test_packet_size_and_signature_guards(self):
  for size in (1,47,49):
   with self.assertRaises(ProtocolError):settings_packet(25,size=size)
  for raw in (bytes(48),b'XBD\x01'):
   with self.assertRaises(ProtocolError):decode_snapshot(raw)
