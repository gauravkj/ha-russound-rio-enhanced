"""Support for Russound RIO button entities."""

from dataclasses import dataclass

from aiorussound.rio import Controller

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RussoundConfigEntry
from .entity import RussoundBaseEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RussoundControllerButtonEntityDescription(ButtonEntityDescription):
    """Describes Russound RIO controller button entity."""


CONTROL_ENTITIES: tuple[RussoundControllerButtonEntityDescription, ...] = (
    RussoundControllerButtonEntityDescription(
        key="all_zones_off",
        name="All Zones Off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound RIO button entities based on a config entry."""
    client = entry.runtime_data

    entities: list[ButtonEntity] = [
        RussoundAllZonesOffButton(controller, description)
        for controller in client.controllers.values()
        for description in CONTROL_ENTITIES
    ]

    async_add_entities(entities)


class RussoundControllerEntity(RussoundBaseEntity):
    """Base class for controller level Russound entities."""

    def __init__(self, controller: Controller) -> None:
        """Initialize controller level entity."""
        super().__init__(controller, zone_id=None)
        self._attr_has_entity_name = True


class RussoundAllZonesOffButton(RussoundControllerEntity, ButtonEntity):
    """Controller level All Zones Off button."""

    entity_description: RussoundControllerButtonEntityDescription

    def __init__(
        self,
        controller: Controller,
        description: RussoundControllerButtonEntityDescription,
    ) -> None:
        """Initialize All Zones Off button."""
        super().__init__(controller)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._controller.device_str}-{description.key}"
        )

    @command
    async def async_press(self) -> None:
        """Turn off all zones on this controller."""
        for zone in self._controller.zones.values():
            if zone.status:
                await zone.zone_off()
