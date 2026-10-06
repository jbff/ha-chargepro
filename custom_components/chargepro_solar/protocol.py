"""Framing and decoding for the Helios/HQST BLE serial protocol.

Modbus-RTU-style: requests ``addr func reg_hi reg_lo cnt_hi cnt_lo crc16_le``
; responses ``addr func len data... crc16_le`` — CRC-16/MODBUS (reflected,
poly 0xA001, init 0xFFFF), stored little-endian. Verified against live
frames from an HQST HP-2430N (2026-10-04) and ddrown/ble-solar captures.
"""
from __future__ import annotations

import struct
from typing import Final

from .const import GROUP_COUNT, GROUP_REG


def modbus_crc16(data: bytes) -> int:
    """Standard Modbus CRC-16 (reflected, poly 0xA001, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def build_request(group: int) -> bytes:
    """Build the read request for a protocol group."""
    reg = GROUP_REG[group]
    count = GROUP_COUNT[group]
    # Modbus is big-endian for register/count fields; CRC stored little-endian
    body = struct.pack(">BBHH", 0x01, 0x03, reg, count)
    return body + modbus_crc16(body).to_bytes(2, "little")


def validate_response(frame: bytes, group: int) -> bytearray:
    """Validate header/length/CRC of a response frame, return payload data."""
    if len(frame) < 5:
        raise ValueError(f"group{group}: frame too short ({len(frame)}b)")
    if frame[0] != 0x01 or frame[1] != 0x03:
        raise ValueError(f"group{group}: bad header {frame[0]:02x}{frame[1]:02x}")
    length = frame[2]
    if len(frame) != length + 5:
        raise ValueError(
            f"group{group}: length byte {length} != payload {len(frame) - 5}"
        )
    if modbus_crc16(frame[:-2]) != int.from_bytes(frame[-2:], "little"):
        raise ValueError(f"group{group}: CRC mismatch")
    return bytearray(frame[3 : 3 + length])


def s16(v: bytearray, o: int) -> int:
    return v[o] << 8 | v[o + 1]


# flag bits in group1 @ 27
FLAG_MAXV = 0x0001
FLAG_MPPT = 0x0002
FLAG_FLOAT = 0x0004
FLAG_DCLOAD = 0x8000


def decode_group1(frame: bytes) -> dict:
    """Live measurements. ddrown/ble-solar group1decode, offsets validated."""
    v = validate_response(frame, 1)
    flags = s16(v, 24)  # frame offset 27 - 3 header bytes
    return {
        "unknown_1_1": s16(v, 0),
        "battery_voltage": s16(v, 2) * 0.1,
        "battery_current": s16(v, 4) * 0.01,
        "solar_power": s16(v, 6),
        "temp_controller": v[8],
        "temp_battery": v[9],
        "dcload_voltage": s16(v, 10) * 0.1,
        "dcload_power": s16(v, 12) * 0.1,
        "dcload_current": s16(v, 14) * 0.1,
        "solar_voltage": s16(v, 16) * 0.1,
        "max_charge_power": s16(v, 18),
        "charge_today_wh": s16(v, 20),
        "dcload_today_wh": s16(v, 22),
        "mppt_mode": bool(flags & FLAG_MPPT),
        "float_mode": bool(flags & FLAG_FLOAT),
        "maxv_mode": bool(flags & FLAG_MAXV),
        "dcload_mode": bool(flags & FLAG_DCLOAD),
        "charge_total_wh": int.from_bytes(v[30:34], "big"),
        "dcload_total_wh": int.from_bytes(v[34:38], "big"),
        "errors": 0,
    }


def decode_group2(frame: bytes) -> dict:
    """Charger settings (subset useful to humans)."""
    v = validate_response(frame, 2)
    return {
        "system_voltage": s16(v, 2),
        "boost_voltage_1": s16(v, 6) * 0.1,
        "over_recovery_v_1": s16(v, 12) * 0.1,
        "over_discharge_v": s16(v, 18) * 0.1,
        "light_delay_s": s16(v, 24),
        "light_control_v": s16(v, 26),
    }


def decode_group3(frame: bytes) -> dict:
    """Lifetime/derived totals."""
    v = validate_response(frame, 3)
    return {
        "total_charge_wh": s16(v, 0),
        "max_charge_power_3": s16(v, 4),
        "highest_voltage": s16(v, 6) * 0.1,
        "lowest_voltage": s16(v, 8) * 0.1,
    }


def decode_group4(frame: bytes) -> dict:
    """Error register."""
    v = validate_response(frame, 4)
    return {"errors": s16(v, 0)}


DECODERS = {1: decode_group1, 2: decode_group2, 3: decode_group3, 4: decode_group4}


def decode_all(frames: dict[int, bytes]) -> dict:
    """Decode every group; collect all fields into one flat dict."""
    out: dict = {}
    for group, frame in frames.items():
        try:
            out.update(DECODERS[group](frame))
        except (ValueError, IndexError, TypeError) as ex:
            out[f"group{group}_error"] = str(ex)
    return out


def merge_notification_fragments(fragments: list[bytes]) -> list[bytes]:
    """Split an accumulated notification buffer into separate frames.

    Responses are back-to-back modbus frames with self-describing length
    bytes; split on the (addr, func, len) prefix structure.
    """
    out = []
    pos = 0
    buf = b"".join(fragments)
    while pos + 5 <= len(buf):
        length = buf[pos + 2]
        frame = buf[pos : pos + length + 5]
        if len(frame) < length + 5:
            break
        out.append(frame)
        pos += length + 5
    return out