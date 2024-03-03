"""Cover platform for Teslemetry integration."""
from __future__ import annotations

from typing import Any

from tesla_fleet_api.const import WindowCommand, Trunk, Scope, TelemetryField

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TeslemetryCoverStates, TeslemetryTimestamp
from .entity import TeslemetryVehicleEntity
from .models import TeslemetryVehicleData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Teslemetry sensor platform from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        klass(vehicle, data.scopes)
        for (klass) in (
            TeslemetryWindowEntity,
            TeslemetryChargePortEntity,
            TeslemetryFrontTrunkEntity,
            TeslemetryRearTrunkEntity,
        )
        for vehicle in data.vehicles
    )


class TeslemetryWindowEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for current charge."""

    _attr_device_class = CoverDeviceClass.WINDOW
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, data: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(
            data, "windows", timestamp_key=TeslemetryTimestamp.VEHICLE_STATE
        )
        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        fd = self.get("vehicle_state_fd_window")
        fp = self.get("vehicle_state_fp_window")
        rd = self.get("vehicle_state_rd_window")
        rp = self.get("vehicle_state_rp_window")

        if fd or fp or rd or rp == TeslemetryCoverStates.OPEN:
            self._attr_is_closed = False
        elif fd and fp and rd and rp == TeslemetryCoverStates.CLOSED:
            self._attr_is_closed = True
        else:
            self._attr_is_closed = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Vent windows."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.window_control(command=WindowCommand.VENT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.window_control(command=WindowCommand.CLOSE))
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryChargePortEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(
            vehicle,
            "charge_state_charge_port_door_open",
            timestamp_key=TeslemetryTimestamp.CHARGE_STATE,
            streaming_key=TelemetryField.CHARGE_PORT,
        )
        self.scoped = any(
            scope in scopes
            for scope in [Scope.VEHICLE_CMDS, Scope.VEHICLE_CHARGING_CMDS]
        )
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = self._value

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open windows."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.charge_port_door_open())
        self._attr_is_closed = False
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close windows."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.charge_port_door_close())
        self._attr_is_closed = True
        self.async_write_ha_state()


class TeslemetryFrontTrunkEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_ft")

        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        self._attr_is_closed = self.exactly(TeslemetryCoverStates.CLOSED)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open front trunk."""
        self.raise_for_scope()
        await self.wake_up_if_asleep()
        await self.handle_command(self.api.actuate_trunk(Trunk.FRONT))
        self._attr_is_closed = False
        self.async_write_ha_state()

    # In the future this could be extended to add aftermarket close support through a option flow


class TeslemetryRearTrunkEntity(TeslemetryVehicleEntity, CoverEntity):
    """Cover entity for the charge port."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, vehicle: TeslemetryVehicleData, scopes: list[Scope]) -> None:
        """Initialize the sensor."""
        super().__init__(vehicle, "vehicle_state_rt")

        self.scoped = Scope.VEHICLE_CMDS in scopes
        if not self.scoped:
            self._attr_supported_features = CoverEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        value = self._value
        if value == TeslemetryCoverStates.CLOSED:
            self._attr_is_closed = True
        elif value == TeslemetryCoverStates.OPEN:
            self._attr_is_closed = False
        else:
            self._attr_is_closed = None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open rear trunk."""
        if self.is_closed is not False:
            self.raise_for_scope()
            await self.wake_up_if_asleep()
            await self.handle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = False
            self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close rear trunk."""
        if self.is_closed is not True:
            self.raise_for_scope()
            await self.wake_up_if_asleep()
            await self.handle_command(self.api.actuate_trunk(Trunk.REAR))
            self._attr_is_closed = True
            self.async_write_ha_state()
