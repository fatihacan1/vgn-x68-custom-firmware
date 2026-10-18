import unittest
from tools.inspect_battery_firmware import gp_byte_offset, andes_bit_branch, auipc_jalr_target, inspect


class FirmwareEvidenceTests(unittest.TestCase):
    def test_level_load_gp_offset(self):
        self.assertEqual(gp_byte_offset(0x3700070b), 0x370)

    def test_gpio_branches(self):
        branch = andes_bit_branch(0x4047745b, 0x2001ba20)
        self.assertEqual(branch, {'when': 'set', 'register': 14, 'bit': 4, 'target': '2001BA28'})
        self.assertEqual(andes_bit_branch(0x4037f45b, 0x2001ba2c)['target'], '2001BA34')

    def test_calls_must_use_relocated_ram_pc(self):
        self.assertEqual(auipc_jalr_target(0x20008097, 0x1f4080e7, 0x81f0), 0x200103e4)
        self.assertEqual(auipc_jalr_target(0x20008097, 0xfa4080e7, 0x8440), 0x200103e4)

    def test_unknown_payload_cannot_inherit_known_address_claims(self):
        with self.assertRaises(ValueError):
            inspect(bytes(236916))

    def test_unknown_instruction_patterns_are_rejected(self):
        with self.assertRaises(ValueError):
            andes_bit_branch(0, 0)
        with self.assertRaises(ValueError):
            auipc_jalr_target(0, 0, 0)
