from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HuckleberryDataUpdateCoordinator
from .form_state import (
    FIELD_ACTIVITY_FORM,
    FIELD_BOTTLE_FORM,
    FIELD_DIAPER_FORM,
    FIELD_DIAPER_RASH,
)


@dataclass(frozen=True, slots=True)
class HuckleberrySwitchDescription:
    key: str
    name: str
    icon: str
    enabled_default: bool = True


SWITCH_FIELDS: tuple[HuckleberrySwitchDescription, ...] = (
    HuckleberrySwitchDescription(
        key=FIELD_ACTIVITY_FORM,
        name="Activity Form Toggle",
        icon="mdi:form-select",
    ),
    HuckleberrySwitchDescription(
        key=FIELD_BOTTLE_FORM,
        name="Bottle Form Toggle",
        icon="mdi:form-select",
    ),
    HuckleberrySwitchDescription(
        key=FIELD_DIAPER_FORM,
        name="Diaper Form Toggle",
        icon="mdi:form-select",
    ),
    HuckleberrySwitchDescription(
        key=FIELD_DIAPER_RASH,
        name="Diaper Rash",
        icon="mdi:medical-bag",
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

    entities: list[HuckleberryFormSwitchEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in SWITCH_FIELDS:
            entities.append(
                HuckleberryFormSwitchEntity(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberryFormSwitchEntity(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    SwitchEntity,
):
    """Native Switch form value for Huckleberry actions."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberrySwitchDescription,
    ) -> None:
        super().__init__(coordinator)
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_switch"
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
    def is_on(self) -> bool:
        value = self.coordinator.get_form_value(
            self._child_uid,
            self.entity_description.key,
        )
        return bool(value)

    async def async_turn_on(self, **kwargs: object) -> None:
        del kwargs
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            True,
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        del kwargs
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            False,
        )
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.enabled_default
