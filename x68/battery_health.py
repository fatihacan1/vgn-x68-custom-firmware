"""Pack-voltage estimate and charge trend from the 0.6.0 diagnostic snapshot.

The native battery routine compares its scaled ADC value against 1510 and 2035.
Read as millivolts at the ADC pin behind a 1:2 divider, these are 3.02 V and
4.07 V at the pack: the usual empty/full window of a single Li-ion cell. The
owner's multimeter reading (0.08 V) matched the estimate from the same scale
(41 units -> 0.082 V). The divider ratio is inferred, not read from a schematic,
so every value here is labelled as an estimate.
"""
from __future__ import annotations

import time

DIVIDER_RATIO = 2
ASSUMPTION = (
    "Estimate: native ADC units read as millivolts at the sense pin behind an "
    "inferred 1:2 divider. Firmware thresholds 1510/2035 map to 3.02/4.07 V."
)

# (upper bound in volts, state, headline, advice steps)
VERDICTS = [
    (0.05, "no_voltage", "No voltage on the battery line.",
     ["Check that the battery connector is fully seated.",
      "If it is, the pack's protection board has cut the cell off. Jump-start it as below.",
      "Unplug the pack. Clip a slow source to the cell tabs (B+ / B-) behind the protection board.",
      "Back at 3.0 V, plug it in with USB and press Start monitoring here."]),
    (2.0, "dead", "Deeply discharged. Jump-start it.",
     ["Unplug the pack from the keyboard.",
      "Slow source: two AA cells in series through 10-33 ohm, or USB 5 V through 100 ohm. Red to B+, black to B-.",
      "If a small protection board sits on the pack, clip to the cell tabs behind it, not the wire ends.",
      "Measure every 10 minutes. Stop if the pack gets warm or swells.",
      "At 3.0 V, plug it back in with USB and press Start monitoring. Rising voltage means the keyboard charges it."]),
    (3.0, "over_discharged", "Low but recoverable.",
     ["Keep USB connected and press Start monitoring.",
      "Rising voltage within a few minutes means the keyboard's charger is working.",
      "Flat line: keep the slow source on until 3.0 V, then try again."]),
    (3.5, "low", "Low. Charge before wireless use.",
     ["Keep USB connected. Voltage should rise steadily while charging."]),
    (4.25, "ok", "Battery voltage looks healthy.",
     ["Nothing to do. Use monitoring to watch it charge or discharge."]),
    (float("inf"), "high", "Voltage above a normal Li-ion cell.",
     ["This often means no battery is attached and the charger output is being read.",
      "Check the connector, then read again."]),
]


def estimate(snapshot: dict) -> dict:
    scaled = snapshot["scaled_code_units"]
    lower = snapshot["lower_threshold_code_units"]
    upper = snapshot["upper_threshold_code_units"]
    volts = round(scaled * DIVIDER_RATIO / 1000, 3)
    for bound, state, headline, steps in VERDICTS:
        if volts < bound:
            break
    percent = None
    if upper > lower:
        percent = max(0, min(100, round(100 * (scaled - lower) / (upper - lower))))
    return {
        "observed_at": snapshot["observed_at"],
        "pack_volts_estimate": volts,
        "empty_volts_estimate": lower * DIVIDER_RATIO / 1000,
        "full_volts_estimate": upper * DIVIDER_RATIO / 1000,
        "percent_estimate": percent,
        "state": state,
        "headline": headline,
        "steps": steps,
        # PE4 drops with USB removed (HID status 0); treated as external power.
        "external_power": snapshot["pe4"],
        "assumption": ASSUMPTION,
    }


class ChargeTrend:
    """Least-squares slope of the pack estimate over a sliding window."""

    def __init__(self, window_s=900, now=time.monotonic):
        self.window_s = window_s
        self.now = now
        self.points = []

    def add(self, volts):
        t = self.now()
        self.points.append((t, volts))
        self.points = [p for p in self.points if t - p[0] <= self.window_s]

    def clear(self):
        self.points.clear()

    def slope_mv_per_min(self):
        if len(self.points) < 3:
            return None
        n = len(self.points)
        mt = sum(t for t, _ in self.points) / n
        mv = sum(v for _, v in self.points) / n
        den = sum((t - mt) ** 2 for t, _ in self.points)
        if den == 0:
            return None
        return sum((t - mt) * (v - mv) for t, v in self.points) / den * 60000

    def span_s(self):
        return self.points[-1][0] - self.points[0][0] if self.points else 0

    def verdict(self, external_power):
        slope = self.slope_mv_per_min()
        if slope is None or self.span_s() < 120:
            return "collecting", "Collecting readings. Keep monitoring for at least 2 minutes."
        if slope >= 2:
            return "charging", f"Charging: voltage rising {slope:+.1f} mV/min."
        if slope <= -2:
            return "discharging", f"Discharging: voltage falling {slope:+.1f} mV/min."
        if external_power and self.points[-1][1] < 4.0:
            return "not_charging", (f"Not charging: USB power present but voltage flat ({slope:+.1f} mV/min) "
                                    "over the last few minutes.")
        return "steady", f"Steady ({slope:+.1f} mV/min)."
