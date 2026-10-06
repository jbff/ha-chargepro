"""The ChargePro Solar integration (HQST/Helios MPPT over BLE)."""
from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.config_entries import ConfigEntry

from .coordinator import ChargeProCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]
DOMAIN = "chargepro_solar"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChargePro Solar from a config entry."""
    address = entry.data[CONF_ADDRESS]
    coordinator = ChargeProCoordinator(
        hass, address, entry.data.get(CONF_NAME, address), entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(coordinator.async_unload)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry on options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def device_info(coordinator: ChargeProCoordinator, entry: ConfigEntry) -> DeviceInfo:
    """Device registry entry for the charger."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME) or f"ChargePro {coordinator._address[-5:]}",
        manufacturer="HQST / Helios New Energy",
        model="HP-2430N",
    )