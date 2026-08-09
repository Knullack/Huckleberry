from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import HuckleberryDataUpdateCoordinator
from .form_state import FIELD_ACTIVITY_DURATION, FIELD_BOTTLE_AMOUNT


@dataclass(frozen=True, slots=True)
class HuckleberryNumberDescription:
    key: str
    name: str
    icon: str
    native_min_value: float
    native_max_value: float
    native_step: float
    native_unit_of_measurement: str | None = None
    device_class: NumberDeviceClass | None = None
    enabled_default: bool = True


NUMBER_FIELDS: tuple[HuckleberryNumberDescription, ...] = (
    HuckleberryNumberDescription(
        key=FIELD_BOTTLE_AMOUNT,
        name="Bottle Amount",
        icon="mdi:baby-bottle-outline",
        native_min_value=0.0,
        native_max_value=1000.0,
        native_step=0.1,
    ),
    HuckleberryNumberDescription(
        key=FIELD_ACTIVITY_DURATION,
        name="Activity Duration (Seconds)",
        icon="mdi:timer-outline",
        native_min_value=0.0,
        native_max_value=86400.0,
        native_step=1.0,
        native_unit_of_measurement="s",
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

    entities: list[HuckleberryFormNumberEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in NUMBER_FIELDS:
            entities.append(
                HuckleberryFormNumberEntity(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberryFormNumberEntity(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    NumberEntity,
):
    """Native Number form value for Huckleberry actions."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberryNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_number"
        )
        self._attr_icon = description.icon
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
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
    def native_value(self) -> float:
        value = self.coordinator.get_form_value(
            self._child_uid,
            self.entity_description.key,
        )
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.set_form_value(
            self._child_uid,
            self.entity_description.key,
            value,
        )
        self.async_write_ha_state()

    @property
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.enabled_default
