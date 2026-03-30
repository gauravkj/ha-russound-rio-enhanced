"""Support for Russound number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiorussound.rio import Controller, ZoneControlSurface

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import RussoundConfigEntry
from .entity import RussoundBaseEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RussoundZoneNumberEntityDescription(NumberEntityDescription):
    """Describes Russound zone number entities."""

    value_fn: Callable[[ZoneControlSurface], float]
    set_value_fn: Callable[[ZoneControlSurface, float], Awaitable[None]]


CONTROL_ENTITIES: tuple[RussoundZoneNumberEntityDescription, ...] = (
    RussoundZoneNumberEntityDescription(
        key="balance",
        name="Balance",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.balance,
        set_value_fn=lambda zone, value: zone.set_balance(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="bass",
        name="Bass",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.bass,
        set_value_fn=lambda zone, value: zone.set_bass(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="treble",
        name="Treble",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.treble,
        set_value_fn=lambda zone, value: zone.set_treble(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="turn_on_volume",
        name="Startup Volume",
        native_min_value=0,
        native_max_value=100,
        native_step=2,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.turn_on_volume * 2,
        set_value_fn=lambda zone, value: zone.set_turn_on_volume(int(value / 2)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound number entities based on a config entry."""
    client = entry.runtime_data

    entities: list[NumberEntity] = []

    for controller in client.controllers.values():
        entities.append(RussoundControllerStartupVolumeNumber(controller))

        for zone_id in controller.zones:
            for description in CONTROL_ENTITIES:
                entities.append(RussoundZoneNumberEntity(controller, zone_id, description))

    async_add_entities(entities)


class RussoundControllerEntity(RussoundBaseEntity):
    """Base class for controller level Russound entities."""

    def __init__(self, controller: Controller) -> None:
        """Initialize controller level entity."""
        super().__init__(controller, zone_id=None)
        self._attr_has_entity_name = True


class RussoundControllerStartupVolumeNumber(
    RussoundControllerEntity, NumberEntity, RestoreEntity
):
    """Controller level startup volume applied to all zones."""

    _attr_name = "Startup Volume for All Zones"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 2

    def __init__(self, controller: Controller) -> None:
        """Initialize controller startup volume number."""
        super().__init__(controller)
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._controller.device_str}-turn_on_volume_all"
        )
        self._master_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last controller level value if available."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in ("unknown", "unavailable"):
            try:
                self._master_value = float(last_state.state)
                return
            except ValueError:
                pass

        first_zone = next(iter(self._controller.zones.values()))
        self._master_value = float(first_zone.turn_on_volume * 2)

    @property
    def native_value(self) -> float:
        """Return the stored controller startup volume."""
        if self._master_value is None:
            first_zone = next(iter(self._controller.zones.values()))
            return float(first_zone.turn_on_volume * 2)
        return self._master_value

    @command
    async def async_set_native_value(self, value: float) -> None:
        """Set startup volume on all zones and store controller master value."""
        self._master_value = float(value)
        zone_value = int(value / 2)

        for zone in self._controller.zones.values():
            await zone.set_turn_on_volume(zone_value)

        self.async_write_ha_state()


class RussoundZoneNumberEntity(RussoundBaseEntity, NumberEntity):
    """Defines a Russound zone number entity."""

    entity_description: RussoundZoneNumberEntityDescription

    def __init__(
        self,
        controller: Controller,
        zone_id: int,
        description: RussoundZoneNumberEntityDescription,
    ) -> None:
        """Initialize a Russound zone number entity."""
        super().__init__(controller, zone_id)
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = description.name
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._zone.device_str}-{description.key}"
        )

    @property
    def native_value(self) -> float:
        """Return the native value of the entity."""
        return float(self.entity_description.value_fn(self._zone))

    @command
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.entity_description.set_value_fn(self._zone, value)
