"""Switch platform for Russound RIO Enhanced."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import RussoundBaseEntity, command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Russound switch entities from a config entry."""
    client = entry.runtime_data
    entities: list[SwitchEntity] = []

    for controller in client.controllers.values():
        for zone_id in controller.zones:
            zone = controller.zones[zone_id]

            if hasattr(zone, "low_volume_boost") and hasattr(zone, "set_low_volume_boost"):
                entities.append(RussoundLowVolumeBoostSwitch(controller, zone_id))

            if hasattr(zone, "do_not_disturb") and hasattr(zone, "set_do_not_disturb"):
                entities.append(RussoundDoNotDisturbSwitch(controller, zone_id))

    async_add_entities(entities)


class RussoundZoneSwitchEntity(RussoundBaseEntity, SwitchEntity):
    """Base Russound zone switch."""

    _switch_key: str
    _attr_icon: str

    def __init__(self, controller, zone_id: int) -> None:
        """Initialize the switch."""
        super().__init__(controller, zone_id)
        self._attr_unique_id = f"{self._device_identifier}-{zone_id}-{self._switch_key}"

    @property
    def available(self) -> bool:
        """Return whether entity is available."""
        return self._client.is_connected()


class RussoundLowVolumeBoostSwitch(RussoundZoneSwitchEntity):
    """Russound Low Volume Boost switch."""

    _attr_name = "Low Volume Boost"
    _attr_icon = "mdi:volume-plus"
    _switch_key = "low_volume_boost"

    @property
    def is_on(self) -> bool:
        """Return true if low volume boost is enabled."""
        return bool(getattr(self._zone, "low_volume_boost", False))

    @command
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on low volume boost."""
        if hasattr(self._zone, "set_low_volume_boost"):
            await self._zone.set_low_volume_boost(True)

    @command
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off low volume boost."""
        if hasattr(self._zone, "set_low_volume_boost"):
            await self._zone.set_low_volume_boost(False)


class RussoundDoNotDisturbSwitch(RussoundZoneSwitchEntity):
    """Russound Do Not Disturb switch."""

    _attr_name = "Do Not Disturb"
    _attr_icon = "mdi:minus-circle-off"
    _switch_key = "do_not_disturb"

    @property
    def is_on(self) -> bool:
        """Return true if do not disturb is enabled."""
        return bool(getattr(self._zone, "do_not_disturb", False))

    @command
    async def async_turn_on(self, **kwargs) -> None:
        """Turn on do not disturb."""
        if hasattr(self._zone, "set_do_not_disturb"):
            await self._zone.set_do_not_disturb(True)

    @command
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off do not disturb."""
        if hasattr(self._zone, "set_do_not_disturb"):
            await self._zone.set_do_not_disturb(False)
