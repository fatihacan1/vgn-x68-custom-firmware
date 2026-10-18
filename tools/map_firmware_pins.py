"""List every direct GPIO register write in the stock V0113 image (Telink B91, 0x801403xx).

Usage: python tools/map_firmware_pins.py firmware-library/stock-v0113.bin
Needs LLVM (llvm-objcopy, llvm-objdump). Reads the file only; no USB access.
Andes custom opcodes decode as <unknown>; the scan follows lui 0x80140 bases
and their sb/sh/sw stores, so bit-twiddled read-modify-write sequences are shown
with a few instructions of context. Code copied to RAM appears at its flash offset.
"""
import collections, re, subprocess, sys, tempfile
from pathlib import Path

LLVM = Path('C:/Program Files/LLVM/bin') if sys.platform == 'win32' else Path('/usr/bin')
REG = {0: 'IN', 1: 'IE', 2: 'OEN', 3: 'OUT', 4: 'POL', 5: 'DS', 6: 'FUNC_EN', 7: 'IRQ'}


def disassemble(binary):
    with tempfile.TemporaryDirectory() as tmp:
        obj = Path(tmp) / 'image.o'
        subprocess.run([str(LLVM / 'llvm-objcopy'), '-I', 'binary', '-O', 'elf32-littleriscv',
                        '--rename-section', '.data=.text,code,alloc,load,contents', str(binary), str(obj)], check=True)
        text = subprocess.run([str(LLVM / 'llvm-objdump'), '-D', '--triple=riscv32', '--mattr=+m,+a,+c,+f,+zicsr',
                               '--adjust-vma=0x20000000', '-M', 'no-aliases', str(obj)], capture_output=True, text=True).stdout
    out = []
    for line in text.splitlines():
        m = re.match(r'\s*([0-9a-f]{8}):\s+[0-9a-f ]+\s+(\S+)\s*(.*)', line)
        if m:
            out.append((int(m.group(1), 16), m.group(2), re.sub(r'<[^>]*>', '', m.group(3)).strip()))
    return out


def gpio_writes(ins):
    hits = collections.defaultdict(list)
    for i, (_, op, args) in enumerate(ins):
        if op != 'lui' or not args.endswith('0x80140'):
            continue
        off = {args.split(',')[0].strip(): 0}
        for j in range(i + 1, min(i + 60, len(ins))):
            addr, op2, args2 = ins[j]
            parts = [p.strip() for p in args2.split(',')]
            m = re.match(r'(-?0x[0-9a-f]+|-?\d+)\((\w+)\)', parts[-1]) if parts else None
            if op2 in ('sb', 'sh', 'sw') and m and m.group(2) in off:
                target = 0x80140000 + off[m.group(2)] + int(m.group(1), 0)
                if 0x80140300 <= target < 0x80140330:
                    k = target - 0x80140300
                    ctx = ' | '.join(f'{o} {g}' for _, o, g in ins[max(i, j - 3):j + 1])
                    hits[('P' + 'ABCDEF'[k >> 3], REG[k & 7])].append((addr, ctx))
            if op2 == 'addi' and len(parts) == 3 and parts[1] in off and parts[0] != parts[1]:
                off[parts[0]] = off[parts[1]] + int(parts[2], 0)
                continue
            if parts and parts[0] in off and op2 not in ('sb', 'sh', 'sw', 'beq', 'bne', 'blt', 'bge', 'bltu', 'bgeu'):
                del off[parts[0]]
            if not off:
                break
    return hits


if __name__ == '__main__':
    for (port, reg), rows in sorted(gpio_writes(disassemble(sys.argv[1])).items()):
        print(f'== {port} {reg}: {len(rows)} writes')
        for addr, ctx in rows:
            print(f'   {addr:08X}  {ctx}')
