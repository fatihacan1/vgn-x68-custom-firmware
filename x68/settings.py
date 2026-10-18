"""X68 settings report 4, independently implemented from static evidence.

The dispatch table in the official X68 payload is at 0x2001E72C.
Read/write pairs: parameters 5/6, keymap 8/9, macro bank 20/21.
Only bounded settings operations are exposed; no firmware or reset commands.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import struct
import time

from .protocol import enumerate_targets, interface_matches, is_wireless, collection_reports, ProtocolError

SETTINGS_DESCRIPTOR = bytes.fromhex(
    "06 1c ff 09 92 a1 01 85 04 19 00 29 ff 15 00 26 ff 00 75 08 95 3f 81 00 "
    "19 00 29 ff 15 00 26 ff 00 75 08 95 3f 91 00 c0"
)
WIRELESS_SETTINGS_REPORTS = {(4, 'in', 8, 63), (4, 'out', 8, 63)}
READ_LIMITS = {3: 34, 5: 64, 8: 384, 20: 4096, 26: 6, 25:48}
WRITE_LIMITS = {6: 64, 9: 384, 21: 4096, 24: 6}
MODIFIERS = {"CTRL": 1, "SHIFT": 2, "ALT": 4, "WIN": 8,
             "RCTRL": 16, "RSHIFT": 32, "RALT": 64, "RWIN": 128}
HID_KEYS = {chr(65+i): i+4 for i in range(26)}
HID_KEYS.update({str(i): i+29 for i in range(1, 10)})
HID_KEYS.update({"0": 39, "ENTER": 40, "ESC": 41, "BACKSPACE": 42, "TAB": 43,
                 "SPACE": 44, "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49,
                 ";": 51, "'": 52, "`": 53, ",": 54, ".": 55, "/": 56,
                 "CAPSLOCK": 57, "PRINTSCREEN": 70, "SCROLLLOCK": 71,
                 "PAUSE": 72, "INSERT": 73, "HOME": 74, "PAGEUP": 75,
                 "DELETE": 76, "END": 77, "PAGEDOWN": 78,
                 "RIGHT": 79, "LEFT": 80, "DOWN": 81, "UP": 82})
HID_KEYS.update({f"F{i}": i+57 for i in range(1, 13)})
NAMES = {v: k for k, v in HID_KEYS.items()}
MOD_NAMES = {v << 8: k for k, v in MODIFIERS.items()}
MODES = [(1, "Wave"), (2, "Colour cloud"), (3, "Vortex"), (4, "Spectrum"), (5, "Breathing"), (6, "Solid"), (7, "Reactive"), (8, "Ripple"), (9, "Trail"), (10, "Stars"), (11, "Flowers"), (12, "Scroll"), (13, "Wings"), (14, "Build up"), (15, "Rain"), (16, "Scan"), (17, "Spread"), (18, "Fast wave"), (19, "Custom table"), (20, "Off")]


def settings_packet(command: int, offset=0, data=b"", size=None) -> bytes:
    if command in (1, 2):
        if offset or data or size:
            raise ProtocolError("Invalid range-limit packet.")
        count = 0
    elif command in READ_LIMITS:
        if command == 25 and (offset != 0 or size != 48):
            raise ProtocolError('Diagnostic query accepts exactly 48 bytes at offset zero.')
        if command == 26 and (offset != 0 or size != 6):
            raise ProtocolError("The battery query may only use the verified 6-byte format.")
        if data or type(size) is not int:
            raise ProtocolError("Invalid read.")
        count = size
        if offset < 0 or not 1 <= count <= 56 or offset + count > READ_LIMITS[command]:
            raise ProtocolError("Read is outside the verified settings region.")
    elif command in WRITE_LIMITS:
        count = len(data)
        if command == 24 and (offset or count != 6):
            raise ProtocolError('RAM clock sync accepts exactly six bytes at offset zero.')
        if size is not None or offset < 0 or not 1 <= count <= 56 or offset + count > WRITE_LIMITS[command]:
            raise ProtocolError("Write is outside the verified settings region.")
    else:
        raise ProtocolError("This command is not supported and was not sent.")
    packet = bytearray(64)
    packet[0], packet[3], packet[4] = 4, command, count
    packet[5:8] = offset.to_bytes(3, "little")
    packet[8:8+len(data)] = data
    packet[1:3] = (sum(packet[3:]) & 0xFFFF).to_bytes(2, "little")
    return bytes(packet)


def decode_lighting(data: bytes) -> dict:
    if len(data) != 64:
        raise ProtocolError("The settings block must be 64 bytes.")
    # The first byte is retained; newer Evision config tools also retain it.
    mode, brightness, speed = data[1:4]
    if mode not in dict(MODES) or brightness > 4 or speed > 4:
        raise ProtocolError("RGB fields are not in the expected format; writing is disabled.")
    return {"mode": mode, "brightness": brightness, "speed": 4-speed,
            "rainbow": bool(data[5]) if data[5] in (0,1) else None,
            "rainbow_raw": data[5], "color": "#"+data[6:9].hex(), "raw_hex": data.hex(" ")}


def encode_lighting(original: bytes, mode, brightness, speed, rainbow, color) -> bytes:
    decode_lighting(original)
    if mode not in dict(MODES) or not 0 <= brightness <= 4 or not 0 <= speed <= 4:
        raise ProtocolError("RGB values are out of range.")
    try:
        rgb = bytes.fromhex(color.removeprefix("#"))
    except ValueError:
        raise ProtocolError("Colour must be #RRGGBB.") from None
    if len(rgb) != 3:
        raise ProtocolError("Colour must be three bytes.")
    result = bytearray(original)
    result[1:4] = bytes([mode, brightness, 4-speed])
    if rainbow is not None:
        if type(rainbow) is not bool:
            raise ProtocolError('Rainbow must be True, False, or None to preserve the device flag.')
        result[5] = int(rainbow)
    result[6:9] = rgb
    return bytes(result)


def keymap_entries(data: bytes) -> list[dict]:
    if len(data) != 384:
        raise ProtocolError("The keymap block must be 384 bytes.")
    entries = []
    for index in range(128):
        flag, high, low = data[index*3:index*3+3]
        code = high*256 + low
        if flag == 32 and code:
            name = MOD_NAMES.get(code, NAMES.get(code, f"HID {code:04X}"))
        elif flag in (112, 113):
            name = f"Makro {high+1}"
        elif flag == 160 and high == 1 and low == 0:
            name = "Fn"
        elif code == 0:
            name = "Empty"
        else:
            name = f"Function {flag:02X}/{code:04X}"
        entries.append({"index": index, "flag": flag, "code": code, "name": name,
                        "editable": 16 <= index < 96 and flag in (32, 112, 113) and (bool(code) or flag != 32)})
    return entries


def encode_key(name: str) -> bytes:
    name = name.upper().strip()
    if name == 'FN':
        return bytes([160, 1, 0])
    if name in MODIFIERS:
        return bytes([32, MODIFIERS[name], 0])
    if name in HID_KEYS:
        return bytes([32, 0, HID_KEYS[name]])
    raise ProtocolError("Unsupported target key.")


def compile_macro(text: str) -> bytes:
    """Small explicit DSL: CTRL+C, WAIT 100, ENTER; no command execution."""
    events = []
    delay = 0
    held = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip().upper()
        if not line or line.startswith("#"):
            continue
        if line.startswith("WAIT "):
            try:
                delay += int(line[5:])
            except ValueError:
                raise ProtocolError(f"Line {number}: WAIT expects milliseconds.") from None
            if not 0 <= delay <= 65535:
                raise ProtocolError("WAIT must be 0-65535 ms.")
            continue
        if line.startswith("DOWN ") or line.startswith("UP "):
            down = line.startswith("DOWN ")
            name = line.split(" ", 1)[1].strip()
            mouse = {"MOUSELEFT": 1, "MOUSERIGHT": 2, "MOUSEMIDDLE": 4}
            if name in MODIFIERS:
                action, value = (137 if down else 9), MODIFIERS[name]
            elif name in HID_KEYS:
                action, value = (138 if down else 10), HID_KEYS[name]
            elif name in mouse:
                action, value = (129 if down else 1), mouse[name]
            else:
                raise ProtocolError(f"Line {number}: unknown key {name!r}.")
            if down == (name in held):
                raise ProtocolError(f"Line {number}: unmatched press/release.")
            held.add(name) if down else held.remove(name)
            events.append(struct.pack("<HBB", delay, action, value))
            delay = 0
            continue
        parts = line.split("+")
        mods = []
        keys = []
        for name in parts:
            if name in MODIFIERS:
                mods.append(MODIFIERS[name])
            elif name in HID_KEYS:
                keys.append(HID_KEYS[name])
            else:
                raise ProtocolError(f"Line {number}: unknown key {name!r}.")
        if len(keys) > 6 or len(set(parts)) != len(parts):
            raise ProtocolError("Repeated key or too many keys held at once.")
        sequence = [(137, m) for m in mods] + [(138, k) for k in keys]
        sequence += [(10, k) for k in reversed(keys)] + [(9, m) for m in reversed(mods)]
        for position, (action, key) in enumerate(sequence):
            events.append(struct.pack("<HBB", delay if position == 0 else 20, action, key))
        delay = 20
    if held:
        raise ProtocolError("Keys still held at the end of the macro: "+", ".join(sorted(held)))
    if not 1 <= len(events) <= 90:
        raise ProtocolError("A macro needs 1-90 press/release events.")
    return struct.pack("<HBB", len(events), 53, 0) + b"".join(events)


def macro_text(block: bytes) -> str:
    count = int.from_bytes(block[:2], 'little')
    if len(block) != count*4+4:
        raise ProtocolError("Invalid macro block size.")
    lines = []
    for pos in range(4, len(block), 4):
        delay, action, value = struct.unpack_from('<HBB', block, pos)
        if delay:
            lines.append(f"WAIT {delay}")
        if action in (137, 9):
            name = next((k for k, v in MODIFIERS.items() if v == value), None)
        elif action in (138, 10):
            name = NAMES.get(value)
        elif action in (129, 1):
            name = {1: 'MOUSELEFT', 2: 'MOUSERIGHT', 4: 'MOUSEMIDDLE'}.get(value)
        else:
            name = None
        if not name:
            raise ProtocolError("This macro contains mouse or special events the text editor cannot show. The data on the keyboard is kept.")
        lines.append(('DOWN ' if action in (137, 138, 129) else 'UP ')+name)
    return '\n'.join(lines)


def parse_macro_bank(data: bytes) -> list[bytes]:
    if len(data) < 18 or data[:2] != b"\xaa\x55":
        raise ProtocolError("Macro bank header not recognised; it will not be overwritten.")
    total, count = struct.unpack_from("<HH", data, 2)
    if not 1 <= count <= 16 or not 16+2*count <= total <= 4096 or len(data) < total:
        raise ProtocolError("Macro bank size not recognised; it will not be overwritten.")
    offsets = list(struct.unpack_from("<"+"H"*count, data, 16)) + [total]
    if offsets[0] != 16+2*count or offsets != sorted(offsets):
        raise ProtocolError("Invalid macro offsets.")
    blocks = []
    for start, end in zip(offsets, offsets[1:]):
        block = data[start:end]
        if len(block) < 4 or struct.unpack_from("<H", block)[0]*4+4 != len(block):
            raise ProtocolError("Macro event size not recognised.")
        blocks.append(block)
    return blocks


def replace_macro(original: bytes, slot: int, block: bytes) -> bytes:
    if not 0 <= slot < 16:
        raise ProtocolError("Macro slot must be 1-16.")
    blocks = parse_macro_bank(original)
    while len(blocks) <= slot:
        blocks.append(b"\x00\x00\x35\x00")
    blocks[slot] = block
    offset = 16+2*len(blocks)
    offsets = []
    for value in blocks:
        offsets.append(offset)
        offset += len(value)
    if offset > 4096:
        raise ProtocolError("The macro bank would exceed 4096 bytes.")
    header = bytearray(original[:16])
    struct.pack_into("<HH", header, 2, offset, len(blocks))
    result = bytes(header) + struct.pack("<"+"H"*len(offsets), *offsets) + b"".join(blocks)
    parse_macro_bank(result)
    return result


class SettingsClient:
    def __init__(self, client, backups: Path):
        self.client = client
        self.backups = backups
        self.trace = []

    @contextmanager
    def _device(self, wireless=True):
        # Bulk transfers (LCD media) pass wireless=False and stay on the cable.
        with self.client.lock:
            matches = [d for d in enumerate_targets(self.client.backend, wireless)
                       if d['usage_page'] == 0xFF1C and d['usage'] == 0x92 and interface_matches(d,1)]
            if len(matches) != 1:
                raise ProtocolError("Exactly one X68 settings interface is required." if wireless or matches
                                    else "This needs the USB cable in wired mode.")
            device = self.client.backend.device()
            try:
                device.open_path(matches[0]['path'])
                descriptor = bytes(device.get_report_descriptor())
                if (collection_reports(descriptor, 0xFF1C, 0x92) != WIRELESS_SETTINGS_REPORTS
                        if is_wireless(matches[0]) else descriptor != SETTINGS_DESCRIPTOR):
                    raise ProtocolError("The X68 settings interface descriptor did not match; nothing was written.")
                while device.read(64, 10):
                    # Bounded drain, no continuous unsolicited stream expected.
                    break
                yield device
            finally:
                device.close()

    def _exchange(self, device, command, offset=0, data=b"", size=None):
        packet = settings_packet(command, offset, data, size)
        if device.write(packet) != 64:
            raise ProtocolError("Settings packet was incomplete; it was not resent.")
        deadline = time.monotonic()+2
        while time.monotonic() < deadline:
            reply = bytes(device.read(64, 200))
            if len(reply) == 64 and reply[:8] == packet[:8]:
                self.trace.append({"command": command, "offset": offset, "size": packet[4],
                                   "tx": packet.hex(" "), "rx": reply.hex(" ")})
                self.trace = self.trace[-160:]
                return reply[8:8+packet[4]]
        raise ProtocolError(f"No matching reply for settings command {command:02X}; it was not resent.")

    def _read(self, device, command, length):
        return b"".join(self._exchange(device, command, pos, size=min(56, length-pos))
                        for pos in range(0, length, 56))

    def _write(self, device, command, data):
        for pos in range(0, len(data), 56):
            self._exchange(device, command, pos, data[pos:pos+56])

    def _backup(self, kind, data):
        self.backups.mkdir(parents=True, exist_ok=True)
        path = self.backups / (datetime.now().strftime("%Y%m%d-%H%M%S-%f")+"-"+kind+".json")
        path.write_text(json.dumps({"product": "SUBOR X68", "kind": kind, "data_hex": data.hex(" ")}, indent=2), encoding="utf-8")
        return str(path)

    @contextmanager
    def _transaction(self, device):
        self._exchange(device, 1)
        try:
            yield
        finally:
            self._exchange(device, 2)
            time.sleep(0.1)

    def read_settings(self):
        with self._device() as device:
            params = self._read(device, 5, 64)
            mapping = self._read(device, 8, 384)
            macro_bank = self._read(device, 20, 4096)
        try:
            lighting = decode_lighting(params)
            lighting_error = None
        except ProtocolError as error:
            lighting, lighting_error = None, str(error)
        try:
            blocks = parse_macro_bank(macro_bank)
            macros = [{"slot": i+1, "events": int.from_bytes(b[:2], "little"), "block_hex": b.hex(" ")} for i, b in enumerate(blocks)]
            macro_error = None
        except ProtocolError as error:
            macros, macro_error = [], str(error)
        return {"parameters_hex": params.hex(" "), "keymap_hex": mapping.hex(" "),
                "macro_bank_hex": macro_bank.hex(" "), "lighting": lighting,
                "lighting_error": lighting_error, "keys": keymap_entries(mapping),
                "macros": macros, "macro_error": macro_error}

    def set_lighting(self, mode, brightness, speed, rainbow, color):
        with self._device() as device:
            original = self._read(device, 5, 64)
            desired = encode_lighting(original, mode, brightness, speed, rainbow, color)
            if desired == original:
                return {"changed": False, "lighting": decode_lighting(original)}
            backup = self._backup("lighting", original)
            with self._transaction(device):
                self._write(device, 6, desired)
            readback = self._read(device, 5, 64)
            if readback != desired:
                raise ProtocolError("RGB readback did not match. Backup: "+backup)
            return {"changed": True, "backup": backup, "lighting": decode_lighting(readback)}

    def sync_clock(self, moment=None):
        """V0113 parameter bytes 0x23..0x28 -> original RTC setter 0x2000F4A4.

        Setter writes seconds, minutes, hours, weekday, day and month, then
        clears RTC control register 0. It sets year to 0x22 internally; the
        native replacement deliberately does not display a year.
        """
        moment = moment or datetime.now().astimezone()
        def bcd(number): return (number//10)*16+number%10
        fields=bytes(map(bcd,[moment.second,moment.minute,moment.hour,moment.isoweekday(),moment.day,moment.month]))
        with self._device() as device:
            original=self._read(device,5,64)
            backup=self._backup('lighting',original)
            desired=bytearray(original);desired[0x23:0x29]=fields
            with self._transaction(device):
                self._write(device,6,bytes(desired))
            actual=self._read(device,5,64)
            if actual[0x23:0x29] != fields:
                raise ProtocolError('Clock settings readback differs. Backup: '+backup)
            changed=[i for i,(a,b) in enumerate(zip(original,actual)) if a!=b]
            unexpected=[i for i in changed if not 0x23<=i<0x29 and i!=0x29]
            if unexpected:
                raise ProtocolError('Unexpected parameter changes after clock sync: '+str(unexpected))
            return {'clock_fields_bcd':fields.hex(' '),'local_time':moment.isoformat(),
                    'backup':backup,'changed_offsets':changed,
                    'rtc_running_requires_physical_confirmation':True}

    def sync_clock_live(self, firmware_crc, moment=None, receiver=False):
        """Custom 0.5.1 command 18, RAM only.

        Over the 2.4 GHz receiver the version reply is the receiver's CRC, so the keyboard's
        build cannot be checked. Stock V0113 routes command 18 to its unsupported handler,
        so sending it there unverified changes nothing.
        """
        from .firmware import LIVE_CLOCK_CRCS
        if not receiver and firmware_crc not in LIVE_CLOCK_CRCS:
            raise ProtocolError('Live clock sync requires the reviewed Lavender Quest 0.5.1 firmware.')
        moment=moment or datetime.now().astimezone()
        fields=bytes((n//10)*16+n%10 for n in [moment.second,moment.minute,moment.hour,moment.isoweekday(),moment.day,moment.month])
        with self._device() as device:
            self._exchange(device,24,data=fields)
        return {'local_time':moment.isoformat(),'clock_fields_bcd':fields.hex(' '),'persistent_flash_write':False}

    def _set_mapping(self, device, original, desired):
        if len(original) != 384 or len(desired) != 384:
            raise ProtocolError("Invalid keymap size.")
        backup = self._backup("keymap", original)
        with self._transaction(device):
            self._write(device, 9, desired)
        if self._read(device, 8, 384) != desired:
            raise ProtocolError("Keymap readback did not match. Backup: "+backup)
        return backup

    def remap(self, index, target):
        with self._device() as device:
            original = self._read(device, 8, 384)
            self._check_editable(original, index)
            desired = bytearray(original)
            desired[index*3:index*3+3] = encode_key(target)
            if desired == original:
                return {"changed": False}
            return {"changed": True, "backup": self._set_mapping(device, original, bytes(desired))}

    def remap_batch(self, changes):
        if not changes: return {'changed':False,'count':0}
        with self._device() as device:
            original=self._read(device,8,384);desired=bytearray(original)
            for index,target in changes.items():
                self._check_editable(original,index)
                desired[index*3:index*3+3]=encode_key(target)
            if desired==original:return {'changed':False,'count':0}
            return {'changed':True,'count':len(changes),'backup':self._set_mapping(device,original,bytes(desired))}

    @staticmethod
    def _check_editable(mapping, index):
        if type(index) is not int or not 0 <= index < 128 or not keymap_entries(mapping)[index]['editable']:
            raise ProtocolError("This matrix cell cannot be edited (Fn, empty or a special function).")

    def assign_macro(self, index, slot, text):
        block = compile_macro(text)
        with self._device() as device:
            mapping = self._read(device, 8, 384)
            self._check_editable(mapping, index)
            original_bank = self._read(device, 20, 4096)
            new_bank = replace_macro(original_bank, slot, block)
            backup = self._backup("macros", original_bank)
            with self._transaction(device):
                self._write(device, 21, new_bank)
            actual = self._read(device, 20, len(new_bank))
            if actual != new_bank:
                raise ProtocolError("Macro bank readback did not match. Backup: "+backup)
            desired = bytearray(mapping)
            desired[index*3:index*3+3] = bytes([113, slot, 1])  # repeat count = 1
            key_backup = self._set_mapping(device, mapping, bytes(desired))
            return {"changed": True, "macro_backup": backup, "keymap_backup": key_backup,
                    "slot": slot+1, "events": int.from_bytes(block[:2], 'little')}

    def restore(self, path):
        record = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        if record.get("product") != "SUBOR X68" or record.get("kind") not in {"lighting", "keymap", "macros"}:
            raise ProtocolError("This is not an X68 settings backup.")
        data = bytes.fromhex(record['data_hex'])
        kind = record['kind']
        read_cmd, write_cmd, length = {"lighting": (5, 6, 64), "keymap": (8, 9, 384), "macros": (20, 21, 4096)}[kind]
        if len(data) != length:
            raise ProtocolError("Backup size differs from what was expected.")
        with self._device() as device:
            current = self._read(device, read_cmd, length)
            backup = self._backup(kind, current)
            with self._transaction(device):
                self._write(device, write_cmd, data)
            if self._read(device, read_cmd, length) != data:
                raise ProtocolError("Backup readback did not match. Backup taken before the operation: "+backup)
            return {"restored": kind, "backup": backup}
