import struct
import unittest

from x68.protocol import ProtocolError
from x68.settings import (settings_packet, encode_lighting, compile_macro, parse_macro_bank,
                          replace_macro, macro_text, keymap_entries, HID_KEYS, encode_key)


class SettingsTests(unittest.TestCase):
    def test_packet_bounds_exclude_firmware_and_unknown_commands(self):
        for cmd in (0, 4, 10, 11, 0xAA, 0xFC):
            with self.subTest(cmd=cmd), self.assertRaises(ProtocolError):
                settings_packet(cmd, data=b'\x00')
        with self.assertRaises(ProtocolError):
            settings_packet(21, 4090, data=bytes(7))
        with self.assertRaises(ProtocolError):
            settings_packet(8, 380, size=5)

    def test_unsigned_checksum_and_boundaries(self):
        packet = settings_packet(9, 330, data=bytes([113, 15, 255]))
        self.assertEqual(len(packet), 64)
        self.assertEqual(packet[5:8], bytes([74, 1, 0]))
        self.assertEqual(int.from_bytes(packet[1:3], 'little'), sum(packet[3:]))

    def test_lighting_preserves_every_unrelated_byte(self):
        original = bytearray(range(64))
        original[1:4] = bytes([4, 4, 4])
        original[5] = 0
        actual = encode_lighting(bytes(original), 6, 2, 1, False, '#ff0080')
        self.assertEqual(actual[1:4], bytes([6, 2, 3]))
        self.assertEqual(actual[6:9], bytes([255, 0, 128]))
        for index in set(range(64)) - {1, 2, 3, 5, 6, 7, 8}:
            self.assertEqual(actual[index], original[index])

    def test_unknown_rainbow_flag_is_preserved_without_inventing_its_meaning(self):
        from x68.settings import decode_lighting
        original=bytearray(64)
        original[1:4]=bytes([6,4,2]);original[5]=255
        self.assertIsNone(decode_lighting(bytes(original))['rainbow'])
        actual=encode_lighting(bytes(original),6,3,2,None,'#b69bcb')
        self.assertEqual(actual[5],255)
        self.assertEqual(actual[2],3)

    def test_macro_chord_contains_balanced_modifier_and_key_events(self):
        block = compile_macro('CTRL+C\nWAIT 150\nCTRL+V')
        events = [struct.unpack_from('<HBB', block, p) for p in range(4, len(block), 4)]
        self.assertEqual(events[:4], [(0, 137, 1), (20, 138, 6), (20, 10, 6), (20, 9, 1)])
        self.assertEqual(events[4][0], 170)
        self.assertEqual(block[:4], b'\x08\x00\x35\x00')

    def test_original_device_mouse_macro_roundtrips_events(self):
        block = bytes.fromhex('02 00 a0 ae 4e 00 81 01 00 00 01 01')
        result = compile_macro(macro_text(block))
        self.assertEqual(result[4:], block[4:])

    def test_macro_rejects_stuck_keys_invalid_delays_and_unknown_input(self):
        for text in ('DOWN CTRL', 'UP A', 'WAIT -1\nA', 'WAIT 65536\nA', 'RUN calc.exe', 'A\n'*46):
            with self.subTest(text=text), self.assertRaises(ProtocolError):
                compile_macro(text)

    def test_replace_macro_preserves_other_slots_and_reserved_header(self):
        old = compile_macro('CTRL+C')
        header = bytearray(b'\xaa\x55'+bytes(14))
        header[6:16] = b'preserveME'
        struct.pack_into('<HH', header, 2, 18+len(old), 1)
        bank = bytes(header)+b'\x12\x00'+old
        new = replace_macro(bank, 2, compile_macro('CTRL+V'))
        blocks = parse_macro_bank(new)
        self.assertEqual(new[6:16], bank[6:16])
        self.assertEqual(blocks[0], old)
        self.assertEqual(blocks[1], b'\x00\x00\x35\x00')
        self.assertEqual(blocks[2], compile_macro('CTRL+V'))

    def test_invalid_existing_bank_prevents_replacement(self):
        with self.assertRaises(ProtocolError):
            replace_macro(bytes(4096), 0, compile_macro('A'))

    def test_f13_to_f24_use_hid_usages_and_decode_back(self):
        self.assertEqual([HID_KEYS[f"F{i}"] for i in range(13, 25)], list(range(0x68, 0x74)))
        data = bytearray(384)
        data[0:3] = bytes([32, 0, HID_KEYS["F17"]])
        self.assertEqual(keymap_entries(bytes(data))[0]["name"], "F17")
        self.assertIn(bytes([138, HID_KEYS["F17"]]), compile_macro("F17"))

    def test_fn_and_reserved_cells_are_not_editable(self):
        mapping = bytearray(384)
        mapping[90*3:90*3+3] = b'\xa0\x01\x00'
        mapping[81*3:81*3+3] = b'\x20\x08\x00'
        entries = keymap_entries(bytes(mapping))
        self.assertFalse(entries[90]['editable'])
        self.assertEqual(entries[90]['name'], 'Fn')
        self.assertTrue(entries[81]['editable'])
        self.assertEqual(entries[81]['name'], 'WIN')

    def test_media_actions_use_consumer_encoding_and_remain_editable(self):
        for name, expected in [('Play / Pause', '30 cd 00'), ('Previous Track', '30 b6 00'),
                               ('Next Track', '30 b5 00'), ('Mute', '30 e2 00'),
                               ('Volume Down', '30 ea 00'), ('Volume Up', '30 e9 00')]:
            with self.subTest(name=name):
                encoded=encode_key(name.lower())
                self.assertEqual(encoded,bytes.fromhex(expected))
                mapping=bytearray(384);mapping[56*3:57*3]=encoded
                entry=keymap_entries(bytes(mapping))[56]
                self.assertEqual(entry['name'],name);self.assertTrue(entry['editable'])
                mapping[:3]=encoded
                self.assertFalse(keymap_entries(bytes(mapping))[0]['editable'])

    def test_unknown_consumer_actions_and_invalid_formats_stay_protected(self):
        for encoded in (b'\x30\x00\x00',b'\x30\xcd\x01',b'\x30\xff\x00'):
            mapping=bytearray(384);mapping[56*3:57*3]=encoded
            self.assertFalse(keymap_entries(bytes(mapping))[56]['editable'])


if __name__ == '__main__':
    unittest.main()
