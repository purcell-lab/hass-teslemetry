"""Select platform for Teslemetry integration."""
from __future__ import annotations

from tesla_fleet_api.const import Scopes
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TeslemetrySeatHeaterOptions
from .entity import (
    TeslemetryVehicleEntity,
    TeslemetryEnergyInfoEntity,
)
from .models import TeslemetryEnergyData, TeslemetryVehicleData

SEAT_HEATERS = {
    "climate_state_seat_heater_left": "front_left",
    "climate_state_seat_heater_right": "front_right",
    "climate_state_seat_heater_rear_left": "rear_left",
    "climate_state_seat_heater_rear_center": "rear_center",
    "climate_state_seat_heater_rear_right": "rear_right",
    "climate_state_seat_heater_third_row_left": "third_row_left",
    "climate_state_seat_heater_third_row_right": "third_row_right",
}


@dataclass(frozen=True, kw_only=True)
class TeslemetrySelectEntityDescription(SelectEntityDescription):
    """Describes a Teslemetry Select entity."""

    key: str
    func: Callable


ENERGY_INFO_DESCRIPTIONS: tuple(TeslemetrySelectEntityDescription, ...) = (
    TeslemetrySelectEntityDescription(
        key="default_real_mode",
        func=lambda api, value: api.operation(value),
        options=["autonomous", "self_consumption", "backup"],
    ),
    TeslemetrySelectEntityDescription(
        key="component_net_meter_mode",
        func=lambda api, value: api.grid_import_export(
            customer_preferred_export_rule=value
        ),
        options=["battery_ok", "pv_only", "never"],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Teslemetry select platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for vehicle in data.vehicles:
        scoped = Scopes.VEHICLE_CMDS in data.scopes
        entities.append(
            TeslemetrySeatHeaterSelectEntity(
                vehicle, "climate_state_seat_heater_left", scoped
            )
        )
        entities.append(
            TeslemetrySeatHeaterSelectEntity(
                vehicle, "climate_state_seat_heater_right", scoped
            )
        )
        if vehicle.coordinator.data.get("vehicle_config_rear_seat_heaters"):
            entities.append(
                TeslemetrySeatHeaterSelectEntity(
                    vehicle, "climate_state_seat_heater_rear_left", scoped
                )
            )
            entities.append(
                TeslemetrySeatHeaterSelectEntity(
                    vehicle, "climate_state_seat_heater_rear_center", scoped
                )
            )
            entities.append(
                TeslemetrySeatHeaterSelectEntity(
                    vehicle, "climate_state_seat_heater_rear_right", scoped
                )
            )
            if vehicle.coordinator.data.get("vehicle_config_third_row_seats") != "None":
                entities.append(
                    TeslemetrySeatHeaterSelectEntity(
                        vehicle, "climate_state_seat_heater_third_row_left", scoped
                    )
                )
                entities.append(
                    TeslemetrySeatHeaterSelectEntity(
                        vehicle, "climate_state_seat_heater_third_row_right", scoped
                    )
                )

    for energysite in data.energysites:
        for description in ENERGY_INFO_DESCRIPTIONS:
            if description.key in energysite.info_coordinator.data:
                entities.append(
                    TeslemetryEnergySiteSelectEntity(
                        energysite, description, Scopes.ENERGY_CMDS in data.scopes
                    )
                )

    async_add_entities(entities)


class TeslemetrySeatHeaterSelectEntity(TeslemetryVehicleEntity, SelectEntity):
    """Select entity for vehicle seat heater."""

    _attr_options = [
        TeslemetrySeatHeaterOptions.OFF,
        TeslemetrySeatHeaterOptions.LOW,
        TeslemetrySeatHeaterOptions.MEDIUM,
        TeslemetrySeatHeaterOptions.HIGH,
    ]

    def __init__(self, data: TeslemetryVehicleData, key: str, scoped: bool) -> None:
        """Initialize the vehicle seat select entity."""
        super().__init__(data, key)
        self.scoped = scoped

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        value = self.get()
        if value is None:
            return None
        return self._attr_options[value]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        level = self._attr_options.index(option)
        await self.api.remote_seat_heater_request(SEAT_HEATERS[self.key], level)
        self.set((self.key, level))


class TeslemetryEnergySiteSelectEntity(TeslemetryEnergyInfoEntity, SelectEntity):
    """Select entity for energy sites."""

    def __init__(
        self,
        data: TeslemetryEnergyData,
        description: TeslemetrySelectEntityDescription,
        scoped: bool,
    ) -> None:
        """Initialize the operation mode select entity."""
        super().__init__(data, description.key)
        self.scoped = scoped
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self.get()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self.raise_for_scope()
        await self.entity_description.func(self.api, option)
        self.set((self.key, option))
