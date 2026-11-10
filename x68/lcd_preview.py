"""Live LCD preview for each Lavender Quest build.

A line-for-line Python port of firmware/native_screen.c render() as it was at
each release (0.6.0 4244ba0, 0.8.0 2b7436e, 0.9.0 a9d69ce, 0.9.1 67b82bd,
0.9.2 1f76ae4; 0.5.1 draws the same screen as 0.6.0). The background is the
build's own 160x96 RGB565 image at payload 0x31664, taken from the
firmware-patches JSON (only bytes this project wrote). If the official V0113
payload is cached, the few background bytes that equal stock are exact too;
otherwise they are filled from the neighbouring pixel.

Display only: no device I/O.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

WIDTH, HEIGHT = 160, 96
FRAME = WIDTH * HEIGHT * 2
BG_START, BG_END = 0x31664, 0x38E64

# What each build draws beyond the 0.5.1 base screen.
FEATURES = {
    'lavender-quest-0.5.1': {'twelve': False, 'header': None},
    'lavender-quest-0.6.0': {'twelve': False, 'header': None},
    'lavender-quest-0.8.0': {'twelve': True, 'header': None},
    'lavender-quest-0.9.0': {'twelve': True, 'header': 'text'},
    'lavender-quest-0.9.1': {'twelve': True, 'header': 'badges', 'win': (0x55ff, 0x7f7b, 0x3598, 0x4e9f), 'rail': True},
    'lavender-quest-0.9.2': {'twelve': True, 'header': 'badges', 'win': (0xed3d, 0xb79a, 0xacdd, 0xf691), 'rail': False},
    'lavender-quest-0.10.0': {'twelve': True, 'header': 'badges', 'win': (0xed3d, 0xb79a, 0xacdd, 0xf691), 'rail': False},
}

NUMBERS = ((14, 17, 19, 21, 25, 17, 14), (4, 12, 4, 4, 4, 4, 14), (14, 17, 1, 2, 4, 8, 31), (30, 1, 1, 14, 1, 1, 30),
           (2, 6, 10, 18, 31, 2, 2), (31, 16, 16, 30, 1, 1, 30), (14, 16, 16, 30, 17, 17, 14), (31, 1, 2, 4, 8, 8, 8),
           (14, 17, 17, 14, 17, 17, 14), (14, 17, 17, 15, 1, 1, 14))
ALPHABET = 'ACFIKLMNOW:'
GLYPHS = ((14, 17, 17, 31, 17, 17, 17), (15, 16, 16, 16, 16, 16, 15), (31, 16, 16, 30, 16, 16, 16), (14, 4, 4, 4, 4, 4, 14),
          (17, 18, 20, 24, 20, 18, 17), (16, 16, 16, 16, 16, 16, 31), (17, 27, 21, 21, 17, 17, 17), (17, 25, 21, 19, 17, 17, 17),
          (14, 17, 17, 17, 17, 17, 14), (17, 17, 17, 21, 21, 27, 17), (0, 4, 4, 0, 4, 4, 0))
APPLE = (24, 48, 0, 476, 1022, 2044, 2032, 2032, 2044, 1022, 508, 216)
AM_PM_M = ((14, 17, 17, 31, 17, 17, 17), (30, 17, 17, 30, 16, 16, 16), (17, 27, 21, 21, 17, 17, 17))


def background(patch_file: Path, stock: bytes | None = None) -> bytes:
    """The build's background image (RGB565, high byte first)."""
    patch = json.loads(Path(patch_file).read_text(encoding='utf-8'))
    data = bytearray(stock[BG_START:BG_END]) if stock and len(stock) >= BG_END else bytearray(FRAME)
    known = bytearray(FRAME) if not stock else None
    for offset, hex_bytes in patch['runs']:
        chunk = bytes.fromhex(hex_bytes)
        start, end = max(offset, BG_START), min(offset + len(chunk), BG_END)
        if end > start:
            data[start - BG_START:end - BG_START] = chunk[start - offset:end - offset]
            if known is not None:
                known[start - BG_START:end - BG_START] = b'\x01' * (end - start)
    if known is not None:  # Without the stock payload, fill the few unpatched pixels from the left neighbour.
        for i in range(0, FRAME, 2):
            if not (known[i] and known[i + 1]) and i >= 2:
                data[i:i + 2] = data[i - 2:i]
    return bytes(data)


class _Screen:
    def __init__(self, bg: bytes):
        self.fb = bytearray(bg)

    def pixel(self, x, y, color):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            n = (y * WIDTH + x) * 2
            self.fb[n] = (color >> 8) & 255
            self.fb[n + 1] = color & 255

    def digit(self, n, x, y, scale, color):
        if not 0 <= n <= 9:
            return
        for row in range(7):
            for col in range(5):
                if NUMBERS[n][row] & (16 >> col):
                    for dy in range(scale):
                        for dx in range(scale):
                            self.pixel(x + col * scale + dx, y + row * scale + dy, color)

    def pair(self, value, x, y, scale, color):
        self.digit(value // 10, x, y, scale, color)
        self.digit(value % 10, x + 6 * scale, y, scale, color)

    def label(self, text, x, y, color):
        for ch in text:
            if ch in ALPHABET:
                glyph = GLYPHS[ALPHABET.index(ch)]
                for row in range(7):
                    for col in range(5):
                        if glyph[row] & (16 >> col):
                            self.pixel(x + col, y + row, color)
            x += 6


def render(build: str, bg: bytes, moment: datetime, twelve=False, mac=False, locked=False, battery=100, phase=0) -> bytes:
    """One 160x96 RGB565 frame, as the build's render() would draw it. phase counts quarter seconds."""
    features = FEATURES[build]
    s = _Screen(bg)
    hour24 = moment.hour
    twelve = twelve and features['twelve']
    hour = (hour24 % 12 or 12) if twelve else hour24

    header = features['header']
    if header == 'text':
        s.label('MAC' if mac else 'WIN', 64, 3, 0xb79b)
        s.label('L:ON' if locked else 'L:OFF', 88, 3, 0xf6b1 if locked else 0xd6ba)
    elif header == 'badges':
        if mac:
            for y in range(12):
                for x in range(11):
                    if APPLE[y] & (1024 >> x):
                        s.pixel(4 + x, 3 + y, 0xf7bf)
        else:
            a, b, c, d = features['win']
            for y in range(9):
                for x in range(9):
                    if x != 4 and y != 4:
                        s.pixel(5 + x, 5 + y, (a if x < 4 else b) if y < 4 else (c if x < 4 else d))
        s.label('MAC' if mac else 'WIN', 86, 6, 0xf7bf if mac else 0xb79b)
        if features.get('rail'):
            for y in range(6, 13):
                s.pixel(78, y, 0xd65f if mac else 0x7f7b)
        body, shine = (0xf6b1, 0xff7b) if locked else (0xb79b, 0xdffd)
        for y in range(9, 16):
            for x in range(132, 143):
                s.pixel(x, y, body)
        for x in range(133, 142):
            s.pixel(x, 9, shine)
        s.pixel(132, 15, 0x3929); s.pixel(142, 15, 0x3929)
        shackle = 134 if locked else 140
        for x in range(shackle + 1, shackle + 6):
            s.pixel(x, 4, shine)
        for y in range(5, 9):
            s.pixel(shackle, y, shine); s.pixel(shackle + 6, y, shine)
        for x, y in ((137, 11), (138, 11), (137, 12), (138, 12), (137, 13)):
            s.pixel(x, y, 0x3929)
        for x, y in ((125, 9), (126, 9), (125, 10), (126, 10)):
            s.pixel(x, y, body)

    s.pair(hour, 10, 24, 2, 0xf7bf); s.pair(moment.minute, 39, 24, 2, 0xf7bf)
    s.pixel(35, 28, 0x7f7b); s.pixel(35, 33, 0x7f7b)
    s.pair(moment.second, 67, 31, 1, 0x7f7b)
    if twelve:
        for row in range(7):
            for col in range(5):
                if AM_PM_M[1 if hour24 >= 12 else 0][row] & (16 >> col):
                    s.pixel(85 + col, 31 + row, 0x7f7b)
                if AM_PM_M[2][row] & (16 >> col):
                    s.pixel(91 + col, 31 + row, 0x7f7b)
    s.pair(moment.day, 108, 24, 1, 0xe51f); s.pair(moment.month, 127, 24, 1, 0xe51f)
    s.pixel(122, 27, 0xe51f); s.pixel(121, 28, 0xe51f); s.pixel(120, 29, 0xe51f)
    if phase % 16 < 2:  # eye blink
        for x, y, c in ((107, 57, 0xb79b), (112, 57, 0xb79b), (106, 58, 0x20c6), (107, 58, 0x20c6), (111, 58, 0x20c6), (112, 58, 0x20c6)):
            s.pixel(x, y, c)
    if phase & 1:  # scarf flutter
        s.pixel(117, 62, 0x1712); s.pixel(118, 62, 0x1712); s.pixel(117, 60, 0xed3b); s.pixel(118, 60, 0xed3b)
    for y in range(62, 69):  # spinning coin
        for x in range(132, 136):
            s.pixel(x, y, 0x10a5)
    half = 2 if phase % 4 == 0 else (0 if phase % 4 == 2 else 1)
    for y in range(63, 68):
        for x in range(133 - half, 134 + half):
            s.pixel(x, y, 0xf6b1)

    level = battery
    for y in range(86, 95):
        for x in range(53, 107):
            s.pixel(x, y, 0x6a90)
    ink = 0xb79b if level <= 100 else 0xc638
    for x in range(55, 68):
        s.pixel(x, 87, ink); s.pixel(x, 93, ink)
    for y in range(87, 94):
        s.pixel(55, y, ink); s.pixel(67, y, ink)
    for y in range(89, 92):
        s.pixel(68, y, ink)
    if level <= 100:
        for y in range(89, 92):
            for x in range(57, 57 + level * 9 // 100):
                s.pixel(x, y, ink)
        if level == 100:
            s.digit(1, 72, 87, 1, ink)
        s.digit((level // 10) % 10, 78, 87, 1, ink); s.digit(level % 10, 84, 87, 1, ink)
    else:
        for x in range(78, 89):
            if x < 82 or x > 84:
                s.pixel(x, 90, ink)
    s.pixel(91, 87, ink); s.pixel(92, 88, ink); s.pixel(95, 92, ink); s.pixel(96, 93, ink)
    for i in range(5):
        s.pixel(96 - i, 87 + i, ink)
    return bytes(s.fb)


def to_rgb(frame: bytes) -> bytes:
    """RGB565 (high byte first) to 8-bit RGB."""
    out = bytearray(WIDTH * HEIGHT * 3)
    for i in range(WIDTH * HEIGHT):
        v = (frame[2 * i] << 8) | frame[2 * i + 1]
        out[3 * i] = ((v >> 11) & 31) * 255 // 31
        out[3 * i + 1] = ((v >> 5) & 63) * 255 // 63
        out[3 * i + 2] = (v & 31) * 255 // 31
    return bytes(out)
