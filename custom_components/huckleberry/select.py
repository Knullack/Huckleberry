from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HuckleberryDataUpdateCoordinator
from .form_state import (
    ACTIVITY_TYPE_OPTIONS,
    BOTTLE_TYPE_OPTIONS,
    BOTTLE_UNIT_OPTIONS,
    DIAPER_AMOUNT_OPTIONS,
    DIAPER_COLOR_OPTIONS,
    DIAPER_CONSISTENCY_OPTIONS,
    DIAPER_MODE_OPTIONS,
    FIELD_ACTIVITY_TYPE,
    FIELD_BOTTLE_TYPE,
    FIELD_BOTTLE_UNITS,
    FIELD_DIAPER_MODE,
    FIELD_PEE_AMOUNT,
    FIELD_POO_AMOUNT,
    FIELD_POO_COLOR,
    FIELD_POO_CONSISTENCY,
)


@dataclass(frozen=True, slots=True)
class HuckleberrySelectDescription:
    key: str
    name: str
    icon: str
    options: tuple[str, ...]
    enabled_default: bool = True


SELECT_FIELDS: tuple[HuckleberrySelectDescription, ...] = (
    HuckleberrySelectDescription(
        key=FIELD_ACTIVITY_TYPE,
        name="Activity Type",
        icon="mdi:run",
        options=ACTIVITY_TYPE_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_BOTTLE_TYPE,
        name="Bottle Type",
        icon="mdi:baby-bottle",
        options=BOTTLE_TYPE_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_BOTTLE_UNITS,
        name="Bottle Units",
        icon="mdi:ruler",
        options=BOTTLE_UNIT_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_DIAPER_MODE,
        name="Diaper Mode",
        icon="mdi:baby-face-outline",
        options=DIAPER_MODE_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_PEE_AMOUNT,
        name="Pee Amount",
        icon="mdi:water",
        options=DIAPER_AMOUNT_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_POO_AMOUNT,
        name="Poo Amount",
        icon="mdi:scale",
        options=DIAPER_AMOUNT_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_POO_COLOR,
        name="Poo Color",
        icon="mdi:palette",
        options=DIAPER_COLOR_OPTIONS,
    ),
    HuckleberrySelectDescription(
        key=FIELD_POO_CONSISTENCY,
        name="Poo Consistency",
        icon="mdi:texture",
        options=DIAPER_CONSISTENCY_OPTIONS,
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

    entities: list[HuckleberryFormSelectEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in SELECT_FIELDS:
            entities.append(
                HuckleberryFormSelectEntity(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberryFormSelectEntity(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    SelectEntity,
):
    """Native Select form value for Huckleberry actions."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberrySelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_select"
        )
        self._attr_icon = description.icon
        self._attr_options = list(description.options)
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
    def current_option(self) -> str | None:
        value = self.coordinator.get_form_value(
            self._child_uid,
            self.entity_description.key,
        )
        if isinstance(value, str) and value in self.entity_description.options:
            return value
        return self.entity_description.options[0]

    def select_option(self, option: str) -> None:
        if option not in self.entity_description.options:
            raise HomeAssistantError(
                f"Unsupported option {option} for {self.entity_description.key}"
            )
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            option,
        )
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.enabled_default
