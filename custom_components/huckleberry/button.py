from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    SERVICE_CANCEL_NURSING,
    SERVICE_CANCEL_SLEEP,
    SERVICE_COMPLETE_NURSING,
    SERVICE_COMPLETE_SLEEP,
    SERVICE_PAUSE_NURSING,
    SERVICE_PAUSE_SLEEP,
    SERVICE_RESUME_NURSING,
    SERVICE_RESUME_SLEEP,
    SERVICE_START_NURSING,
    SERVICE_START_SLEEP,
    SERVICE_SWITCH_NURSING_SIDE,
)
from .coordinator import HuckleberryDataUpdateCoordinator
from .models import ChildSnapshot


@dataclass(frozen=True, slots=True)
class HuckleberryButtonDescription:
    key: str
    name: str
    icon: str
    service: str


BUTTONS: tuple[HuckleberryButtonDescription, ...] = (
    HuckleberryButtonDescription(
        key="start_sleep",
        name="Start Sleep",
        icon="mdi:play",
        service=SERVICE_START_SLEEP,
    ),
    HuckleberryButtonDescription(
        key="complete_sleep",
        name="Complete Sleep",
        icon="mdi:check",
        service=SERVICE_COMPLETE_SLEEP,
    ),
    HuckleberryButtonDescription(
        key="cancel_sleep",
        name="Cancel Sleep",
        icon="mdi:close",
        service=SERVICE_CANCEL_SLEEP,
    ),
    HuckleberryButtonDescription(
        key="pause_sleep",
        name="Pause Sleep",
        icon="mdi:pause",
        service=SERVICE_PAUSE_SLEEP,
    ),
    HuckleberryButtonDescription(
        key="resume_sleep",
        name="Resume Sleep",
        icon="mdi:play-pause",
        service=SERVICE_RESUME_SLEEP,
    ),
    HuckleberryButtonDescription(
        key="start_nursing",
        name="Start Nursing",
        icon="mdi:play-circle-outline",
        service=SERVICE_START_NURSING,
    ),
    HuckleberryButtonDescription(
        key="pause_nursing",
        name="Pause Nursing",
        icon="mdi:pause-circle-outline",
        service=SERVICE_PAUSE_NURSING,
    ),
    HuckleberryButtonDescription(
        key="resume_nursing",
        name="Resume Nursing",
        icon="mdi:play-pause",
        service=SERVICE_RESUME_NURSING,
    ),
    HuckleberryButtonDescription(
        key="switch_nursing_side",
        name="Switch Nursing Side",
        icon="mdi:swap-horizontal",
        service=SERVICE_SWITCH_NURSING_SIDE,
    ),
    HuckleberryButtonDescription(
        key="complete_nursing",
        name="Complete Nursing",
        icon="mdi:check-circle-outline",
        service=SERVICE_COMPLETE_NURSING,
    ),
    HuckleberryButtonDescription(
        key="cancel_nursing",
        name="Cancel Nursing",
        icon="mdi:close-circle-outline",
        service=SERVICE_CANCEL_NURSING,
    ),
)

NURSING_SERVICES = {
    SERVICE_START_NURSING,
    SERVICE_PAUSE_NURSING,
    SERVICE_RESUME_NURSING,
    SERVICE_SWITCH_NURSING_SIDE,
    SERVICE_COMPLETE_NURSING,
    SERVICE_CANCEL_NURSING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HuckleberryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[HuckleberrySleepControlButton] = []
    for child_uid, child_name in coordinator.child_names.items():
        for description in BUTTONS:
            entities.append(
                HuckleberrySleepControlButton(
                    coordinator=coordinator,
                    config_entry=entry,
                    child_uid=child_uid,
                    child_name=child_name,
                    description=description,
                )
            )

    async_add_entities(entities)


class HuckleberrySleepControlButton(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator], ButtonEntity
):
    """Button entity for safe sleep controls."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        description: HuckleberryButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._child_uid = child_uid
        self._child_name = child_name
        self.entity_description = description
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {description.name}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}_{child_uid}_{description.key}_button"
        )
        self._attr_icon = description.icon

    @property
    def snapshot(self) -> ChildSnapshot | None:
        return self.coordinator.get_snapshot(self._child_uid)

    @property
    def available(self) -> bool:
        snapshot = self.snapshot
        return super().available and snapshot is not None

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
    def entity_registry_enabled_default(self) -> bool:
        return self.entity_description.service in {
            SERVICE_START_SLEEP,
            SERVICE_COMPLETE_SLEEP,
            SERVICE_CANCEL_SLEEP,
            SERVICE_START_NURSING,
            SERVICE_COMPLETE_NURSING,
            SERVICE_CANCEL_NURSING,
        }

    async def async_press(self) -> None:
        if not self._can_press():
            raise HomeAssistantError(
                f"Action {self.entity_description.service} is not currently available"
            )

        await self.coordinator.async_execute_service(
            self.entity_description.service,
            self._child_uid,
        )

    def _can_press(self) -> bool:
        snapshot = self.snapshot
        if snapshot is None:
            return False

        timer = snapshot.timer
        service = self.entity_description.service

        if service == SERVICE_START_SLEEP:
            return not timer.active
        if service in {SERVICE_COMPLETE_SLEEP, SERVICE_CANCEL_SLEEP}:
            return timer.active
        if service == SERVICE_PAUSE_SLEEP:
            return timer.active and not timer.paused
        if service == SERVICE_RESUME_SLEEP:
            return timer.active and timer.paused

        return service in NURSING_SERVICES
