from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HuckleberryDataUpdateCoordinator
from .form_state import (
    FIELD_ACTIVITY_DATETIME,
    FIELD_BOTTLE_DATETIME,
    FIELD_DIAPER_DATETIME,
    FIELD_SLEEP_END,
    FIELD_SLEEP_START,
)


@dataclass(frozen=True, slots=True)
class HuckleberryDateTimeDescription:
    key: str
    name: str
    icon: str
    enabled_default: bool = True


DATETIME_FIELDS: tuple[HuckleberryDateTimeDescription, ...] = (
    HuckleberryDateTimeDescription(
        key=FIELD_ACTIVITY_DATETIME,
        name="Activity Date/Time",
        icon="mdi:calendar-clock",
    ),
    HuckleberryDateTimeDescription(
        key=FIELD_BOTTLE_DATETIME,
        name="Bottle Date/Time",
        icon="mdi:calendar-clock",
    ),
    HuckleberryDateTimeDescription(
        key=FIELD_DIAPER_DATETIME,
        name="Diaper Date/Time",
        icon="mdi:calendar-clock",
    ),
    HuckleberryDateTimeDescription(
        key=FIELD_SLEEP_START,
        name="Sleep Start",
        icon="mdi:sleep",
    ),
    HuckleberryDateTimeDescription(
        key=FIELD_SLEEP_END,
        name="Sleep End",
        icon="mdi:sleep-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HuckleberryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[HuckleberryFormDateTimeEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in DATETIME_FIELDS:
            entities.append(
                HuckleberryFormDateTimeEntity(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberryFormDateTimeEntity(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    DateTimeEntity,
):
    """Native DateTime form value for Huckleberry actions."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberryDateTimeDescription,
    ) -> None:
        super().__init__(coordinator)
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_datetime"
        )
        self._attr_icon = description.icon
        self.coordinator.get_form_values(child_uid)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._child_uid)},
            name=f"Huckleberry {self._child_name}",
            manufacturer="Huckleberry",
            model="Child Profile",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        value = self.coordinator.get_form_value(
            self._child_uid,
            self.entity_description.key,
        )
        if isinstance(value, datetime):
            return value
        return None

    async def async_set_value(self, value: datetime) -> None:
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            value,
        )
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.enabled_default
