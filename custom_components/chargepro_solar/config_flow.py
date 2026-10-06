"""Bluetooth config flow for the ChargePro Solar integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .const import DOMAIN, NAME_PREFIX


def _matches(info: BluetoothServiceInfoBleak) -> bool:
    return (info.name or "").startswith(NAME_PREFIX) or info.address.startswith(
        NAME_PREFIX
    )


class ChargeProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for a ChargePro/HQST controller."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a bluetooth advertisement match (from manifest)."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._info = discovery_info
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the discovered device."""
        assert self._info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=f"{self._info.title or self._info.name} ({self._info.address[-5:]})",
                data={
                    CONF_NAME: self._info.name,
                    CONF_ADDRESS: self._info.address,
                },
            )
        self.context["title_placeholders"] = {CONF_NAME: self._info.name}
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={CONF_NAME: self._info.name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual entry: pick from discovered devices or type the MAC."""
        errors: dict[str, str] = {}
        candidates = {
            si.address: si.address
            for si in bluetooth.async_discovered_service_info(self.hass)
            if _matches(si)
        }
        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            existing = self._async_current_ids()
            if address in existing:
                errors[CONF_ADDRESS] = "already_configured"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                name = candidates.get(address, user_input.get(CONF_NAME) or address)
                return self.async_create_entry(
                    title=f"ChargePro ({address[-5:]})", data={CONF_ADDRESS: address, CONF_NAME: name}
                )
        schema = vol.Schema(
            {
                vol.Optional(CONF_ADDRESS, description="suggested"): vol.In(
                    candidates, msg_invalid_choice="device not advertising yet"
                )
                if candidates
                else cv.string,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)