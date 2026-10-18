"""Regression checks for device matching, no-write guards and reply handling."""
import unittest
from unittest.mock import patch

from x68.protocol import DESCRIPTOR, VERSION_REQUEST, X68Client, ProtocolError, parse_version_response


TARGET = {"vendor_id": 0x320F, "product_id": 0x5055, "product_string": "SUBOR X68",
          "manufacturer_string": "Telink", "usage_page": 0xFFEF, "interface_number": 2,
          "path": b"verified-x68", "release_number": 0x113}
RESPONSE = bytes.fromhex("05 01 08 00 00 00 00 00 e6 1b 96 14") + bytes(52)


class Device:
    def __init__(self, descriptor=DESCRIPTOR):
        self.descriptor = descriptor
        self.writes = []
        self.closed = False

    def open_path(self, path):
        self.path = path

    def get_report_descriptor(self):
        return self.descriptor

    def write(self, value):
        self.writes.append(value)
        return len(value)

    def read(self, length, timeout):
        return RESPONSE if self.writes else []

    def close(self):
        self.closed = True


class Backend:
    def __init__(self, devices=None, descriptor=DESCRIPTOR):
        self.devices = [TARGET.copy()] if devices is None else devices
        self.handle = Device(descriptor)

    def enumerate(self, vid, pid):
        return self.devices

    def device(self):
        return self.handle


class ProtocolTests(unittest.TestCase):
    def test_mac_missing_interface_number_still_requires_exact_descriptor(self):
        with patch('x68.protocol.sys.platform','darwin'):
            good=Backend([{**TARGET,'interface_number':-1}]);X68Client(good).query_version()
            self.assertEqual(good.handle.writes,[VERSION_REQUEST])
            bad=Backend([{**TARGET,'interface_number':-1}],DESCRIPTOR[:-1])
            with self.assertRaises(ProtocolError):X68Client(bad).query_version()
            self.assertEqual(bad.handle.writes,[])
    def test_shared_vid_pid_other_model_refused_without_write(self):
        b = Backend([{**TARGET, "product_string": "ZUOYA GMK104"}])
        with self.assertRaises(ProtocolError):
            X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [])

    def test_changed_descriptor_refused_and_handle_closed(self):
        b = Backend(descriptor=DESCRIPTOR[:-1])
        with self.assertRaises(ProtocolError):
            X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [])
        self.assertTrue(b.handle.closed)

    def test_ambiguous_devices_refused_without_write(self):
        b = Backend([TARGET.copy(), {**TARGET, "path": b"other-x68"}])
        with self.assertRaises(ProtocolError):
            X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [])

    def test_inventory_does_not_write(self):
        b = Backend()
        self.assertEqual(X68Client(b).inventory()["usb_release_hex"], "0113")
        self.assertEqual(b.handle.writes, [])

    def test_only_exact_known_request_is_sent_once(self):
        b = Backend()
        result = X68Client(b).query_version()
        expected = bytes.fromhex("05 01 00 00") + bytes([255] * 29) + bytes(31)
        self.assertEqual(b.handle.writes, [expected])
        self.assertEqual(len(expected), 64)
        self.assertTrue(result["crc_matches_reference"])
        self.assertEqual(result["reported_crc"], "14961BE6")
        self.assertTrue(b.handle.closed)

    def test_rate_limit_prevents_second_write(self):
        b = Backend()
        c = X68Client(b)
        c.query_version()
        with self.assertRaises(ProtocolError):
            c.query_version()
        self.assertEqual(len(b.handle.writes), 1)

    def test_no_reply_times_out_without_retry(self):
        b = Backend()
        b.handle.read = lambda *args: []
        with patch("x68.protocol.time.monotonic", side_effect=[0, 0, 1, 2, 3, 6]):
            with self.assertRaisesRegex(ProtocolError, "No valid reply"):
                X68Client(b).query_version()
        self.assertEqual(b.handle.writes, [VERSION_REQUEST])
        self.assertTrue(b.handle.closed)

    def test_short_write_is_not_retried(self):
        b = Backend()
        def short_write(value):
            b.handle.writes.append(value)
            return 12
        b.handle.write = short_write
        with self.assertRaisesRegex(ProtocolError, "Incomplete write"):
            X68Client(b).query_version()
        self.assertEqual(len(b.handle.writes), 1)

    def test_truncated_or_wrong_header_response_refused(self):
        for value in (RESPONSE[:12], bytes(64), RESPONSE + b"\x00"):
            with self.subTest(value=value):
                with self.assertRaises(ProtocolError):
                    parse_version_response(value)

    def test_different_crc_is_not_called_corruption(self):
        reply = bytearray(RESPONSE)
        reply[8] ^= 1
        result = parse_version_response(bytes(reply))
        self.assertFalse(result["crc_matches_reference"])
        self.assertNotIn("corrupt", result)


if __name__ == "__main__":
    unittest.main()
