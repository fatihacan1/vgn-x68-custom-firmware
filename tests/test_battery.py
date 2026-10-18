import unittest
from x68.protocol import ProtocolError
from x68.settings import settings_packet
from x68.battery import decode_battery, BatteryHistory, query_battery


def sample(level=0, status=1):
    return {'observed_at': '2026-10-18T01:00:00+03:00', 'transport': 'available',
            **decode_battery(bytes([level, status, 0, 0, 0, 0]))}


class BatteryTests(unittest.TestCase):
    def test_exact_live_verified_request(self):
        packet = settings_packet(26, size=6)
        self.assertEqual(packet, bytes.fromhex('04 20 00 1a 06 00 00 00')+bytes(56))

    def test_no_parameter_sweep_possible_for_battery(self):
        for offset, size in [(1, 5), (0, 1), (0, 7), (0, 56)]:
            with self.subTest(offset=offset, size=size), self.assertRaises(ProtocolError):
                settings_packet(26, offset, size=size)

    def test_live_payload_does_not_become_a_guessed_percent_or_charging_state(self):
        result = decode_battery(bytes([0, 1, 0, 0, 0, 0]))
        self.assertEqual(result['level_raw'], 0)
        self.assertEqual(result['status_bits'], '00000001')
        self.assertEqual(result['reported_percent'], 0)
        for field in ('percent', 'charging', 'battery_present', 'voltage_mv', 'current_ma'):
            self.assertIsNone(result[field])

    def test_unfamiliar_bytes_are_preserved_not_clamped(self):
        result = decode_battery(bytes([255, 128, 1, 2, 3, 4]))
        self.assertEqual(result['level_raw'], 255)
        self.assertEqual(result['other_bytes_hex'], '01 02 03 04')
        self.assertIsNone(result['percent'])
        self.assertIsNone(result['reported_percent'])

    def test_full_override_is_reported_without_claiming_physical_full_or_charging(self):
        result = decode_battery(bytes([100, 2, 0, 0, 0, 0]))
        self.assertEqual(result['reported_percent'], 100)
        self.assertTrue(result['firmware_full_override'])
        self.assertIsNone(result['percent'])
        self.assertIsNone(result['charging'])

    def test_bad_payload_length_refused(self):
        for value in (bytes(), bytes(5), bytes(7)):
            with self.assertRaises(ProtocolError):
                decode_battery(value)

    def test_unplug_does_not_fabricate_zero_and_reconnect_is_recorded(self):
        h = BatteryHistory()
        h.record(sample(77, 1))
        h.record(error='USB disconnected')
        h.record(error='Still unavailable')
        self.assertIsNone(h.samples[-1]['level_raw'])
        self.assertEqual(h.summary()['last_success']['level_raw'], 77)
        self.assertEqual(h.connection_losses, 1)
        h.record(sample(78, 2))
        self.assertTrue(h.summary()['level_changed_in_retained_samples'])
        self.assertEqual(h.summary()['errors'], 2)

    def test_history_is_bounded_and_notes_are_distinct_from_measurements(self):
        h = BatteryHistory(limit=2)
        for level in (1, 2, 3):
            h.record(sample(level))
        h.add_note('Kablo çıkarıldı, ekran söndü')
        self.assertEqual(len(h.samples), 2)
        self.assertEqual(h.summary()['successes'], 3)
        self.assertEqual(h.notes[0]['source'], 'user_observation')
        self.assertEqual(h.samples[-1]['level_raw'], 3)

    def test_long_disconnect_keeps_last_real_measurement(self):
        h = BatteryHistory(limit=2)
        h.record(sample(77, 1))
        for _ in range(3):
            h.record(error='USB disconnected')
        self.assertEqual(h.summary()['last_success']['level_raw'], 77)
        self.assertIsNone(h.samples[-1]['level_raw'])

    def test_query_sends_only_one_battery_read_without_begin_end_or_settings_write(self):
        from contextlib import contextmanager
        class FakeSettings:
            calls = []
            @contextmanager
            def _device(self):
                yield 'device'
            def _exchange(self, device, command, **kwargs):
                self.calls.append((command, kwargs))
                return bytes([0, 1, 0, 0, 0, 0])
        settings = FakeSettings()
        self.assertEqual(query_battery(settings)['transport'], 'available')
        self.assertEqual(settings.calls, [(26, {'size': 6})])


if __name__ == '__main__':
    unittest.main()
