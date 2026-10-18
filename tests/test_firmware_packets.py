import unittest
from unittest.mock import patch
import zlib
from x68.firmware import validate_visual_patch, V0113_SIZE
from x68.firmware import crc16, encode_block, start_packet, packet, result_code, validate_v0113


class FirmwarePacketTests(unittest.TestCase):
    def test_crc_matches_modbus_reference(self):
        self.assertEqual(crc16(b'123456789'), 0x4b37)

    def test_start_matches_original_updater(self):
        self.assertEqual(start_packet(),bytes.fromhex('05 02 02 00 01 ff')+bytes([255])*58)

    def test_block_covers_index_and_all_sixteen_data_bytes(self):
        block = encode_block(257,bytes(range(16)))
        self.assertEqual(block[:2],b'\x01\x01')
        self.assertEqual(block[2:18],bytes(range(16)))
        self.assertEqual(int.from_bytes(block[18:],'little'),crc16(block[:18]))

    def test_only_explicit_success_result_is_success(self):
        self.assertEqual(result_code(bytes.fromhex('05 02 03 00 06 ff 00')+bytes(57)),0)
        self.assertEqual(result_code(bytes.fromhex('05 02 03 00 06 ff 04')+bytes(57)),4)
        self.assertIsNone(result_code(start_packet()))
        self.assertIsNone(result_code(bytes.fromhex('05 02 03 00 06 ff 00')))

    def test_unknown_firmware_and_bad_lengths_refused(self):
        with self.assertRaises(ValueError):validate_v0113(bytes(236916))
        with self.assertRaises(ValueError):packet(bytes(61))
        with self.assertRaises(ValueError):encode_block(0,bytes(15))

    def test_visual_guard_allows_only_assets_and_checksum(self):
        stock=bytes(V0113_SIZE)
        candidate=bytearray(stock)
        candidate[0x27418]=255
        candidate[-4:]=(zlib.crc32(candidate[:-4])^0xffffffff).to_bytes(4,'little')
        with patch('x68.firmware.validate_v0113'):
            validate_visual_patch(candidate,stock)
            candidate[0x1ba10]=1
            candidate[-4:]=(zlib.crc32(candidate[:-4])^0xffffffff).to_bytes(4,'little')
            with self.assertRaisesRegex(ValueError,'code or unverified data'):
                validate_visual_patch(candidate,stock)

    def test_visual_guard_rejects_resizing_and_invalid_checksum(self):
        stock=bytes(V0113_SIZE)
        with patch('x68.firmware.validate_v0113'):
            with self.assertRaisesRegex(ValueError,'size'):
                validate_visual_patch(stock+b'x',stock)
            with self.assertRaisesRegex(ValueError,'checksum'):
                validate_visual_patch(stock,stock)
