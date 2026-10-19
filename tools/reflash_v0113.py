"""Explicit one-shot OTA for stock V0113 or reviewed native display builds.

Without --write-firmware this performs an offline encoding check. Close other
keyboard software before writing and leave USB connected throughout the run.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from x68.firmware import validate_payload, validate_visual_patch, start_packet, data_packets, end_packet, result_code, V0113_CRC, NATIVE_SCREEN_SHA256
from x68.protocol import X68Client, ProtocolError
from x68.settings import SettingsClient
from x68.battery import query_battery


def reflash(payload, stock_reference=None, current_visual_reference=None, progress=None, allow_unreviewed=False, current_user_reference=None):
    if allow_unreviewed:
        from x68.firmware import inspect_custom_firmware
        if stock_reference is None:raise ValueError('The verified stock reference is required.')
        inspect_custom_firmware(payload,stock_reference)
    else:validate_payload(payload,stock_reference)
    # Historical exact-hash reviewed native builds: recognize them for update,
    # but never offer the earlier frozen-display versions as install targets.
    frames=list(data_packets(payload,stock_reference,allow_unreviewed=allow_unreviewed))
    final_frame=end_packet(payload,stock_reference,allow_unreviewed=allow_unreviewed)
    allowed_current_crcs = {V0113_CRC,int.from_bytes(payload[-4:],'little'),0xEF331DCE,0x4CB077DE,0xFC2EBCFE,0x3C866A9B,0x10EE7CA9,0x127F9EB4,0x1383FD83,0x41815162}
    if current_user_reference is not None:
        from x68.firmware import inspect_custom_firmware
        inspect_custom_firmware(current_user_reference,stock_reference)
        allowed_current_crcs.add(int.from_bytes(current_user_reference[-4:],'little'))
    if current_visual_reference is not None:
        validate_payload(current_visual_reference,stock_reference or payload)
        allowed_current_crcs.add(int.from_bytes(current_visual_reference[-4:],'little'))
    folder = ROOT/'reports'/'firmware-sessions'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    report_path = folder/'result.json'
    report = {'started_at': datetime.now().astimezone().isoformat(),
              'unreviewed_user_firmware':bool(allow_unreviewed),
              'payload_sha256': hashlib.sha256(payload).hexdigest(), 'phase': 'preflight',
              'packets_sent': 0, 'ota_result': None, 'acknowledgements': [],
              'firmware_kind': 'unreviewed_user_binary' if allow_unreviewed else ('native_display_renderer' if hashlib.sha256(payload).hexdigest() == NATIVE_SCREEN_SHA256 else ('native_visual_assets' if stock_reference is not None and payload != stock_reference else 'stock_v0113')),
              'claim': 'User binary behavior is unreviewed.' if allow_unreviewed else 'Reviewed display builds do not change charging logic. No charging repair is claimed.'}
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    client = X68Client()
    settings = SettingsClient(client, folder)
    device = None
    try:
        report['inventory_before'] = client.inventory()
        if report['inventory_before']['usb_release_hex'] != '0113':
            raise ProtocolError('USB revision is not the verified 0113 target.')
        report['version_before'] = client.query_version()
        if int(report['version_before']['reported_crc'],16) not in allowed_current_crcs:
            raise ProtocolError('Current reported CRC differs from the investigated target.')
        before = settings.read_settings()
        (folder/'settings-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2),encoding='utf-8')
        report['backups'] = {kind: settings._backup(kind, bytes.fromhex(before[key]))
                              for kind,key in [('lighting','parameters_hex'),('keymap','keymap_hex'),('macros','macro_bank_hex')]}
        report['battery_before'] = query_battery(settings)
        vendor = client._vendor_device()
        device = client.backend.device()
        device.open_path(vendor['path'])
        client._verify_descriptor(device)
        until = time.monotonic()+0.1
        while time.monotonic() < until and device.read(64,10):
            pass
        report['phase'] = 'writing'
        save()

        def send(frame, final=False):
            if device.write(frame) != 64:
                raise ProtocolError('Short OTA write; no blind retry sent.')
            report['packets_sent'] += 1
            until = time.monotonic()+5
            while time.monotonic() < until:
                reply = bytes(device.read(64,200))
                if not reply:
                    continue
                code = result_code(reply)
                if code is not None:
                    report['ota_result'] = code
                    report['acknowledgements'].append(reply.hex(' '))
                    save()
                    if code != 0:
                        raise ProtocolError(f'Device rejected OTA with result {code}.')
                    if final:
                        return
                    raise ProtocolError('Unexpected early OTA completion; stopped.')
                if reply == frame:
                    if not final:
                        return
                    continue
                report['acknowledgements'].append({'unexpected': reply.hex(' ')})
                save()
                raise ProtocolError('OTA response differs from the verified echo format; stopped without retry.')
            raise ProtocolError('OTA response timed out; no blind retry sent.')

        send(start_packet())
        for index, frame in enumerate(frames):
            send(frame)
            if progress is not None and index % 50 == 0:
                progress(index+1, len(frames))
            if index % 100 == 0:
                report['data_packets_done'] = index+1
                save()
            if index % 500 == 0:
                print(f'Firmware {index+1}/{len(frames)} packets',flush=True)
        send(final_frame, final=True)
        report['phase'] = 'waiting_for_device'
        save()
        device.close()
        device = None
        deadline = time.monotonic()+30
        time.sleep(3)
        last_error = None
        while time.monotonic() < deadline:
            try:
                report['version_after'] = client.query_version()
                break
            except Exception as error:
                last_error = str(error)
                time.sleep(2)
        else:
            raise ProtocolError('No post-update version response: '+str(last_error))
        report['expected_crc'] = f'{int.from_bytes(payload[-4:],"little"):08X}'
        if report['version_after']['reported_crc'] != report['expected_crc']:
            raise ProtocolError('Post-update CRC differs from the validated payload.')
        after = settings.read_settings()
        # Stock initialization can reset the global RGB defaults on reboot.
        # Restore only the documented RGB fields, never a whole stale parameter
        # block or any unreviewed image's unknown settings layout.
        rgb_offsets=(1,2,3,5,6,7,8)
        old_params=bytes.fromhex(before['parameters_hex']);new_params=bytes.fromhex(after['parameters_hex'])
        if not allow_unreviewed and before.get('lighting') and any(old_params[i]!=new_params[i] for i in rgb_offsets):
            light=before['lighting']
            report['lighting_restored']=settings.set_lighting(light['mode'],light['brightness'],light['speed'],light['rainbow'],light['color'])
            after=settings.read_settings()
        # Stock boot initialization can reset custom actions after an OTA.
        # Restore the exact saved banks through the checked backup writer.
        if not allow_unreviewed:
            for kind,key in (('macros','macro_bank_hex'),('keymap','keymap_hex')):
                if before[key] != after[key]:
                    report[kind+'_restored']=settings.restore(report['backups'][kind])
                    after=settings.read_settings()
        (folder/'settings-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
        report['settings_preserved'] = {key:before[key] == after[key]
                                        for key in ('parameters_hex','keymap_hex','macro_bank_hex')}
        report['battery_after'] = query_battery(settings)
        report['phase'] = 'complete'
    except Exception as error:
        report['error'] = str(error)
        report['stopped_in_phase'] = report['phase']
        report['phase'] = 'stopped'
        raise
    finally:
        if device is not None:
            device.close()
        report['finished_at'] = datetime.now().astimezone().isoformat()
        save()
        print('Firmware session report: '+str(report_path),flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload',type=Path)
    parser.add_argument('--write-firmware',action='store_true')
    parser.add_argument('--stock-reference',type=Path,help='Exact original V0113 required for an asset-only patch')
    parser.add_argument('--current-visual-reference',type=Path,help='Validated previous visual build, for rollback to stock')
    args = parser.parse_args()
    payload = args.payload.read_bytes()
    stock_reference=args.stock_reference.read_bytes() if args.stock_reference else None
    current_reference=args.current_visual_reference.read_bytes() if args.current_visual_reference else None
    validate_payload(payload,stock_reference)
    frames=list(data_packets(payload,stock_reference))
    print(json.dumps({'offline_validated':True,'data_packets':len(frames),
                      'start':start_packet().hex(' '),'end':end_packet(payload,stock_reference).hex(' ')}),flush=True)
    if args.write_firmware:
        result = reflash(payload,stock_reference,current_reference)
        print(json.dumps({'phase':result['phase'],'ota_result':result['ota_result'],
                          'settings_preserved':result.get('settings_preserved'),
                          'battery_after':result.get('battery_after')},ensure_ascii=True))


if __name__ == '__main__':
    main()
