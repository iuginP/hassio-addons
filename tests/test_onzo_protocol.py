import importlib.util
import os
import struct
import unittest
from unittest import mock
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "onzo_smart_energy/protocol.py"
SPEC = importlib.util.spec_from_file_location("onzo_protocol", MODULE_PATH)
protocol = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(protocol)


class FakeHIDDevice:
    def __init__(self, reads=()):
        self.reads = list(reads)
        self.writes = []
        self.opened_path = None
        self.closed = False

    def open_path(self, path):
        self.opened_path = path

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def read(self, size, timeout):
        return self.reads.pop(0)

    def close(self):
        self.closed = True


class ReportIdHIDDevice(FakeHIDDevice):
    def write(self, data):
        self.writes.append(bytes(data))
        if len(data) != 65 or data[0] != 0:
            return 0
        return len(data)


class OnzoProtocolTests(unittest.TestCase):
    def test_connection_targets_an_enumerated_hid_path(self):
        device = FakeHIDDevice()
        connection = protocol.Connection(b"/dev/hidraw7", device_factory=lambda: device)
        connection.connect()
        connection.disconnect()
        self.assertEqual(device.opened_path, b"/dev/hidraw7")
        self.assertTrue(device.closed)

    def test_connection_reports_an_unmapped_hidraw_device(self):
        connection = protocol.Connection(b"/dev/hidraw0")
        with mock.patch.object(os.path, "exists", return_value=False):
            with self.assertRaisesRegex(
                protocol.ProtocolError, "is not mapped into the add-on"
            ):
                connection.connect()

    def test_message_framing_round_trips_multiple_hid_frames(self):
        payload = b"x" * 70
        first = bytes([0, 62]) + payload[:62]
        second = bytes([1, 8]) + payload[62:] + b"\xff" * 54
        device = FakeHIDDevice([first, second])
        connection = protocol.Connection(b"path", device_factory=lambda: device)
        connection.connect()
        connection.message_send(payload)
        self.assertEqual(len(device.writes), 2)
        self.assertTrue(all(len(report) == 65 for report in device.writes))
        self.assertTrue(all(report[0] == 0 for report in device.writes))
        self.assertEqual(connection.message_receive(), payload)

    def test_message_send_includes_hidapi_report_id(self):
        device = ReportIdHIDDevice()
        connection = protocol.Connection(b"path", device_factory=lambda: device)
        connection.connect()

        connection.message_send(b"request")

        self.assertEqual(len(device.writes[0]), 65)
        self.assertEqual(device.writes[0][0], 0)
        self.assertEqual(device.writes[0][1:3], bytes((1, 7)))

    def test_clamp_serial_combines_two_registers(self):
        clamp = protocol.Clamp(None)
        values = {2: 0x5678, 3: 0x1234}
        with mock.patch.object(
            clamp,
            "_send_request",
            side_effect=lambda request_type, register_id, **kwargs: values[register_id],
        ):
            self.assertEqual(clamp.get_serial(), 0x12345678)

    def test_response_rejects_a_mismatched_transaction(self):
        connection = protocol.Connection(b"path")
        transaction = 123
        response = struct.pack(
            protocol.REQUEST_HEADER_FORMAT,
            0,
            0,
            transaction + 1,
            protocol.NetworkID.CLAMP,
            protocol.ResponseType.GET_REGISTER,
            5,
        ) + struct.pack("<H", 42)
        connection.message_send = lambda data: None
        connection.message_receive = lambda: response
        clamp = protocol.Clamp(connection)
        with mock.patch.object(protocol.random, "getrandbits", return_value=transaction):
            with self.assertRaisesRegex(protocol.ProtocolError, "Transaction"):
                clamp.get_register(5)


if __name__ == "__main__":
    unittest.main()
