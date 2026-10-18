from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import queue
import sys
import time
from pathlib import Path

from x68.protocol import X68Client
from x68.settings import SettingsClient, MODES, HID_KEYS, MODIFIERS, compile_macro, macro_text

ROOT = Path(__file__).resolve().parent


def stamp():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def key_id(scan, extended=False):
    return f"{'E0:' if extended else ''}{scan:02X}"


# Schematic positions; actual Raw Input scan codes, independent of OS language.
ROWS = [
    [("Esc", 1), *[(str(i % 10), i + 1) for i in range(1, 11)], ("-", 12), ("=", 13), ("Sil", 14, False, 2), ("Del", 83, True)],
    [("Tab", 15, False, 1.5), *[(k, 16 + i) for i, k in enumerate("QWERTYUIOP")], ("[", 26), ("]", 27), ("\\", 43), ("PgUp", 73, True)],
    [("Caps", 58, False, 1.8), *[(k, 30 + i) for i, k in enumerate("ASDFGHJKL")], (";", 39), ("'", 40), ("Enter", 28, False, 2), ("PgDn", 81, True)],
    [("Shift", 42, False, 2.2), *[(k, 44 + i) for i, k in enumerate("ZXCVBNM")], (",", 51), (".", 52), ("/", 53), ("Shift", 54, False, 1.8), ("↑", 72, True), ("End", 79, True)],
    [("Ctrl", 29, False, 1.3), ("Win", 91, True, 1.3), ("Alt", 56, False, 1.3), ("Boşluk", 57, False, 5),
     ("Alt", 56, True, 1.3), ("Fn", None, False, 1.3), ("Ctrl", 29, True, 1.3), ("←", 75, True), ("↓", 80, True), ("→", 77, True)],
]
KEY_NAMES = {}
for row in ROWS:
    for entry in row:
        label, scan, *extra = entry
        ext = extra[0] if extra else False
        if scan is not None:
            KEY_NAMES[key_id(scan, ext)] = label
KEY_NAMES.update({key_id(scan): f"F{i}" for i, scan in enumerate([*range(0x3B, 0x45), 0x57, 0x58, *range(0x64, 0x6F), 0x76], 1)})
KEY_NAMES.update({"38": "Sol Alt", "E0:38": "Sağ Alt", "E0:5B": "Sol Win", "1D": "Sol Ctrl", "E0:1D": "Sağ Ctrl"})


def main():
    parser = argparse.ArgumentParser(description="VGN X68 Studio command line")
    parser.add_argument("--inventory", action="store_true", help="Read device information without sending commands")
    parser.add_argument("--probe", action="store_true", help="Send the verified version / CRC query")
    parser.add_argument("--battery", action='store_true', help="Query the verified battery report (no settings writes)")
    parser.add_argument("--monitor-battery", action='store_true', help="Start GUI battery monitoring on launch")
    parser.add_argument("--samples", type=int, default=1, help="Number of battery reports (1-2000)")
    parser.add_argument("--interval", type=float, default=5, help="Seconds between battery queries (2-300)")
    parser.add_argument("--output", type=Path, help="Save CLI JSON output to a file")
    parser.add_argument("--smoke", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument('--verify-library',action='store_true',help='Build every patched firmware from the official payload and verify hashes; no device access')
    parser.add_argument('--offline',action='store_true',help='With --verify-library: use only the cached official payload')
    args = parser.parse_args()
    if args.verify_library:
        # Rebuilds every patched release from the cached official payload; no device access.
        from x68 import firmware_source
        from x68.desktop import CACHE
        import hashlib
        stock=firmware_source.stock(CACHE,download=not args.offline)
        result={'verified':True,'device_access':False,'builds':{label:hashlib.sha256(firmware_source.build(CACHE,label,download=False)).hexdigest() for label in firmware_source.BUILDS}}
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result));return 0
    if not 1 <= args.samples <= 2000 or not 2 <= args.interval <= 300:
        parser.error('samples must be 1-2000 and interval 2-300.')
    if args.inventory or args.probe or args.battery:
        try:
            client = X68Client()
            result = {"created_at": stamp()}
            if args.inventory or args.probe:
                result['inventory'] = client.inventory()
            if args.probe:
                result["version_query"] = client.query_version()
            if args.battery:
                from x68.battery import query_battery, BatteryHistory
                tracker = BatteryHistory()
                settings = SettingsClient(client, ROOT/'reports'/'backups')
                for index in range(args.samples):
                    try:
                        tracker.record(sample=query_battery(settings))
                    except Exception as error:
                        tracker.record(error=str(error))
                    result['battery'] = tracker.report()
                    if args.output:
                        args.output.parent.mkdir(parents=True, exist_ok=True)
                        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                    if index+1 < args.samples:
                        time.sleep(args.interval)
                result['battery_packets'] = settings.trace
            data = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(data, encoding="utf-8")
            print(data)
            return 0
        except Exception as error:
            print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
            return 1
    import tkinter as tk
    root = tk.Tk()
    from x68.desktop import Studio
    application = Studio(root, smoke=args.smoke)
    if args.monitor_battery and not args.smoke:
        application.battery_panel.start_monitor()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
