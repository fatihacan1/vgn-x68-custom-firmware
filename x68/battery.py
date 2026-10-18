"""Battery report 0x1A. Field semantics are deliberately conservative.

The original X68 dispatcher handles 0x1A at 0x2001BA0C. It updates a cached
measurement timestamp and returns one level byte and one GPIO-derived status
byte. No calibrated voltage, current or documented charger-control command has
been established. WOB Protocol C names this request GetBatteryInformationCom.
"""
from __future__ import annotations

from datetime import datetime
import time

from .protocol import ProtocolError

BATTERY_LIMITATION = (
    "The firmware's 0-100 battery indicator is read; its calibration and freshness are unverified. "
    "The physical charging meaning of the status byte is unverified. "
    "This report is not a battery voltage, charging current or battery health measurement."
)


def decode_battery(payload: bytes) -> dict:
    if len(payload) != 6:
        raise ProtocolError("The battery reply must be exactly 6 bytes.")
    return {
        "level_raw": payload[0],
        "status_raw": payload[1],
        "status_bits": f"{payload[1]:08b}",
        "other_bytes_hex": payload[2:].hex(" "),
        "payload_hex": payload.hex(" "),
        "reported_percent": payload[0] if payload[0] <= 100 and (payload[1] in (0, 1) or (payload[1] == 2 and payload[0] == 100)) else None,
        "reported_percent_note": "The keyboard's own 0-100 indicator, not an independent state-of-charge measurement.",
        "firmware_full_override": payload[0] == 100 and payload[1] == 2,
        "percent": None,
        "charging": None,
        "battery_present": None,
        "voltage_mv": None,
        "current_ma": None,
        "limitation": BATTERY_LIMITATION,
    }


def query_battery(settings_client) -> dict:
    with settings_client._device() as device:
        payload = settings_client._exchange(device, 26, size=6)
    return {
        "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "transport": "available",
        "source": "X68 report 04 / command 1A, 6-byte response",
        **decode_battery(payload),
    }


class BatteryHistory:
    def __init__(self, limit=2000):
        self.limit = limit
        self.samples = []
        self.notes = []
        self.started = time.monotonic()
        self.connection_losses = 0
        self.last_available = None
        self.total_successes = 0
        self.total_errors = 0
        self.last_successful_sample = None

    def record(self, sample=None, error=None):
        if (sample is None) == (error is None):
            raise ValueError("Provide one successful sample or one error")
        if error is not None:
            value = {
                "observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "transport": "unavailable",
                "level_raw": None,
                "status_raw": None,
                "reported_percent": None,
                "error": str(error),
            }
            self.total_errors += 1
        else:
            value = dict(sample)
            self.total_successes += 1
        available = value['transport'] == 'available'
        if self.last_available is True and not available:
            self.connection_losses += 1
        self.last_available = available
        value['elapsed_s'] = round(time.monotonic()-self.started, 2)
        if available:
            self.last_successful_sample = dict(value)
        self.samples.append(value)
        if len(self.samples) > self.limit:
            del self.samples[:-self.limit]
        return value

    def add_note(self, text):
        text = text.strip()
        if text:
            self.notes.append({"observed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                               "elapsed_s": round(time.monotonic()-self.started, 2),
                               "source": "user_observation", "text": text[:500]})
            self.notes = self.notes[-200:]

    def summary(self):
        valid = [s for s in self.samples if s['transport'] == 'available']
        levels = [s['level_raw'] for s in valid]
        return {
            "session_seconds": round(time.monotonic()-self.started, 1),
            "successes": self.total_successes,
            "errors": self.total_errors,
            "retained_samples": len(self.samples),
            "connection_losses": self.connection_losses,
            "last_attempt": self.samples[-1] if self.samples else None,
            "last_success": self.last_successful_sample,
            "min_level_raw": min(levels) if levels else None,
            "max_level_raw": max(levels) if levels else None,
            "level_changed_in_retained_samples": len(set(levels)) > 1,
        }

    def report(self):
        return {"summary": self.summary(), "samples": self.samples, "observations": self.notes,
                "limitation": BATTERY_LIMITATION,
                "disconnection_note": "Losing USB access is not a new 0% reading. The last successful value is kept with its time."}
