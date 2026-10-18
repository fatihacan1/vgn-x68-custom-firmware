import unittest
from x68.battery_health import estimate, ChargeTrend


def snap(scaled, pe4=True):
    return {'observed_at': '2026-10-18T18:46:31+03:00', 'scaled_code_units': scaled,
            'lower_threshold_code_units': 1510, 'upper_threshold_code_units': 2035, 'pe4': pe4}


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class HealthTests(unittest.TestCase):
    def test_owner_multimeter_reading_matches_estimate(self):
        result = estimate(snap(41))
        self.assertAlmostEqual(result['pack_volts_estimate'], 0.082)
        self.assertEqual(result['state'], 'dead')
        self.assertEqual(result['percent_estimate'], 0)

    def test_thresholds_map_to_li_ion_window(self):
        self.assertAlmostEqual(estimate(snap(1510))['empty_volts_estimate'], 3.02)
        self.assertAlmostEqual(estimate(snap(1510))['full_volts_estimate'], 4.07)
        self.assertEqual(estimate(snap(1900))['state'], 'ok')
        self.assertEqual(estimate(snap(2035))['percent_estimate'], 100)

    def test_disconnected_line_and_charger_only_output(self):
        self.assertEqual(estimate(snap(12))['state'], 'no_voltage')
        self.assertEqual(estimate(snap(2200))['state'], 'high')

    def test_trend_needs_two_minutes(self):
        clock = Clock()
        trend = ChargeTrend(now=clock)
        for v in (3.5, 3.51, 3.52):
            trend.add(v)
            clock.t += 30
        self.assertEqual(trend.verdict(True)[0], 'collecting')

    def test_rising_flat_and_falling(self):
        for step, power, expected in ((0.01, True, 'charging'), (0.0, True, 'not_charging'),
                                      (-0.01, False, 'discharging'), (0.0, False, 'steady')):
            clock = Clock()
            trend = ChargeTrend(now=clock)
            for i in range(10):
                trend.add(3.6 + step * i)
                clock.t += 30
            self.assertEqual(trend.verdict(power)[0], expected)

    def test_window_drops_old_points(self):
        clock = Clock()
        trend = ChargeTrend(window_s=60, now=clock)
        for _ in range(5):
            trend.add(1.0)
            clock.t += 30
        self.assertLessEqual(len(trend.points), 3)
