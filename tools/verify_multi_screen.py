"""Emulate the multi-screen media logic of a native display build in Unicorn (no keyboard access).

Runs on top of tools/verify_native_screen.py. For every screen mode it checks that
the RV32 renderer reads exactly the expected frame from the A2000..DE000 bank, that
empty slots, mode 0 and invalid tables never read flash, that an unchanged frame is
not re-read, that RAM writes stay in the renderer's scopes, and that the host build
of the same C source shows the same pixels.
"""
from pathlib import Path
import argparse, ctypes, json, sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from unicorn import Uc, UC_ARCH_RISCV, UC_MODE_RISCV32, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.riscv_const import UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2, UC_RISCV_REG_GP, UC_RISCV_REG_PC, UC_RISCV_REG_RA, UC_RISCV_REG_SP

PARAM, BANK, FRAME = 0x80550, 0xA2000, 30720
TABLE = {1: (0, 1, 1000), 2: (1, 3, 100), 3: (0, 0, 0), 4: (4, 4, 200)}  # first, count, period ms
ALLOWED = [(0x9f000, 0x9ff00), (0x819e0, 0x891e0), (0x80b80, 0x80b87), (0x80d8c, 0x80d93),
           (0x80c9a, 0x80c9b), (0x80d20, 0x80d21), (0x80d49, 0x80d4a), (0x80d82, 0x80d83)]


def table_bytes(entries, magic=b'XS\x01'):
    data = bytearray(64)
    data[45:48] = magic
    for mode, (first, count, period) in entries.items():
        data[48 + (mode - 1) * 4:52 + (mode - 1) * 4] = bytes([first, count]) + period.to_bytes(2, 'little')
    return data


def run(payload, params, mode, ticks):
    """Render once per tick value, keeping RAM state between calls. Returns (flash reads, frames shown)."""
    uc = Uc(UC_ARCH_RISCV, UC_MODE_RISCV32); uc.mem_map(0, 0x100000); uc.mem_map(0x20000000, 0x40000); uc.mem_map(0x80140000, 0x1000)
    uc.mem_write(0x20000000, payload); uc.mem_write(0x1200, payload[0x12b0:0xa0b4])
    uc.mem_write(0xbb4, (0x11000).to_bytes(4, 'little')); uc.mem_write(0x11000, bytes.fromhex('67 80 00 00'))
    block = bytearray(params); block[33] = mode
    uc.mem_write(PARAM, bytes(block)); uc.mem_write(0x80573, bytes([0x42, 0x35, 0x03, 7, 0x18, 0x10]))
    uc.reg_write(UC_RISCV_REG_SP, 0x9ff00); uc.reg_write(UC_RISCV_REG_GP, 0x80800)
    reads, shown = [], []

    def hardware(machine, address, size, user):
        if address == 0x6eac:
            machine.mem_write(0x80c9a, b'\0'); machine.reg_write(UC_RISCV_REG_PC, machine.reg_read(UC_RISCV_REG_RA))
        elif address == 0x11000:
            src, length, dest = (machine.reg_read(r) for r in (UC_RISCV_REG_A0, UC_RISCV_REG_A1, UC_RISCV_REG_A2))
            assert BANK <= src and src + length <= BANK + 8 * FRAME and length == FRAME and dest == 0x819e0 and (src - BANK) % FRAME == 0, 'Out-of-bank flash read'
            index = (src - BANK) // FRAME; machine.mem_write(dest, bytes([index + 1]) * length); reads.append(index)
            machine.reg_write(UC_RISCV_REG_PC, machine.reg_read(UC_RISCV_REG_RA))
        elif address == 0x2000f4f4:
            raise AssertionError('Unexpected RTC read')

    def writes(machine, access, address, size, value, user):
        assert any(lo <= address and address + size <= hi for lo, hi in ALLOWED), f'Out-of-scope write {address:08X}'
        assert not (PARAM <= address < PARAM + 64), 'Renderer wrote the parameter block'
    uc.hook_add(UC_HOOK_CODE, hardware); uc.hook_add(UC_HOOK_MEM_WRITE, writes)
    for tick in ticks:
        uc.mem_write(0x80140200, tick.to_bytes(4, 'little')); uc.reg_write(UC_RISCV_REG_RA, 0x10000)
        uc.emu_start(0x7110, 0x10000, count=2000000)
        assert uc.reg_read(UC_RISCV_REG_PC) == 0x10000 and uc.reg_read(UC_RISCV_REG_SP) == 0x9ff00, 'Renderer did not return cleanly'
        fb = bytes(uc.mem_read(0x819e0, FRAME))
        shown.append(fb[0] - 1 if fb == bytes([fb[0]]) * FRAME and 1 <= fb[0] <= 8 else None)
    return reads, shown


def host_frame(folder, params, mode, tick):
    dll = ctypes.CDLL(str((Path(folder) / 'screen-host.dll').resolve()))
    block = bytearray(params); block[33] = mode
    (ctypes.c_ubyte * 64).in_dll(dll, 'params')[:] = block
    media = (ctypes.c_ubyte * (8 * FRAME)).in_dll(dll, 'media_data')
    for index in range(8):
        media[index * FRAME:(index + 1) * FRAME] = bytes([index + 1]) * FRAME
    ctypes.c_uint.in_dll(dll, 'tick').value = tick; dll.render()
    fb = bytes((ctypes.c_ubyte * FRAME).in_dll(dll, 'framebuffer'))
    return fb[0] - 1 if fb == bytes([fb[0]]) * FRAME and 1 <= fb[0] <= 8 else None


def verify(payload, folder):
    results = []
    good = table_bytes(TABLE)
    for mode in range(5):
        first, count, period = TABLE.get(mode, (0, 0, 0))
        ticks = [0, period * 16000 if period else 16000000, 2 * period * 16000 if period else 32000000, 2 * period * 16000 + 1 if period else 32000001]
        reads, shown = run(payload, good, mode, ticks)
        if mode and count:
            expected = [first + (t // (period * 16000)) % count for t in ticks]
            assert shown == expected, f'mode {mode}: shown {shown} expected {expected}'
            assert reads == [e for i, e in enumerate(expected) if i == 0 or e != expected[i - 1]], f'mode {mode}: reads {reads}'
            for t, e in zip(ticks, expected):
                assert host_frame(folder, good, mode, t) == e, f'mode {mode}: host differs at tick {t}'
        else:
            assert reads == [] and shown == [None] * len(ticks), f'mode {mode}: desktop expected, got reads {reads}'
        results.append({'case': f'table-mode-{mode}', 'passed': True, 'flash_reads': reads, 'frames': shown})
    for name, params, mode in [
        ('table-overflow', table_bytes({2: (6, 3, 100)}), 2),
        ('table-first-out-of-bank', table_bytes({1: (8, 1, 100)}), 1),
        ('table-period-too-short', table_bytes({1: (0, 2, 10)}), 1),
        ('table-period-too-long', table_bytes({1: (0, 2, 6000)}), 1),
        ('wrong-magic-mode-2', table_bytes({2: (0, 2, 100)}, b'XS\x02'), 2),
        ('mode-5-ignored', good, 5),
        ('mode-255-ignored', good, 255),
    ]:
        reads, shown = run(payload, params, mode, [0, 16000000])
        assert reads == [] and shown == [None, None], f'{name}: expected desktop, got {reads}'
        results.append({'case': name, 'passed': True})
    legacy = bytearray(64); legacy[34] = 2; legacy[42:44] = (125).to_bytes(2, 'little')
    reads, shown = run(payload, legacy, 4, [0, 2000000])
    assert reads == [0, 1] and shown == [0, 1], f'legacy single media: {reads}'
    results.append({'case': 'legacy-mode-4-without-table', 'passed': True})
    return {'device_test': False, 'cases': results}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--folder', type=Path, default=ROOT / 'reports/native-desktop'); a = p.parse_args()
    result = verify((a.folder / 'x68-v0113-pixel-desktop.bin').read_bytes(), a.folder)
    (a.folder / 'multi-screen-emulation.json').write_text(json.dumps(result, indent=2), encoding='utf-8'); print(json.dumps(result))
