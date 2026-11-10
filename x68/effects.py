"""On-screen lighting preview: one animation per X68 effect.

The keyboard renders its effects in firmware that is not documented, so these
are approximations drawn from each effect's name and common keyboard
behaviour. They follow the same brightness (0-4), speed (0-4, higher = faster),
colour and rainbow settings that Send writes, so changing a setting changes the
preview immediately. Typing-reactive effects (Reactive, Ripple) are shown with
simulated key presses.

No device I/O here: pure functions, deterministic for a given time.
"""
from __future__ import annotations

import colorsys
import math

WIDTH = 18.0          # keyboard width in key units
CENTRE = (8.5, 2.0)   # roughly the middle of the main block
UNLIT = (0.231, 0.188, 0.294)   # '#3b304b', the preview colour of a dark key
LEVELS = (0.06, 0.3, 0.55, 0.78, 1.0)

# Short descriptions shown under the board (English keys; translated in i18n).
DESCRIPTIONS = {
    'Wave': 'Colours flow across the keyboard from left to right.',
    'Colour cloud': 'Soft clouds of colour drift and blend slowly.',
    'Vortex': 'Colours spin around the centre of the keyboard.',
    'Spectrum': 'The whole keyboard cycles through every colour together.',
    'Breathing': 'Keys slowly fade in and out, like breathing.',
    'Solid': 'Every key stays on one steady colour.',
    'Reactive': 'Only the keys you press light up, then fade away.',
    'Ripple': 'Each key press sends a ring of light outwards.',
    'Trail': 'A light runs across the keys, leaving a fading tail.',
    'Stars': 'Random keys twinkle on and off like stars.',
    'Flowers': 'Patches of colour bloom open and fade, one after another.',
    'Scroll': 'Bands of colour scroll up the keyboard row by row.',
    'Wings': 'Colours spread outwards from the middle to both sides.',
    'Build up': 'Keys light up column by column until the board is full.',
    'Rain': 'Drops of light fall down the keyboard.',
    'Scan': 'A bar of light sweeps from side to side.',
    'Spread': 'Rings of colour keep spreading out from the centre.',
    'Fast wave': 'The wave effect, flowing much faster.',
    'Custom table': 'Plays the per-key colour table stored on the keyboard; shown here as one colour.',
    'Off': 'All lighting is switched off.',
}

# Effects that light only some keys at a time (unlit keys show as dark).
_SPARSE = {'Reactive', 'Ripple', 'Trail', 'Stars', 'Flowers', 'Build up', 'Rain', 'Scan'}


def _noise(*values) -> float:
    """Deterministic 0..1 pseudo-random value (FNV-1a over integers)."""
    h = 2166136261
    for value in values:
        h = ((h ^ (int(value) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    return h / 0xFFFFFFFF


def _rgb(colour: str):
    try:
        return tuple(int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return (0.71, 0.61, 0.80)


def _hex(rgb) -> str:
    return '#' + ''.join(f'{max(0, min(255, round(v * 255))):02x}' for v in rgb)


def _hue(h: float):
    return colorsys.hsv_to_rgb(h % 1.0, 0.72, 1.0)


def _presses(t, rate, keys, every, window):
    """Simulated key presses: (age, key index, slot) for presses in the last `window` seconds."""
    interval = every / rate
    now = int(t // interval)
    found = []
    for slot in range(now - int(window / interval) - 1, now + 1):
        age = t - slot * interval
        if 0 <= age <= window:
            found.append((age, int(_noise(slot, 7) * len(keys)) % len(keys), slot))
    return found


def frame(effect, keys, t, colour, rainbow, speed=2, brightness=4):
    """Colour every key for one moment of the effect.

    keys: list of (key_id, x, y) with x in key units (0..18) and y the row (0..4).
    Returns {key_id: '#rrggbb'}.
    """
    if not keys:
        return {}
    rate = 0.35 + 0.3 * max(0, min(4, int(speed)))
    level = LEVELS[max(0, min(4, int(brightness)))]
    base = _rgb(colour)
    p = t * rate
    cx, cy = CENTRE
    out = {}

    def mix(rgb, intensity):
        intensity = max(0.0, min(1.0, intensity))
        lit = tuple(c * level for c in rgb)
        if effect in _SPARSE:
            return _hex(tuple(u + (l - u) * intensity for u, l in zip(UNLIT, lit)))
        return _hex(tuple(c * (0.15 + 0.85 * intensity) for c in lit))

    def tint(h, intensity=1.0):
        return mix(_hue(h) if rainbow else base, intensity)

    if effect == 'Off':
        return {key: _hex(UNLIT) for key, _, _ in keys}

    if effect in ('Reactive', 'Ripple'):
        presses = _presses(t, rate, keys, 0.45 if effect == 'Reactive' else 0.9, 1.6 if effect == 'Reactive' else 2.2)
        for key, x, y in keys:
            best, hue = 0.0, 0.0
            for age, index, slot in presses:
                _, px, py = keys[index]
                if effect == 'Reactive':
                    value = math.exp(-age * 2.2) if (px, py) == (x, y) else 0.0
                else:
                    radius = age * 5.5
                    ring = 1.0 - abs(math.hypot(x - px, (y - py) * 1.1) - radius) / 1.1
                    value = max(0.0, ring) * max(0.0, 1.0 - age / 2.2)
                if value > best:
                    best, hue = value, _noise(slot, 3)
            out[key] = tint(hue, best)
        return out

    if effect == 'Trail':
        ordered = sorted(keys, key=lambda k: (k[2], k[1] if k[2] % 2 == 0 else -k[1]))
        n = len(ordered)
        head = (p * 9.0) % n
        for i, (key, x, y) in enumerate(ordered):
            behind = (head - i) % n
            out[key] = tint(i / n + p * 0.05, 1.0 - behind / 10.0 if behind < 10 else 0.0)
        return out

    if effect == 'Flowers':
        interval, life = 0.55, 2.6
        now = int(p // interval)
        blooms = []
        for slot in range(now - int(life / interval) - 1, now + 1):
            age = p - slot * interval
            if 0 <= age <= life:
                blooms.append((age, _noise(slot, 1) * WIDTH, _noise(slot, 2) * 4.0, _noise(slot, 4)))
        for key, x, y in keys:
            best, hue = 0.0, 0.0
            for age, bx, by, h in blooms:
                radius = 0.6 + age * 1.6
                d = math.hypot(x - bx, (y - by) * 1.2)
                if d <= radius:
                    value = (1.0 - age / life) * (1.0 - 0.5 * d / radius)
                    if value > best:
                        best, hue = value, h
            out[key] = tint(hue, best)
        return out

    for key, x, y in keys:
        u = x / WIDTH
        if effect in ('Wave', 'Fast wave'):
            q = p * (3.0 if effect == 'Fast wave' else 1.0)
            out[key] = tint(u - q * 0.25, 1.0) if rainbow else mix(base, 0.5 + 0.5 * math.sin(2 * math.pi * (u * 1.5 - q * 0.25)))
        elif effect == 'Colour cloud':
            n = (math.sin(x * 0.35 + p * 0.9) + math.sin(y * 0.9 - p * 0.6) + math.sin((x + y) * 0.25 + p * 0.4) + 3) / 6
            out[key] = tint(n * 0.8 + p * 0.05, 1.0) if rainbow else mix(base, 0.25 + 0.75 * n)
        elif effect == 'Vortex':
            angle = math.atan2((y - cy) * 2.2, x - cx) / (2 * math.pi)
            out[key] = tint(angle + p * 0.3, 1.0) if rainbow else mix(base, 0.5 + 0.5 * math.sin(2 * math.pi * (angle * 2 + p * 0.3)))
        elif effect == 'Spectrum':
            out[key] = mix(_hue(p * 0.08), 1.0)
        elif effect == 'Breathing':
            breath = 0.5 - 0.5 * math.cos(2 * math.pi * p * 0.25)
            out[key] = mix(_hue(math.floor(p * 0.25) * 0.17) if rainbow else base, breath)
        elif effect == 'Solid':
            out[key] = tint(u, 1.0)
        elif effect == 'Stars':
            period = 1.4 + _noise(len(key), ord(key[0]), x * 4, y) * 2.2
            phase = (p / period + _noise(x * 4, y, 9)) % 1.0
            sparkle = math.sin(math.pi * phase * 3) if phase < 1 / 3 else 0.0
            out[key] = tint(_noise(x * 4, y, math.floor(p / period)), sparkle)
        elif effect == 'Scroll':
            out[key] = tint(y / 5 + p * 0.3, 1.0) if rainbow else mix(base, 0.5 + 0.5 * math.sin(2 * math.pi * (y / 5 + p * 0.3)))
        elif effect == 'Wings':
            spread = abs(x - cx) / WIDTH * 2
            out[key] = tint(spread - p * 0.25, 1.0) if rainbow else mix(base, 0.5 + 0.5 * math.sin(2 * math.pi * (spread * 1.5 - p * 0.25)))
        elif effect == 'Build up':
            fill = (p * 0.18) % 1.25
            out[key] = tint(u, 1.0 if u <= fill else 0.0)
        elif effect == 'Rain':
            column = round(x)
            period = 1.0 + _noise(column, 5) * 1.5
            head = ((p / period + _noise(column, 6)) % 1.0) * 7.0 - 1.0
            drop = 1.0 - (head - y) / 2.5 if 0 <= head - y <= 2.5 else 0.0
            out[key] = tint(_noise(column, 8), drop)
        elif effect == 'Scan':
            bar = (0.5 + 0.5 * math.sin(p * 0.9)) * WIDTH
            out[key] = tint(bar / WIDTH, 1.0 - abs(x - bar) / 1.6)
        elif effect == 'Spread':
            d = math.hypot(x - cx, (y - cy) * 1.4) / WIDTH * 2
            ring = (d - p * 0.3) % 1.0
            out[key] = tint(ring, 1.0) if rainbow else mix(base, 0.5 + 0.5 * math.cos(2 * math.pi * ring * 2))
        else:  # Custom table, or anything unknown: steady colour.
            out[key] = mix(base, 1.0)
    return out
