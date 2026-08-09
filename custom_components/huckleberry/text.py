from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HuckleberryDataUpdateCoordinator
from .form_state import FIELD_ACTIVITY_NOTES, FIELD_DIAPER_NOTES


@dataclass(frozen=True, slots=True)
class HuckleberryTextDescription:
    key: str
    name: str
    icon: str
    max_length: int = 512
    enabled_default: bool = True


TEXT_FIELDS: tuple[HuckleberryTextDescription, ...] = (
    HuckleberryTextDescription(
        key=FIELD_ACTIVITY_NOTES,
        name="Activity Notes",
        icon="mdi:text-box-outline",
        max_length=1024,
    ),
    HuckleberryTextDescription(
        key=FIELD_DIAPER_NOTES,
        name="Diaper Notes",
        icon="mdi:text-box-outline",
        max_length=1024,
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

    entities: list[HuckleberryFormTextEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in TEXT_FIELDS:
            entities.append(
                HuckleberryFormTextEntity(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberryFormTextEntity(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    TextEntity,
):
    """Native Text form value for Huckleberry actions."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberryTextDescription,
    ) -> None:
        super().__init__(coordinator)
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_text"
        )
        self._attr_icon = description.icon
        self._attr_native_max = description.max_length
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
    def native_value(self) -> str:
        value = self.coordinator.get_form_value(
            self._child_uid,
            self.entity_description.key,
        )
        if isinstance(value, str):
            return value
        return ""

    async def async_set_value(self, value: str) -> None:
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            value,
        )
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.enabled_default
