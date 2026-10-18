from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import battery_load_trial as trial


class FakeClient:
    def inventory(self):
        return {'product': 'SUBOR X68'}

    def query_version(self):
        return {'crc_matches_reference': True}


class FakeSettings:
    def __init__(self, *args):
        self.original = bytes([0, 1, 4, 2, 0, 255])+bytes(58)
        self.data = self.original
        self.trace = []
        self.writes = []
        self.restore_calls = 0
        self.concurrent_change = False

    def read_settings(self):
        return {'parameters_hex': self.data.hex(), 'keymap_hex': '12', 'macro_bank_hex': '00',
                'lighting_error': 'Unknown flag 255'}

    def _backup(self, kind, value):
        return 'test-backup'

    @contextmanager
    def _device(self):
        yield object()

    @contextmanager
    def _transaction(self, device):
        yield

    def _read(self, device, command, length):
        if self.concurrent_change:
            self.data = bytes([9])+self.data[1:]
            self.concurrent_change = False
        return self.data

    def _write(self, device, command, data):
        self.writes.append((command, data))
        self.data = data

    def restore(self, backup):
        self.restore_calls += 1
        self.data = self.original
        return {'restored': True}


class BatteryLoadTrialTests(unittest.TestCase):
    def setUp(self):
        self.settings = FakeSettings()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/'trial.json'
        for target, value in [('X68Client', FakeClient), ('SettingsClient', lambda *args: self.settings),
                              ('query_battery', lambda settings: {'level_raw': 0, 'status_raw': 1})]:
            patcher = patch.object(trial, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(trial.time, 'sleep')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_brightness_changes_and_all_other_bytes_survive(self):
        result = trial.run(self.output)
        self.assertTrue(result['restored'])
        self.assertEqual(len(self.settings.writes), 1)
        command, data = self.settings.writes[0]
        self.assertEqual(command, 6)
        self.assertEqual([i for i, pair in enumerate(zip(data, self.settings.original)) if pair[0] != pair[1]], [2])
        self.assertEqual(self.settings.restore_calls, 1)

    def test_failed_observation_still_restores_and_records_result(self):
        values = [{'level_raw': 0, 'status_raw': 1}]*3+[RuntimeError('USB timeout')]
        with patch.object(trial, 'query_battery', side_effect=values), self.assertRaises(RuntimeError):
            trial.run(self.output)
        self.assertEqual(self.settings.data, self.settings.original)
        report = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(report['restored'])
        self.assertEqual(report['experiment_error'], 'USB timeout')

    def test_concurrent_change_is_not_overwritten_by_restore(self):
        self.settings.concurrent_change = True
        with self.assertRaises(RuntimeError):
            trial.run(self.output)
        self.assertEqual(self.settings.writes, [])
        self.assertEqual(self.settings.restore_calls, 0)
        self.assertEqual(self.settings.data[0], 9)
