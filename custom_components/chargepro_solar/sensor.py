"""Sensor entities for the ChargePro Solar integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory, EntityDescription  # noqa: F401
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import device_info
from .coordinator import ChargeProCoordinator


@dataclass(frozen=True, kw_only=True)
class ChargeProSensorDescription(SensorEntityDescription):
    """Entity description with an entity-category default per key."""

    category: str = ""


SENSOR_TYPES: tuple[ChargeProSensorDescription, ...] = (
    ChargeProSensorDescription(
        key="battery_voltage", name="Battery voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    ChargeProSensorDescription(
        key="battery_current", name="Battery current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    ChargeProSensorDescription(
        key="solar_voltage", name="Solar panel voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChargeProSensorDescription(
        key="solar_power", name="Solar panel power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ChargeProSensorDescription(
        key="max_charge_power", name="Max charge power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        category="diagnostic",
    ),
    ChargeProSensorDescription(
        key="charge_today_wh", name="Energy charged today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ChargeProSensorDescription(
        key="total_charge_wh", name="Energy charged total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ChargeProSensorDescription(
        key="charge_total_wh", name="Energy charged total (group1)",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        category="diagnostic",
        entity_registry_enabled_default=False,
    ),
    ChargeProSensorDescription(
        key="dcload_voltage", name="DC load voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChargeProSensorDescription(
        key="dcload_power", name="DC load power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChargeProSensorDescription(
        key="dcload_current", name="DC load current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ChargeProSensorDescription(
        key="dcload_today_wh", name="DC load energy today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ChargeProSensorDescription(
        key="temp_controller", name="Controller temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ChargeProSensorDescription(
        key="temp_battery", name="Battery temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ChargeProSensorDescription(
        key="boost_voltage_1", name="Boost voltage setting",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        category="diagnostic",
        entity_registry_enabled_default=False,
    ),
    ChargeProSensorDescription(
        key="over_discharge_v", name="Over-discharge voltage setting",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        category="diagnostic",
        entity_registry_enabled_default=False,
    ),
    ChargeProSensorDescription(
        key="system_voltage", name="System voltage",
        category="diagnostic",
        entity_registry_enabled_default=False,
    ),
    ChargeProSensorDescription(
        key="errors", name="Error register",
        category="diagnostic",
        entity_registry_enabled_default=False,
    ),
)


class ChargeProSensor(CoordinatorEntity[ChargeProCoordinator], SensorEntity):
    """A ChargePro sensor."""

    def __init__(
        self,
        coordinator: ChargeProCoordinator,
        description: ChargeProSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator._address}_{description.key}"
        )
        if description.category == "diagnostic":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = device_info(
            coordinator, coordinator.config_entry
        )

    @property
    def native_value(self):
        """Return the sensor value from coordinator data."""
        return self.coordinator.data.get(self.entity_description.key)


async def async_setup_entry(
    hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ChargePro sensors."""
    coordinator: ChargeProCoordinator = entry.runtime_data
    async_add_entities(
        ChargeProSensor(coordinator, desc) for desc in SENSOR_TYPES
    )