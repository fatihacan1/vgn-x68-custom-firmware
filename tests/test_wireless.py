"""Receiver (320F:5088) matching: layout-checked descriptors, firmware and media stay wired."""
import unittest

from x68.protocol import DESCRIPTOR, VERSION_REQUEST, X68Client, ProtocolError, collection_reports, WIRELESS_VENDOR_REPORTS
from x68.settings import SettingsClient, SETTINGS_DESCRIPTOR, WIRELESS_SETTINGS_REPORTS
from tests.test_protocol import Backend, TARGET

# Interface 1 of the receiver as macOS reports it (all collections in one descriptor).
RECEIVER = bytes.fromhex(
    "05010906a101850105071904297015002501750195788102c005010980a101850205011981298315002501950375018102950175058101c0"
    "050c0901a1018503150026ff1f19002aff1f751095018100c0061cff0992a101850419002aff00150026ff007508953f910019002aff008100c0"
    "06efff0900a1018505150026ff00953f75080901810209029102c005010902a10185060901a1000509190129051500250195057501810295"
    "017503810105010930093116008026ff7f75109502810609381581257f750895018106050c0a38021581257f750895018106c0c0")
class ReceiverBackend(Backend):
    def enumerate(self, vid, pid):
        return [d for d in self.devices if d["product_id"] == pid]


WIRELESS = {**TARGET, "product_id": 0x5088, "product_string": "Wireless Gaming Keyboard", "interface_number": 1}


class WirelessTests(unittest.TestCase):
    def test_receiver_layout_matches_wired_reports(self):
        self.assertEqual(collection_reports(RECEIVER, 0xFFEF, 0), WIRELESS_VENDOR_REPORTS)
        self.assertEqual(collection_reports(RECEIVER, 0xFF1C, 0x92), WIRELESS_SETTINGS_REPORTS)
        self.assertEqual(collection_reports(DESCRIPTOR, 0xFFEF, 0), WIRELESS_VENDOR_REPORTS | {(5, 'feature', 8, 63)})
        self.assertEqual(collection_reports(SETTINGS_DESCRIPTOR, 0xFF1C, 0x92), WIRELESS_SETTINGS_REPORTS)

    def test_version_query_over_receiver(self):
        b = ReceiverBackend([WIRELESS], RECEIVER)
        self.assertEqual(X68Client(b).inventory()["transport"], "wireless")
        X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [VERSION_REQUEST])

    def test_wrong_receiver_layout_refused_without_write(self):
        b = ReceiverBackend([WIRELESS], RECEIVER.replace(bytes.fromhex("953f7508"), bytes.fromhex("95207508")))
        with self.assertRaises(ProtocolError):
            X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [])

    def test_firmware_and_media_paths_never_use_receiver(self):
        b = ReceiverBackend([WIRELESS], RECEIVER)
        with self.assertRaises(ProtocolError):
            X68Client(b)._vendor_device()
        settings = SettingsClient(X68Client(ReceiverBackend([{**WIRELESS, "usage_page": 0xFF1C, "usage": 0x92}], RECEIVER)), None)
        with self.assertRaises(ProtocolError):
            with settings._device(wireless=False):
                pass
        with settings._device():
            pass


if __name__ == "__main__":
    unittest.main()
