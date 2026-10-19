"""Offline encoding for the exact official V0113 USB OTA protocol.

No device access in this module. Source: static analysis of official updater
ota_write / crc16 and X68 handlers 0x2001AC4C, 0x2001ACF8, 0x2001AEA4.
"""
from __future__ import annotations

import hashlib
import struct
import zlib

V0113_SHA256 = '791ae619fb2d7dbe44203192bd42b07073029701ad9ad6363032176559136273'
V0113_SIZE = 236916
V0113_CRC = 0x14961be6
VISUAL_RANGES = ((0x26620,0x26900), (0x270b8,0x38e64))
NATIVE_SCREEN_SHA256 = '0ed295763080a581401c40de9c3d87446ca4b03c08bef12961bbd6b96f96f5ac'
NATIVE_RENDERER_SHA256 = '15b6d7a7d9726217791fbe96cbb1bcd47d0b147c37dd0f47156928647515459c'
LIVE_CLOCK_CRC = '10EE7CA9'
BATTERY_DIAGNOSTIC_CRC = '127F9EB4'
CLOCK_FORMAT_CRC = '1383FD83'
DEVICE_STATUS_CRC = '41815162'
CLOCK_FORMAT_CRCS = {CLOCK_FORMAT_CRC, DEVICE_STATUS_CRC}
BATTERY_DIAGNOSTIC_CRCS = {BATTERY_DIAGNOSTIC_CRC, *CLOCK_FORMAT_CRCS}
LIVE_CLOCK_CRCS = {LIVE_CLOCK_CRC, *BATTERY_DIAGNOSTIC_CRCS, '3C866A9B'}
NATIVE_SCREEN_BUILDS = {
    '60090d9b881a7b72cef4d26020a57fa174d74be424f343016de61fb6b14b0742':
        '3fe674cd2f58c14de403b647e7cfbe42523e251637108cb9cb3608c02d99cfa7',
    '4989ee7f2c9f5400ea327090354192772c957315528b9a76346537ebaf730288':
        '2b0be6928321db6cecf09a83344d4f8b5bac335990f612ac70264e46d430647e',
    NATIVE_SCREEN_SHA256: NATIVE_RENDERER_SHA256,
    '861fb1bb65e18f07b74a89448fbdec1fb9eca7655011d2d7e55c34c5d3477c0d':
        '304ed2037060a1cdedaa86e563a2df5c10b997cf4fa2f88484b0c1ea500a345a',
    '995b9f2fb0056297292ba25ba1d6daf967769b0fc45ed279ad864bb9d7bc15b2':
        '688e29cacde5e4b08a39f800261bc4193842e84e6c7f46b0301a63cd561528e4',
    '1ed4b9f2346f36e707088935bb922437945005061742f6e0da88a9a12d84ef67':
        '9d91768e74302f3b0fb86ab8b991441a7110a4ef8c4e859b9e6334487f34bf85',
    '0c7a61e2c48349a618cd198460a5a04f9bade87879385dc90f2bc795c1f06012':
        '6fea23a738f60adc71e44fc2896d1dbabd1839567c040de2eed91de350f28688',
    '4b68724aff8c95cd383af74beb369e0b081ec1f03b7ec508602cf9b428f9aeba':
        '39311eed80f15c90731b2ba81e794c5748cfe40a1b0b0c89f6c780c7229bcc24',
}
NATIVE_RENDERER_SIZE = 4172
NATIVE_HOOK = bytes.fromhex('17 03 02 20 67 00 43 55')


def validate_native_screen(payload, stock):
    """Accept only the reviewed single-screen build, including its exact code."""
    validate_v0113(stock)
    digest = hashlib.sha256(payload).hexdigest()
    if digest not in NATIVE_SCREEN_BUILDS:
        raise ValueError('Unknown native renderer build')
    if payload[0x71c0:0x71c8] != NATIVE_HOOK:
        raise ValueError('Native LCD hook differs')
    size=NATIVE_RENDERER_SIZE if digest in (NATIVE_SCREEN_SHA256,'995b9f2fb0056297292ba25ba1d6daf967769b0fc45ed279ad864bb9d7bc15b2','861fb1bb65e18f07b74a89448fbdec1fb9eca7655011d2d7e55c34c5d3477c0d') else 4166
    if digest == '4989ee7f2c9f5400ea327090354192772c957315528b9a76346537ebaf730288':size=4193
    if digest == '60090d9b881a7b72cef4d26020a57fa174d74be424f343016de61fb6b14b0742':size=4301
    code = payload[0x27664:0x27664+size]
    if hashlib.sha256(code).hexdigest() != NATIVE_SCREEN_BUILDS[digest]:
        raise ValueError('Native renderer differs')
    for index,(old,new) in enumerate(zip(stock[:-4],payload[:-4])):
        if old != new and not (0x71c0 <= index < 0x71c8 or 0x27664 <= index < 0x38e64 or 0x1e78c<=index<0x1e794):
            raise ValueError(f'Native screen changes unrelated code at {index:08X}')
    if len(payload) != len(stock) or (zlib.crc32(payload[:-4])^0xffffffff) != int.from_bytes(payload[-4:],'little'):
        raise ValueError('Native screen size/checksum differs')


def validate_v0113(payload):
    if len(payload) != V0113_SIZE or hashlib.sha256(payload).hexdigest() != V0113_SHA256:
        raise ValueError('Only the unmodified, verified official V0113 payload is accepted.')
    if payload[0x20:0x24] != b'KNLT':
        raise ValueError('Boot mark mismatch')
    if struct.unpack_from('<I', payload, 0x18)[0] != len(payload):
        raise ValueError('Firmware length mismatch')
    crc = zlib.crc32(payload[:-4]) ^ 0xffffffff
    if crc != V0113_CRC or crc != int.from_bytes(payload[-4:], 'little'):
        raise ValueError('Firmware checksum mismatch')


def inspect_custom_firmware(payload,stock):
    """Offline structural checks, never a claim of hardware compatibility."""
    validate_v0113(stock)
    if len(payload)!=V0113_SIZE:raise ValueError(f'Expected a full raw V0113 .bin: {V0113_SIZE} bytes. EXE/HEX/UF2 files are not supported.')
    if payload[:0x100]!=stock[:0x100]:raise ValueError('V0113 boot/header bytes differ. This file is not accepted by this updater.')
    if (zlib.crc32(payload[:-4])^0xffffffff)!=int.from_bytes(payload[-4:],'little'):raise ValueError('Firmware CRC is invalid; no device command was sent.')
    digest=hashlib.sha256(payload).hexdigest()
    reviewed=digest==V0113_SHA256 or digest in NATIVE_SCREEN_BUILDS
    return {'sha256':digest,'crc':payload[-4:][::-1].hex().upper(),'bytes':len(payload),'reviewed':reviewed,'compatibility_proven':reviewed,'format':'V0113 full raw binary'}


def validate_visual_patch(payload, stock):
    """Permit verified default font/logo assets and checksum changes only."""
    validate_v0113(stock)
    if len(payload) != len(stock):
        raise ValueError('Visual patch changed firmware size')
    for index,(old,new) in enumerate(zip(stock[:-4],payload[:-4])):
        if old != new and not any(start <= index < end for start,end in VISUAL_RANGES):
            raise ValueError(f'Visual patch changes code or unverified data at {index:08X}')
    if (zlib.crc32(payload[:-4])^0xffffffff) != int.from_bytes(payload[-4:],'little'):
        raise ValueError('Visual patch checksum mismatch')


def validate_payload(payload, stock_reference=None):
    if stock_reference is None:
        validate_v0113(payload)
    elif hashlib.sha256(payload).hexdigest() in NATIVE_SCREEN_BUILDS:
        validate_native_screen(payload, stock_reference)
    else:
        validate_visual_patch(payload,stock_reference)


def crc16(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return value


def packet(data):
    if not 1 <= len(data) <= 60:
        raise ValueError('Invalid OTA payload length')
    return bytes([5, 2, len(data), 0])+data+bytes([255])*(60-len(data))


def start_packet():
    return packet(bytes.fromhex('01 ff'))


def encode_block(index, data):
    if not 0 <= index < 65535 or len(data) != 16:
        raise ValueError('Invalid firmware block')
    prefix = struct.pack('<H', index)+data
    return prefix+struct.pack('<H', crc16(prefix))


def data_packets(payload, stock_reference=None, allow_unreviewed=False):
    if allow_unreviewed:inspect_custom_firmware(payload,stock_reference)
    else:validate_payload(payload,stock_reference)
    padded = payload+bytes([255])*(-len(payload) % 16)
    count = len(padded)//16
    for first in range(0, count, 3):
        yield packet(b''.join(encode_block(index, padded[index*16:index*16+16])
                              for index in range(first, min(first+3, count))))


def end_packet(payload, stock_reference=None, allow_unreviewed=False):
    if allow_unreviewed:inspect_custom_firmware(payload,stock_reference)
    else:validate_payload(payload,stock_reference)
    last = (len(payload)+15)//16-1
    return packet(bytes.fromhex('02 ff')+struct.pack('<HH', last, (-last) & 0xffff))


def result_code(reply):
    if len(reply) == 64 and reply[:6] == bytes.fromhex('05 02 03 00 06 ff'):
        return reply[6]
    return None
