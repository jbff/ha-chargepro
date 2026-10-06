"""Constants for the ChargePro Solar integration."""
from __future__ import annotations

DOMAIN = "chargepro_solar"

# Helios/HQST BLE serial channel (write + notify)
UUID_SERIAL = "0000ffe1-0000-1000-8000-00805f9b34fb"

# device advertisement name prefix
NAME_PREFIX = "PVChargePro"

# modbus-style register groups (address, start_reg, register_count)
GROUP_REG = {1: 0x0101, 2: 0x0201, 3: 0x0400, 4: 0x0121}
GROUP_COUNT = {1: 19, 2: 17, 3: 5, 4: 1}

DEFAULT_SCAN_INTERVAL = 60
DISCOVERY_TIMEOUT = 25  # seconds per find-by-address attempt; module
# advertises intermittently (~5min duty cycle), so failures are normal