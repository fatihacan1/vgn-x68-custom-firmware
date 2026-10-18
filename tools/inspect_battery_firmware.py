"""Offline evidence checks for the exact official X68 V0113 payload.

Reads a file only. Does not import hidapi, execute vendor code or flash a device.
Instruction encodings: Andes binutils patch 145934 (2025-11-26).
Addresses are runtime addresses; RAM-resident source offsets are distinct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

PAYLOAD_SHA256 = '791ae619fb2d7dbe44203192bd42b07073029701ad9ad6363032176559136273'


def signed(value, width):
    return value-(1 << width) if value & (1 << (width-1)) else value


def gp_byte_offset(word):
    """Andes LBGP/LBUGP/ADDIGP immediate, signed 18 bits."""
    value = ((word >> 14) & 1) | (((word >> 21) & 1023) << 1)
    value |= ((word >> 20) & 1) << 11
    value |= ((word >> 17) & 7) << 12
    value |= ((word >> 15) & 3) << 15
    value |= ((word >> 31) & 1) << 17
    return signed(value, 18)


def andes_bit_branch(word, address):
    if word & 0x4000707f not in (0x705b, 0x4000705b):
        raise ValueError('Not a supported Andes bit branch')
    offset = (((word >> 8) & 15) << 1) | (((word >> 25) & 31) << 5)
    offset |= ((word >> 31) & 1) << 10
    return {'when': 'set' if word & 0x40000000 else 'clear',
            'register': (word >> 15) & 31, 'bit': (word >> 20) & 31,
            'target': f'{address+signed(offset, 11):08X}'}


def auipc_jalr_target(first, second, address):
    if first & 127 != 0x17 or second & 127 != 0x67:
        raise ValueError('Not AUIPC/JALR')
    if (first >> 7) & 31 != (second >> 15) & 31:
        raise ValueError('AUIPC/JALR register mismatch')
    return (address+signed(first & 0xfffff000, 32)+signed(second >> 20, 12)) & 0xfffffffe


def inspect(payload):
    digest = hashlib.sha256(payload).hexdigest()
    if digest != PAYLOAD_SHA256:
        raise ValueError('Payload differs from the investigated official V0113. No address claims made.')
    expected = {
        'battery_dispatch_entry': (0x1e794, '0c ba 01 20'),
        'cached_level_load': (0x1ba10, '0b 07 00 37'),
        'gpio_e_read': (0x1ba1c, '03 87 07 32'),
        'gpio_e_bit4_branch': (0x1ba20, '5b 74 47 40'),
        'gpio_c_read': (0x1ba28, '83 87 07 31'),
        'gpio_c_bit3_branch': (0x1ba2c, '5b f4 37 40'),
        'status_zero_store': (0x1bf2c, 'a3 04 04 00'),
        'full_override_constant': (0x1c118, '93 07 40 26'),
        'full_override_halfword_store': (0x1c11c, '23 14 f4 00'),
        'level_write': (0x10674, '0b 38 80 36'),
        'level_scale_100': (0x1055c, '13 04 40 06'),
        'level_interpolation_multiply': (0x106a8, '33 84 87 02'),
        'level_interpolation_divide': (0x106ae, '33 47 e4 02'),
        'level_zero_below_threshold': (0x107dc, '01 44'),
        'startup_adc_call': (0x82a0, '97 80 00 20 e7 80 40 1f'),
        'periodic_adc_call': (0x84f0, '97 80 00 20 e7 80 40 fa'),
        'native_status_gpio_e': (0x84a8, '03 87 07 32'),
        'native_status_gpio_c': (0x84b0, '83 87 07 31'),
        'native_status_debounced_one': (0x8642, '85 47 23 80 f5 00'),
        'native_status_debounced_two': (0x864e, '89 47 23 80 f5 00'),
        'native_icon_status_load': (0x1a0fc, '0b 67 00 50'),
        'native_icon_status_one_branch': (0x1a118, '5b 50 17 08'),
        'native_icon_status_two_branch': (0x1a11c, '5b 58 27 02'),
        'native_icon_level_load': (0x1a120, '8b 27 00 37'),
        'adc_gpio_c_gate': (0x10754, '83 87 07 31 5b fc 37 a6'),
        'adc_previous_level_load': (0x1075c, '0b 16 00 0d 83 47 36 00'),
        'adc_previous_level_clamp': (0x10764, '63 74 f4 04 3e 84'),
        'adc_pd1_gpio_function': (0x81c0, '93 e7 27 00 23 0f fd 30'),
        'adc_pd1_output_disabled': (0x81dc, '93 e7 27 00 23 0d fd 30'),
        'adc_pd1_output_latch_low': (0x81e8, '93 f7 d7 0f a3 0d fd 30'),
        'adc_mux_pd1_ground': (0x8204, '93 05 f0 0a 13 05 b0 0e ef 90 0f ec'),
        'adc_upper_threshold': (0x8224, '93 07 30 7f 23 94 f4 00'),
        'adc_lower_threshold': (0x822c, '93 07 60 5e 23 95 f4 00'),
    }
    checks = {}
    for name, (offset, expected_hex) in expected.items():
        raw = bytes.fromhex(expected_hex)
        actual = payload[offset:offset+len(raw)]
        if actual != raw:
            raise ValueError(f'Evidence mismatch: {name}')
        checks[name] = {'payload_offset': f'{offset:08X}', 'bytes': actual.hex(' ')}
    word = lambda offset: struct.unpack_from('<I', payload, offset)[0]
    branches = [andes_bit_branch(word(offset), 0x20000000+offset)
                for offset in (0x1ba20, 0x1ba2c)]
    # Boot code copies source [0x12B0,0xA0B4) to RAM [0x1200,0xA004).
    callers = [{'payload_offset': f'{offset:08X}', 'runtime_address': f'{offset-0xb0:08X}',
                'target': f'{auipc_jalr_target(word(offset), word(offset+4), offset-0xb0):08X}'}
               for offset in (0x82a0, 0x84f0)]
    return {'payload_sha256': digest, 'payload_bytes': len(payload),
            'stored_crc': f'{word(len(payload)-4):08X}', 'checks': checks,
            'computed_unfinalized_crc32': f'{zlib.crc32(payload[:-4]) ^ 0xffffffff:08X}',
            'crc32_matches': (zlib.crc32(payload[:-4]) ^ 0xffffffff) == word(len(payload)-4),
            'cached_level_gp_offset': gp_byte_offset(word(0x1ba10)),
            'gpio_branches': branches, 'adc_callers': callers,
            'full_override_bytes': '64 02',
            'native_display': {
                'status_gp_offset': '0x501',
                'hid_and_native_status_numbers_are_different': True,
                'status_two_bypasses_cached_level_for_icon': True,
                'icon_renderer_call_site': '2001A14C',
                'note': 'A GPIO-selected icon is not an independent measurement of charge.',
            },
            'level_filter': {
                'condition': 'PE4 set, PC3 set, and earlier control flow reaches 0x20010754',
                'behavior': 'Calculated level can be clamped to the previous level at gp+0xD3.',
                'limit': 'This is a displayed-level filter, not evidence of a charge-disable output.',
            },
            'adc_boot_configuration': {
                'positive_input': 'PD1', 'negative_input': 'GND',
                'analog_register_EB_value': 'AF',
                'pd1_output_disabled': True,
                'lower_threshold_code_units': 1510,
                'upper_threshold_code_units': 2035,
                'limit': 'Static initialization only. No live mux readback, board routing or charger-enable identification.',
            },
            'limits': ['Static evidence only; no independent device flash readback.',
                       'GPIO physical functions and charging current are not established.',
                       'No charging repair is claimed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = inspect(args.payload.read_bytes())
    data = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding='utf-8')
    print(data)


if __name__ == '__main__':
    main()
