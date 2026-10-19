"""Builds firmware locally from the official VGN payload plus this project's patches.

The repository and release never contain VGN code. The stock V0113 payload is
fetched from VGN's own download server (or imported from a copy of the official
updater the user already has), recognised by SHA256 and cached on this computer.
The updater is read as bytes only: it is never saved to disk or executed.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from .firmware import V0113_SHA256, V0113_SIZE

UPDATER_URL = 'https://cdn.vgnclub.com/vgn/driver/X68/' + urllib.parse.quote('X68-V0113固件升级.exe')
UPDATER_SHA256 = 'cdf4535a909900c7644e496d415552c6b210f0f87afb77c80a54782e571bd771'
PATCHES = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'firmware-patches'
BUILDS = {'Lavender Quest 0.8.0 / 12-24 hour clock': 'lavender-quest-0.8.0',
          'Lavender Quest 0.6.0 / battery health': 'lavender-quest-0.6.0',
          'Lavender Quest 0.5.1': 'lavender-quest-0.5.1',
          'Original V0113': None}


def find_payload(blob: bytes) -> bytes:
    """Locate the stock payload inside an updater (or accept the raw payload) by exact hash."""
    if len(blob) == V0113_SIZE and hashlib.sha256(blob).hexdigest() == V0113_SHA256:
        return blob
    start = -1
    while True:
        start = blob.find(b'KNLT', start + 1)
        if start < 0x20:
            if start < 0:
                break
            continue
        candidate = blob[start - 0x20:start - 0x20 + V0113_SIZE]
        if hashlib.sha256(candidate).hexdigest() == V0113_SHA256:
            return candidate
    raise ValueError('The official V0113 payload was not found in this file.')


def stock(cache: Path, download=True) -> bytes:
    path = Path(cache) / 'stock-v0113.bin'
    if path.exists():
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() == V0113_SHA256:
            return data
    if not download:
        raise ValueError('Official V0113 firmware is not cached yet.')
    request = urllib.request.Request(UPDATER_URL, headers={'User-Agent': 'X68-Studio'})
    with urllib.request.urlopen(request, timeout=60) as response:
        blob = response.read(16 * 1024 * 1024)
    return save(cache, find_payload(blob))


def import_file(cache: Path, file: Path) -> bytes:
    """Accept the official updater EXE or the raw payload the user already has."""
    return save(cache, find_payload(Path(file).read_bytes()))


def save(cache: Path, payload: bytes) -> bytes:
    Path(cache).mkdir(parents=True, exist_ok=True)
    (Path(cache) / 'stock-v0113.bin').write_bytes(payload)
    return payload


def apply_patch(base: bytes, name: str) -> bytes:
    patch = json.loads((PATCHES / f'{name}.json').read_text(encoding='utf-8'))
    if patch.get('format') != 'x68-patch-1' or hashlib.sha256(base).hexdigest() != patch['base_sha256']:
        raise ValueError('Patch does not match the official V0113 payload.')
    data = bytearray(base)
    for offset, hex_bytes in patch['runs']:
        chunk = bytes.fromhex(hex_bytes)
        data[offset:offset + len(chunk)] = chunk
    data = bytes(data)
    if hashlib.sha256(data).hexdigest() != patch['target_sha256']:
        raise ValueError('Patched firmware hash differs from the reviewed build. Nothing was installed.')
    return data


def build(cache: Path, label: str, download=True) -> bytes:
    base = stock(cache, download)
    name = BUILDS[label]
    return base if name is None else apply_patch(base, name)
