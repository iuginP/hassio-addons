"""Onzo HID protocol support.

Adapted for Python 3 and multi-device path selection from PyOnzo.
"""

from __future__ import annotations

import random
import struct
from enum import IntEnum
from typing import Callable

REQUEST_HEADER_FORMAT = "<HQHHBB"


class ProtocolError(RuntimeError):
    pass


class NetworkID(IntEnum):
    CLAMP = 1
    DISPLAY = 2


class RequestType(IntEnum):
    GET_REGISTER = 1
    SET_REGISTER = 2
    GET_BULK_DATA = 3
    GET_NETWORK_LIST = 4
    CMD_RESET = 5
    WRITE_BULK_DATA = 6
    LDM_COMMAND = 160


class ResponseType(IntEnum):
    GET_REGISTER = 1
    SET_REGISTER = 2
    GET_BULK_DATA = 3
    GET_NETWORK_LIST = 4
    LDM_COMMAND = 160
    ERROR = 240
    END_OF_TRANSFER = 241


class Connection:
    def __init__(self, path, device_factory: Callable | None = None):
        self.path = path
        self.device_factory = device_factory
        self.dev = None

    def connect(self) -> None:
        factory = self.device_factory
        if factory is None:
            import hid

            factory = hid.device
        self.dev = factory()
        self.dev.open_path(self.path)

    def disconnect(self) -> None:
        if self.dev is not None:
            self.dev.close()
            self.dev = None

    def message_send(self, data: bytes) -> None:
        if self.dev is None:
            raise ProtocolError("HID device is not connected")
        while data:
            chunk, data = data[:62], data[62:]
            final = int(not data)
            frame = bytes((final, len(chunk))) + chunk.ljust(62, b"\xff")
            report = b"\x00" + frame
            written = self.dev.write(report)
            if written != len(report):
                raise ProtocolError(
                    f"Incomplete HID write ({written}/{len(report)} bytes)"
                )

    def message_receive(self, timeout: int = 5000) -> bytes:
        if self.dev is None:
            raise ProtocolError("HID device is not connected")
        payload = bytearray()
        while True:
            frame = bytes(self.dev.read(64, timeout))
            if len(frame) != 64:
                raise TimeoutError("Timed out waiting for an Onzo HID response")
            final, frame_size = struct.unpack("<BB", frame[:2])
            if frame_size > 62:
                raise ProtocolError("Invalid HID frame size")
            payload.extend(frame[2 : 2 + frame_size])
            if final:
                return bytes(payload)


class Device:
    network_id: NetworkID
    registers: dict[str, list[int]]

    def __init__(self, connection: Connection | None):
        self.connection = connection

    def _send_request(
        self,
        request_type: RequestType,
        register_id: int,
        request_payload: bytes = b"",
        response_parser: Callable[[bytes], object] = lambda payload: None,
    ):
        if self.connection is None:
            raise ProtocolError("Device has no connection")
        transaction_id = random.getrandbits(16)
        header = struct.pack(
            REQUEST_HEADER_FORMAT,
            0,
            0,
            transaction_id,
            self.network_id,
            request_type,
            register_id,
        )
        self.connection.message_send(header + request_payload)
        response = self.connection.message_receive()
        if len(response) < 16:
            raise ProtocolError("Onzo response header is incomplete")
        fields = struct.unpack(REQUEST_HEADER_FORMAT, response[:16])
        response_transaction = fields[2]
        response_type = ResponseType(fields[4])
        response_register = fields[5]
        if response_type == ResponseType.ERROR:
            raise ProtocolError(f"Onzo rejected register {register_id}")
        if response_transaction != transaction_id:
            raise ProtocolError("Transaction IDs do not match")
        if int(response_type) != int(request_type):
            raise ProtocolError("Response type does not match request type")
        if response_register != register_id:
            raise ProtocolError("Response register does not match request")
        return response_parser(response[16:])

    def get_register(self, register_id: int | str) -> int:
        if isinstance(register_id, int):
            return self._send_request(
                RequestType.GET_REGISTER,
                register_id,
                response_parser=lambda payload: struct.unpack("<H", payload[:2])[0],
            )
        addresses = self.registers[register_id]
        value = 0
        for address in reversed(addresses):
            value = (value << 16) + self.get_register(address)
        return value

    def __getattr__(self, name: str):
        if name.startswith("get_") and name[4:] in self.registers:
            return lambda: self.get_register(name[4:])
        raise AttributeError(name)


class Clamp(Device):
    network_id = NetworkID.CLAMP
    registers = {
        "type": [0],
        "version": [1],
        "serial": [2, 3],
        "status": [4],
        "power": [5],
        "readinginterval": [6],
        "sendinginterval": [7],
        "timestamp": [8, 9],
        "voltage": [10],
        "temperature": [13],
        "powervars": [14],
        "RSSI": [15],
        "EAR": [16, 17],
        "batteryvolts": [18],
        "txpower": [19],
        "instwatt": [23],
        "instvar": [24],
    }

    def get_cumulative_kwh(self) -> float:
        return self.get_EAR() / 10000
