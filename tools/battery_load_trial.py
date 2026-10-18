"""Bounded X68 RGB-off comparison. Never changes charging or firmware controls.

Close other X68 Lab instances before running. Keep USB connected until restore.
Only an exact supported X68 with the reference reported CRC is accepted.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from x68.protocol import X68Client, ProtocolError
from x68.settings import SettingsClient
from x68.battery import query_battery


def run(output: Path):
    client = X68Client()
    settings = SettingsClient(client, ROOT/'reports'/'backups')
    report = {'experiment': 'RGB off / original RGB battery-report comparison',
              'started_at': datetime.now().astimezone().isoformat(),
              'limitation': 'No current or voltage is measured. Unchanged reports do not prove absence of charging.',
              'samples': [], 'restored': False}

    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def observe(phase, count, interval):
        for index in range(count):
            sample = query_battery(settings)
            report['samples'].append({'phase': phase, **sample})
            save()
            if index+1 < count:
                time.sleep(interval)

    report['inventory'] = client.inventory()
    report['version'] = client.query_version()
    if not report['version']['crc_matches_reference']:
        raise ProtocolError('Reference CRC mismatch; RGB trial was not started.')
    before = settings.read_settings()
    original = bytes.fromhex(before['parameters_hex'])
    if len(original) != 64 or original[2] > 4:
        raise ProtocolError('Brightness byte is outside the verified range; nothing changed.')
    if original[2] == 0:
        raise ProtocolError('Brightness is already zero; this comparison cannot reduce the lighting load.')
    backup = settings._backup('lighting', original)
    report['original_lighting_backup'] = backup
    report['original_parameters_hex'] = original.hex(' ')
    report['original_brightness'] = original[2]
    report['unrecognized_lighting_fields'] = before['lighting_error']
    save()
    restore_needed = False
    try:
        observe('baseline', 3, 2)
        desired = bytearray(original)
        desired[2] = 0
        with settings._device() as device:
            if settings._read(device, 5, 64) != original:
                raise ProtocolError('Settings changed during baseline; no trial write was sent.')
            if original != desired:
                # Set immediately before writing so a failed write also restores.
                restore_needed = True
                with settings._transaction(device):
                    settings._write(device, 6, bytes(desired))
            if settings._read(device, 5, 64) != desired:
                raise ProtocolError('Brightness-zero readback mismatch.')
        report['rgb_off_operation'] = {'changed': original != desired,
                                      'only_changed_byte_offset': 2,
                                      'parameters_hex': desired.hex(' ')}
        observe('rgb_off', 11, 3)
    except Exception as error:
        report['experiment_error'] = str(error)
        raise
    finally:
        if restore_needed:
            try:
                report['restore_operation'] = settings.restore(backup)
                after = settings.read_settings()
                report['unchanged_after_restore'] = {
                    key: before[key] == after[key]
                    for key in ('parameters_hex', 'keymap_hex', 'macro_bank_hex')}
                report['restored'] = all(report['unchanged_after_restore'].values())
            except Exception as error:
                report['restore_error'] = str(error)
        report['packets'] = settings.trace
        save()
    if not report['restored']:
        raise ProtocolError('Original settings restoration could not be verified; inspect the report and backup.')
    observe('restored', 3, 2)
    report['finished_at'] = datetime.now().astimezone().isoformat()
    report['packets'] = settings.trace
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-rgb-trial', action='store_true', required=True,
                        help='Explicitly enable this reversible RGB settings write trial')
    parser.add_argument('--output', type=Path, default=ROOT/'reports'/'battery-rgb-trial.json')
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({'output': str(args.output), 'restored': result['restored'],
                      'samples': len(result['samples']),
                      'values': sorted({(s['level_raw'], s['status_raw']) for s in result['samples']})}))
    return 0 if result['restored'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
