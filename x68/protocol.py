"""Only the verified version/CRC request is allowed to leave this module.

No uploader code, vendor executable, firmware payload or arbitrary-write API.
"""
from __future__ import annotations

import hashlib
import sys
import threading
import time
from typing import Any

VID, PID = 0x320F, 0x5055
PRODUCT = "SUBOR X68"
MANUFACTURER = "Telink"
USAGE_PAGE = 0xFFEF
REFERENCE_CRC = 0x14961BE6
REFERENCE_SHA256 = "cdf4535a909900c7644e496d415552c6b210f0f87afb77c80a54782e571bd771"
DESCRIPTOR = bytes.fromhex(
    "06 ef ff 09 00 a1 01 85 05 09 01 15 00 26 ff 00 75 08 95 3f 81 02 "
    "09 02 15 00 26 ff 00 75 08 95 3f 91 02 "
    "09 03 15 00 26 ff 00 75 08 95 3f b1 02 c0"
)
# Official Get Device Fw Version: report 5, 32-byte payload, zero padding.
VERSION_REQUEST = bytes([5, 1, 0, 0] + [255] * 29 + [0] * 31)


class ProtocolError(RuntimeError):
    pass


def is_target(device: dict) -> bool:
    return (
        device.get("vendor_id") == VID
        and device.get("product_id") == PID
        and device.get("product_string") == PRODUCT
        and device.get("manufacturer_string") == MANUFACTURER
    )


def interface_matches(device, number):
    # hidapi on macOS may omit USB interface numbers. Usage, product identity
    # and the complete report descriptor are still mandatory before any write.
    return device.get('interface_number') == number or (sys.platform=='darwin' and device.get('interface_number') in (-1,None))


def parse_version_response(response: bytes) -> dict:
    if len(response) != 64 or response[:4] != bytes([5, 1, 8, 0]):
        raise ProtocolError("The version reply has an unexpected length or header.")
    version = int.from_bytes(response[4:8], "little")
    crc = int.from_bytes(response[8:12], "little")
    return {
        "version_field": f"0x{version:08X}",
        "version_note": "This field has not been confirmed to be the real version number.",
        "reported_crc": f"{crc:08X}",
        "reference_crc": f"{REFERENCE_CRC:08X}",
        "crc_matches_reference": crc == REFERENCE_CRC,
        "limitation": "The reported CRC is compared; the whole flash is not read.",
    }


def serialize_device(device: dict) -> dict:
    result = dict(device)
    result["path"] = device["path"].decode(errors="replace")
    return result


class X68Client:
    def __init__(self, backend: Any = None):
        if backend is None:
            import hid
            backend = hid
        self.backend = backend
        self.lock = threading.Lock()
        self.last_query = -float("inf")

    def _vendor_device(self) -> dict:
        matches = [
            d for d in self.backend.enumerate(VID, PID)
            if is_target(d) and d.get("usage_page") == USAGE_PAGE
            and interface_matches(d,2)
        ]
        if len(matches) != 1:
            raise ProtocolError(
                f"Exactly one wired X68 management interface is required; found {len(matches)}. "
                "Check the cable and the wired-mode switch."
            )
        return matches[0]

    @staticmethod
    def _verify_descriptor(device) -> bytes:
        descriptor = bytes(device.get_report_descriptor())
        if descriptor != DESCRIPTOR:
            raise ProtocolError("HID descriptor did not match. No command was sent to the device.")
        return descriptor

    def inventory(self) -> dict:
        with self.lock:
            devices = [d for d in self.backend.enumerate(VID, PID) if is_target(d)]
            if not devices:
                raise ProtocolError("No wired SUBOR X68 found.")
            vendor = self._vendor_device()
            handle = self.backend.device()
            try:
                handle.open_path(vendor["path"])
                descriptor = self._verify_descriptor(handle)
            finally:
                handle.close()
            return {
                "product": PRODUCT,
                "manufacturer": MANUFACTURER,
                "vid_pid": "320F:5055",
                "usb_release_hex": f"{vendor['release_number']:04X}",
                "interfaces": [serialize_device(d) for d in devices],
                "vendor_report_descriptor": descriptor.hex(" "),
                "descriptor_sha256": hashlib.sha256(descriptor).hexdigest(),
                "report_lengths": {"input": 64, "output": 64, "feature": 64},
                "battery": None,
                "charging": None,
                "unsupported": ["Calibrated battery percentage / charging current", "Factory reset", "Firmware writing"],
            }

    def query_version(self) -> dict:
        with self.lock:
            if time.monotonic() - self.last_query < 2:
                raise ProtocolError("Wait at least 2 seconds between queries.")
            vendor = self._vendor_device()
            handle = self.backend.device()
            try:
                handle.open_path(vendor["path"])
                self._verify_descriptor(handle)
                # Drain stale reports for at most 100 ms before the one request.
                until = time.monotonic() + 0.1
                while time.monotonic() < until and handle.read(64, 10):
                    pass
                self.last_query = time.monotonic()
                written = handle.write(VERSION_REQUEST)
                if written != len(VERSION_REQUEST):
                    raise ProtocolError(f"Incomplete write: {written}/64 bytes. It was not resent.")
                deadline = time.monotonic() + 3
                unrelated = 0
                while time.monotonic() < deadline:
                    response = bytes(handle.read(64, 250))
                    if not response:
                        continue
                    if response[:4] != bytes([5, 1, 8, 0]):
                        unrelated += 1
                        continue
                    return {
                        "operation": "version_crc_query",
                        "request_hex": VERSION_REQUEST.hex(" "),
                        "response_hex": response.hex(" "),
                        "ignored_unrelated_reports": unrelated,
                        **parse_version_response(response),
                    }
                raise ProtocolError("No valid reply within 3 seconds. No further command was sent.")
            finally:
                handle.close()
