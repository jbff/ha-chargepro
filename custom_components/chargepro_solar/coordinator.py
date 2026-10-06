"""Data coordinator for the ChargePro Solar integration.

Design note: the Helios BLE module advertises only intermittently (~5 min
duty-cycle bursts) but holds a connected session fine. So the coordinator
HOLDS the BLE connection across polls instead of reconnecting per poll:
connect once (patiently), poll every scan interval, and re-establish
patiently only after a drop.
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_last_service_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DISCOVERY_TIMEOUT, UUID_SERIAL
from .protocol import build_request, decode_all, merge_notification_fragments

_LOGGER = logging.getLogger(__name__)
CONNECT_PATIENCE = 45.0  # seconds of connect attempts inside one poll
FRAGMENT_SETTLE = 0.4  # seconds to let MTU fragments land
QUERY_TIMEOUT = 4.0


class ChargeProCoordinator(DataUpdateCoordinator[dict]):
    """Poll the HQST/Helios MPPT over BLE, holding the connection."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self._address = address
        self._name = name
        self.entry = entry
        self.client: BleakClient | None = None
        self._last_seen = 0.0
        super().__init__(
            hass,
            _LOGGER,
            name=f"chargepro_solar {address}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_get_connected_client(self) -> BleakClient:
        """Return a live client, connecting if needed."""
        if self.client is not None and self.client.is_connected:
            return self.client
        self.client = None

        device = None
        si = async_last_service_info(self.hass, self._address, connectable=True)
        if si and si.time > time.time() - 120:
            device = si.device
        if device is None:
            si = async_last_service_info(
                self.hass, self._address, connectable=True
            )
            if si:
                device = si.device  # stale cache: worth one attempt anyway
        if device is None:
            from bleak import BleakScanner

            device = await BleakScanner.find_device_by_address(
                self._address, timeout=DISCOVERY_TIMEOUT
            )
        if device is None:
            raise UpdateFailed(
                "Device not advertising since "
                f"{0 if not self._last_seen else int(time.time() - self._last_seen)}s ago "
                "(module duty-cycles ~5 min; retrying)"
            )
        client = await establish_connection(
            BleakClient,
            device,
            self._address,
            timeout=CONNECT_PATIENCE / 5,
            use_services_cache=True,
        )
        self.client = client
        self._last_seen = time.time()
        return client

    async def _async_query_all(self, client: BleakClient) -> dict:
        """Burst all four protocol groups over the held connection."""
        buf = bytearray()
        ev = asyncio.Event()
        results: dict[int, bytes] = {}

        def _cb(_, data: bytes) -> None:
            buf.extend(data)
            ev.set()

        await client.start_notify(UUID_SERIAL, _cb)
        try:
            # the module boots its serial stack after establish (~10-15s of
            # ignored writes observed); settle, then retry each group
            await asyncio.sleep(2)
            for group in (1, 2, 3, 4):
                buf.clear()
                ev.clear()
                resp = b""
                for attempt in range(3):
                    await client.write_gatt_char(
                        UUID_SERIAL, build_request(group), response=False
                    )
                    try:
                        await asyncio.wait_for(ev.wait(), timeout=QUERY_TIMEOUT)
                        await asyncio.sleep(FRAGMENT_SETTLE)  # trailing MTU fragments
                        resp = bytes(buf)
                        break
                    except asyncio.TimeoutError:
                        ev.clear()
                        await asyncio.sleep(0.5)
                results[group] = resp
        finally:
            try:
                await client.stop_notify(UUID_SERIAL)
            except Exception:  # noqa: BLE001
                pass
        frames: dict[int, bytes] = {}
        for group, group_buf in results.items():
            if not group_buf:
                _LOGGER.debug("group %d: no response", group)
                continue
            parts = merge_notification_fragments([bytes(group_buf)])
            if parts:
                frames[group] = parts[-1]
        if not frames:
            raise UpdateFailed("No decodable frames in response")
        _LOGGER.debug("Decoded %d group(s): %s", len(frames), sorted(frames))
        return decode_all(frames)

    async def _async_update_data(self) -> dict:
        """Query the charger, reusing (or re-establishing) the connection."""
        try:
            client = await self._async_get_connected_client()
            return await self._async_query_all(client)
        except UpdateFailed:
            raise
        except Exception as ex:  # noqa: BLE001
            # connection died mid-poll: drop it so the next poll reconnects
            self.client = None
            raise UpdateFailed(f"BLE communication error: {ex}") from ex

    async def async_shutdown(self) -> None:
        """Disconnect the held client on teardown."""
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None
        await super().async_shutdown()

    async def async_unload(self) -> None:
        """Disconnect on entry unload."""
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None