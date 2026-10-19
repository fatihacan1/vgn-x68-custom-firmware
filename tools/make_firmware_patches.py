"""Turn locally built Lavender Quest images into redistributable patches.

A patch holds only the bytes this project wrote (renderer, pixel art, hooks,
CRC). Applying it needs the official V0113 payload, which the app fetches from
VGN's own server on the user's machine. No vendor bytes are stored here.
"""
import hashlib, json, sys, zlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / 'firmware-library'
BUILDS = {'lavender-quest-0.8.0': 'lavender-quest-080.bin', 'lavender-quest-0.6.0': 'lavender-quest-060.bin', 'lavender-quest-0.5.1': 'lavender-quest.bin'}


def runs(base, target):
    out, i = [], 0
    while i < len(target):
        if base[i] == target[i]:
            i += 1
            continue
        j = i
        while j < len(target) and base[j] != target[j]:
            j += 1
        out.append([i, target[i:j].hex()])
        i = j
    return out


if __name__ == '__main__':
    stock = (LIB / 'stock-v0113.bin').read_bytes()
    for name, file in BUILDS.items():
        target = (LIB / file).read_bytes()
        patch = {'format': 'x68-patch-1', 'name': name,
                 'base_sha256': hashlib.sha256(stock).hexdigest(),
                 'target_sha256': hashlib.sha256(target).hexdigest(),
                 'target_crc': f'{zlib.crc32(target[:-4]) ^ 0xffffffff:08X}',
                 'size': len(target), 'runs': runs(stock, target)}
        path = ROOT / 'firmware-patches' / f'{name}.json'
        path.write_text(json.dumps(patch, separators=(',', ':')), encoding='utf-8')
        changed = sum(len(r[1]) // 2 for r in patch['runs'])
        print(name, len(patch['runs']), 'runs', changed, 'bytes', path.stat().st_size, 'file bytes')
