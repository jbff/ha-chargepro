# ChargePro 2.0 / Helios BLE protocol notes

Wire format spoken through the Helios Bluetooth module's serial GATT
service (service `0000ffe0-0000-1000-8000-00805f9b34fb`, characteristic
`0000ffe1-0000-1000-8000-00805f9b34fb`: write + notify). Reverse-engineered
from [ddrown/ble-solar](https://github.com/ddrown/ble-solar) and verified
live on an HQST HP-2430N.

## Transport

- Requests are **written** to `ffe1` as write-without-response.
- Responses arrive as **notifications** on `ffe1`; a response can be split
  across 1–3 notifications (MTU 20). Accumulate and split on the
  self-describing frame length (below).
- The characteristic `0000ffe2-...` is also present (write-only; unused
  here). The module exposes battery service `0x180f` and a Tencent BLE
  platform service `0xfee7`.
- The module advertises intermittently (observed ~5-minute duty cycle when
  idle-woken; bursts after phone-app activity) but holds a live connection
  fine — hold the connection rather than reconnecting per poll.

## Framing (Modbus-RTU-style)

```
request:   01 03 <reg_hi> <reg_lo> <cnt_hi> <cnt_lo> <crc_lo> <crc_hi>
response:  01 03 <len>     <data...>               <crc_lo> <crc_hi>
```

- Register/count fields are **big-endian**.
- `len` = number of **data** bytes in the response (2 × register count).
- CRC = standard **Modbus CRC-16**, stored **little-endian**:
  - init `0xFFFF`, poly `0xA001` (reflected `0x8005`), no final XOR
  - covers everything except its own two bytes.

### Known register groups (read-only)

| Group | reg (0x) | count | contents |
|---|---|---|---|
| 1 | 0101 | 19 | live measurements (below) |
| 2 | 0201 | 17 | settings: system voltage, boost/equalize/over-discharge voltages, light-control settings |
| 3 | 0400 | 5 | totals/voltage extremes: total charge (Wh), max charge power, highest/lowest battery voltage |
| 4 | 0121 | 1 | error register (uint16, 0 = no errors) |

### Group 1 payload (data bytes, offsets relative to after the `len` byte)

| offset(s) | meaning | scale |
|---|---|---|
| 0–1 | unknown (100 = ?) | — |
| 2–3 | battery voltage | 0.1 V |
| 4–5 | battery current (charge positive) | 0.01 A |
| 6–7 | solar power | W |
| 8 | controller temperature | °C |
| 9 | battery temperature | °C |
| 10–11 | DC load voltage | 0.1 V |
| 12–13 | DC load power | 0.1 W |
| 14–15 | DC load current | 0.1 A |
| 16–17 | solar panel voltage | 0.1 V |
| 18–19 | max charge power | W |
| 20–21 | energy charged today | Wh |
| 22–23 | DC load energy today | Wh |
| 24–25 | status flags (bitfield, uint16 BE) | — |
| 26–27 | unknown | — |
| 28–29 | unknown | — |
| 30–33 | charge total | Wh (uint32 BE) |
| 34–37 | DC load total | Wh (uint32 BE) |

Flag bits (offset 24–25): `0x0001` max-voltage mode, `0x0002` MPPT/charge
mode, `0x0004` float mode, `0x8000` DC-load output on. Bit meanings around
0x0001/0x0004 are the least verified (see ddrown's notes for his flag
history).

### Group 2 payload

`0–1` unknown, `2–3` system voltage (nominal, V), `4–5` unknown,
`6–7/8–9/10–11` boost/equalize voltages ×3 (0.1 V), `12–13/14–15`
over-recovery ×2 (0.1 V), `16–17` unknown, `18–19` over-discharge
(0.1 V), `20–21/22–23` unknown, `24–25` light delay (s), `26–27` light
control voltage threshold.

## Other observations

- The device appears to ignore malformed requests (wrong endianness →
  silence) except short/likely-shaped ones — errors are silent, the CRC is
  not echoed, so validate responses client-side.
- One BLE connection at a time; a connected module can be re-connected
  without advertising (connect-by-address works against a cached BlueZ
  record).
- Requests verified byte-for-byte reproducible with the standard Modbus
  CRC; `struct.pack(">BBHH", 1, 3, reg, count) + crc16_le` builds every
  group request.