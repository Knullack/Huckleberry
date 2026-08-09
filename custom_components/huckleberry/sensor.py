from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DAY_SLEEP_SECONDS,
    ATTR_FEED_CONFIDENCE,
    ATTR_LAST_ACTIVITY_MODE,
    ATTR_LAST_ACTIVITY_TIME,
    ATTR_LAST_DIAPER_TIME,
    ATTR_LAST_FEED_AMOUNT,
    ATTR_LAST_FEED_TIME,
    ATTR_LAST_FEED_UNITS,
    ATTR_LAST_GROWTH_HEAD,
    ATTR_LAST_GROWTH_HEIGHT,
    ATTR_LAST_GROWTH_TIME,
    ATTR_LAST_GROWTH_WEIGHT,
    ATTR_LAST_PUMP_TIME,
    ATTR_LAST_PUMP_TOTAL_AMOUNT,
    ATTR_LAST_PUMP_UNITS,
    ATTR_LAST_SLEEP_DURATION_SECONDS,
    ATTR_LAST_SLEEP_END,
    ATTR_LAST_SLEEP_START,
    ATTR_NAPS_TODAY,
    ATTR_NEXT_FEED,
    ATTR_NEXT_FEED_OVERDUE_SECONDS,
    ATTR_NEXT_NAP,
    ATTR_NEXT_NAP_OVERDUE_SECONDS,
    ATTR_NIGHT_SLEEP_SECONDS,
    ATTR_RECENT_ACTIVITY_EVENTS,
    ATTR_RECENT_DIAPER_EVENTS,
    ATTR_RECENT_FEED_EVENTS,
    ATTR_RECENT_HEALTH_EVENTS,
    ATTR_RECENT_PUMP_EVENTS,
    ATTR_RECENT_SLEEP_EVENTS,
    ATTR_SLEEP_CONFIDENCE,
    ATTR_SLEEP_DURATION_SECONDS,
    ATTR_SLEEP_DURATION_TEXT,
    ATTR_SLEEP_PAUSED,
    ATTR_SLEEPING,
    DATA_COORDINATOR,
    DOMAIN,
)
from .coordinator import HuckleberryDataUpdateCoordinator
from .models import ChildSnapshot, HealthEvent


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HuckleberryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[SensorEntity] = []
    for child_uid, child_name in coordinator.child_names.items():
        entities.extend(
            [
                HuckleberrySleepStatusSensor(
                    coordinator,
                    entry,
                    child_uid,
                    child_name,
                ),
                HuckleberrySleepDurationSensor(
                    coordinator,
                    entry,
                    child_uid,
                    child_name,
                ),
                HuckleberryLastFeedSensor(coordinator, entry, child_uid, child_name),
                HuckleberryLastDiaperSensor(coordinator, entry, child_uid, child_name),
                HuckleberryLastPumpSensor(coordinator, entry, child_uid, child_name),
                HuckleberryLastActivitySensor(
                    coordinator,
                    entry,
                    child_uid,
                    child_name,
                ),
                HuckleberryLastGrowthSensor(coordinator, entry, child_uid, child_name),
                HuckleberryNapsTodaySensor(coordinator, entry, child_uid, child_name),
                HuckleberryNextNapSensor(coordinator, entry, child_uid, child_name),
                HuckleberryNextFeedSensor(coordinator, entry, child_uid, child_name),
                HuckleberrySleepConfidenceSensor(
                    coordinator,
                    entry,
                    child_uid,
                    child_name,
                ),
                HuckleberryFeedConfidenceSensor(
                    coordinator,
                    entry,
                    child_uid,
                    child_name,
                ),
            ]
        )

    async_add_entities(entities)


class HuckleberryBaseSensor(
    CoordinatorEntity[HuckleberryDataUpdateCoordinator],
    SensorEntity,
):
    """Shared sensor base for child-scoped entities."""

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
        sensor_key: str,
        sensor_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._child_uid = child_uid
        self._child_name = child_name
        self._attr_has_entity_name = True
        self._attr_name = f"{child_name} {sensor_name}"
        self._attr_unique_id = f"{config_entry.entry_id}_{child_uid}_{sensor_key}"

    @property
    def snapshot(self) -> ChildSnapshot | None:
        return self.coordinator.get_snapshot(self._child_uid)

    @property
    def available(self) -> bool:
        return super().available and self.snapshot is not None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._child_uid)},
            name=f"Huckleberry {self._child_name}",
            manufacturer="Huckleberry",
            model="Child Profile",
            entry_type=DeviceEntryType.SERVICE,
        )


class HuckleberrySleepStatusSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="sleep_status",
            sensor_name="Sleep Status",
        )
        self._attr_icon = "mdi:sleep"

    @property
    def native_value(self) -> str | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return "sleeping" if snapshot.analytics.sleeping else "awake"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None:
            return {}

        duration_seconds = _current_sleep_duration_seconds(snapshot)
        sleep_confidence = round(snapshot.analytics.sleep_confidence * 100.0, 1)
        feed_confidence = round(snapshot.analytics.feed_confidence * 100.0, 1)
        last_sleep = snapshot.sleep_events[-1] if snapshot.sleep_events else None

        return {
            ATTR_SLEEPING: snapshot.analytics.sleeping,
            ATTR_SLEEP_PAUSED: snapshot.analytics.sleep_paused,
            ATTR_SLEEP_DURATION_SECONDS: duration_seconds,
            ATTR_SLEEP_DURATION_TEXT: _format_duration(duration_seconds),
            ATTR_LAST_SLEEP_START: last_sleep.start if last_sleep else None,
            ATTR_LAST_SLEEP_END: last_sleep.end if last_sleep else None,
            ATTR_LAST_SLEEP_DURATION_SECONDS: (
                last_sleep.duration_seconds if last_sleep else None
            ),
            ATTR_NAPS_TODAY: snapshot.analytics.naps_today,
            ATTR_DAY_SLEEP_SECONDS: snapshot.analytics.day_sleep_seconds_today,
            ATTR_NIGHT_SLEEP_SECONDS: snapshot.analytics.night_sleep_seconds_today,
            ATTR_NEXT_NAP: snapshot.analytics.next_nap_at,
            ATTR_NEXT_NAP_OVERDUE_SECONDS: snapshot.analytics.next_nap_overdue_seconds,
            ATTR_NEXT_FEED: snapshot.analytics.next_feed_at,
            ATTR_NEXT_FEED_OVERDUE_SECONDS: (
                snapshot.analytics.next_feed_overdue_seconds
            ),
            ATTR_SLEEP_CONFIDENCE: sleep_confidence,
            ATTR_FEED_CONFIDENCE: feed_confidence,
            ATTR_RECENT_SLEEP_EVENTS: _recent_sleep_events(snapshot),
            ATTR_RECENT_PUMP_EVENTS: _recent_pump_events(snapshot),
            ATTR_RECENT_ACTIVITY_EVENTS: _recent_activity_events(snapshot),
            ATTR_RECENT_HEALTH_EVENTS: _recent_health_events(snapshot),
        }


class HuckleberrySleepDurationSensor(HuckleberryBaseSensor):
    _unsub_tick: Any | None

    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="sleep_duration",
            sensor_name="Sleep Duration",
        )
        self._attr_icon = "mdi:timer-outline"
        self._unsub_tick = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _tick(_: datetime) -> None:
            snapshot = self.snapshot
            if snapshot is None:
                return
            if snapshot.timer.active:
                self.async_write_ha_state()

        self._unsub_tick = async_track_time_interval(
            self.hass,
            _tick,
            timedelta(seconds=1),
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> str | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None

        duration = _current_sleep_duration_seconds(snapshot)
        return _format_duration(duration)


class HuckleberryLastFeedSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="last_feed",
            sensor_name="Last Feed",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:baby-bottle-outline"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.feed_events:
            return None
        return snapshot.feed_events[-1].start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.feed_events:
            return {}

        event = snapshot.feed_events[-1]
        return {
            ATTR_LAST_FEED_TIME: event.start,
            ATTR_LAST_FEED_AMOUNT: event.amount,
            ATTR_LAST_FEED_UNITS: event.units,
            ATTR_RECENT_FEED_EVENTS: _recent_feed_events(snapshot),
        }


class HuckleberryLastDiaperSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="last_diaper",
            sensor_name="Last Diaper",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:baby-face-outline"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.diaper_events:
            return None
        return snapshot.diaper_events[-1].start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.diaper_events:
            return {}

        event = snapshot.diaper_events[-1]
        return {
            ATTR_LAST_DIAPER_TIME: event.start,
            "mode": event.mode,
            "pee_amount": event.pee_amount,
            "poo_amount": event.poo_amount,
            ATTR_RECENT_DIAPER_EVENTS: _recent_diaper_events(snapshot),
        }


class HuckleberryLastPumpSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="last_pump",
            sensor_name="Last Pump",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:pump"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.pump_events:
            return None
        return snapshot.pump_events[-1].start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.pump_events:
            return {}

        event = snapshot.pump_events[-1]
        return {
            ATTR_LAST_PUMP_TIME: event.start,
            ATTR_LAST_PUMP_TOTAL_AMOUNT: event.total_amount,
            ATTR_LAST_PUMP_UNITS: event.units,
            "entry_mode": event.entry_mode,
            "left_amount": event.left_amount,
            "right_amount": event.right_amount,
            "duration_seconds": event.duration_seconds,
            "notes": event.notes,
            ATTR_RECENT_PUMP_EVENTS: _recent_pump_events(snapshot),
        }


class HuckleberryLastActivitySensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="last_activity",
            sensor_name="Last Activity",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:run"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.activity_events:
            return None
        return snapshot.activity_events[-1].start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None or not snapshot.activity_events:
            return {}

        event = snapshot.activity_events[-1]
        return {
            ATTR_LAST_ACTIVITY_TIME: event.start,
            ATTR_LAST_ACTIVITY_MODE: event.mode,
            "duration_seconds": event.duration_seconds,
            "notes": event.notes,
            ATTR_RECENT_ACTIVITY_EVENTS: _recent_activity_events(snapshot),
        }


class HuckleberryLastGrowthSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="last_growth",
            sensor_name="Last Growth",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:ruler"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        latest_growth = _latest_growth_event(snapshot)
        if latest_growth is None:
            return None
        return latest_growth.start

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        latest_growth = _latest_growth_event(snapshot)
        if latest_growth is None:
            return {}

        return {
            ATTR_LAST_GROWTH_TIME: latest_growth.start,
            ATTR_LAST_GROWTH_WEIGHT: latest_growth.weight,
            ATTR_LAST_GROWTH_HEIGHT: latest_growth.height,
            ATTR_LAST_GROWTH_HEAD: latest_growth.head,
            "weight_units": latest_growth.weight_units,
            "height_units": latest_growth.height_units,
            "head_units": latest_growth.head_units,
            ATTR_RECENT_HEALTH_EVENTS: _recent_health_events(snapshot),
        }


class HuckleberryNapsTodaySensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="naps_today",
            sensor_name="Naps Today",
        )
        self._attr_icon = "mdi:weather-night"

    @property
    def native_value(self) -> int | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return snapshot.analytics.naps_today


class HuckleberryNextNapSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="next_nap",
            sensor_name="Next Nap",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:sleep"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return snapshot.analytics.next_nap_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None:
            return {}

        return {
            ATTR_NEXT_NAP_OVERDUE_SECONDS: snapshot.analytics.next_nap_overdue_seconds,
        }


class HuckleberryNextFeedSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="next_feed",
            sensor_name="Next Feed",
        )
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_icon = "mdi:baby-bottle-outline"

    @property
    def native_value(self) -> datetime | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return snapshot.analytics.next_feed_at

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.snapshot
        if snapshot is None:
            return {}

        return {
            ATTR_NEXT_FEED_OVERDUE_SECONDS: (
                snapshot.analytics.next_feed_overdue_seconds
            ),
        }


class HuckleberrySleepConfidenceSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="sleep_confidence",
            sensor_name="Sleep Confidence",
        )
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:chart-bell-curve-cumulative"

    @property
    def native_value(self) -> float | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return round(snapshot.analytics.sleep_confidence * 100.0, 1)


class HuckleberryFeedConfidenceSensor(HuckleberryBaseSensor):
    def __init__(
        self,
        coordinator: HuckleberryDataUpdateCoordinator,
        config_entry: ConfigEntry,
        child_uid: str,
        child_name: str,
    ) -> None:
        super().__init__(
            coordinator,
            config_entry,
            child_uid,
            child_name,
            sensor_key="feed_confidence",
            sensor_name="Feed Confidence",
        )
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:chart-timeline-variant"

    @property
    def native_value(self) -> float | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        return round(snapshot.analytics.feed_confidence * 100.0, 1)


def _format_duration(duration_seconds: int | None) -> str | None:
    if duration_seconds is None:
        return None
    duration_seconds = max(0, duration_seconds)
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _current_sleep_duration_seconds(snapshot: ChildSnapshot) -> int | None:
    if snapshot.timer.active and snapshot.timer.timer_start_time_ms is not None:
        now_seconds = datetime.now(tz=UTC).timestamp()
        start_seconds = snapshot.timer.timer_start_time_ms / 1000.0
        return int(max(0.0, now_seconds - start_seconds))
    return snapshot.analytics.current_sleep_duration_seconds


def _recent_sleep_events(
    snapshot: ChildSnapshot,
    limit: int = 20,
) -> list[dict[str, Any]]:
    events = snapshot.sleep_events[-limit:]
    return [
        {
            "id": event.source_id,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "duration_seconds": event.duration_seconds,
        }
        for event in reversed(events)
    ]


def _recent_feed_events(
    snapshot: ChildSnapshot,
    limit: int = 20,
) -> list[dict[str, Any]]:
    events = snapshot.feed_events[-limit:]
    rows: list[dict[str, Any]] = []

    for event in reversed(events):
        left = _value_to_float(event.raw.get("leftDuration"))
        right = _value_to_float(event.raw.get("rightDuration"))
        duration_seconds: int | None = None
        if left is not None or right is not None:
            duration_seconds = int(round((left or 0.0) + (right or 0.0)))

        rows.append(
            {
                "id": event.source_id,
                "start": event.start.isoformat(),
                "mode": event.mode,
                "amount": event.amount,
                "units": event.units,
                "duration_seconds": duration_seconds,
                "left_duration_seconds": left,
                "right_duration_seconds": right,
            }
        )

    return rows


def _recent_diaper_events(
    snapshot: ChildSnapshot,
    limit: int = 20,
) -> list[dict[str, Any]]:
    events = snapshot.diaper_events[-limit:]
    return [
        {
            "id": event.source_id,
            "start": event.start.isoformat(),
            "mode": event.mode,
            "pee_amount": event.pee_amount,
            "poo_amount": event.poo_amount,
            "color": event.raw.get("color"),
            "consistency": event.raw.get("consistency"),
            "notes": event.raw.get("notes"),
        }
        for event in reversed(events)
    ]


def _recent_pump_events(
    snapshot: ChildSnapshot,
    limit: int = 20,
) -> list[dict[str, Any]]:
    events = snapshot.pump_events[-limit:]
    return [
        {
            "id": event.source_id,
            "start": event.start.isoformat(),
            "entry_mode": event.entry_mode,
            "left_amount": event.left_amount,
            "right_amount": event.right_amount,
            "total_amount": event.total_amount,
            "units": event.units,
            "duration_seconds": event.duration_seconds,
            "notes": event.notes,
        }
        for event in reversed(events)
    ]


def _recent_activity_events(
    snapshot: ChildSnapshot,
    limit: int = 20,
) -> list[dict[str, Any]]:
    events = snapshot.activity_events[-limit:]
    return [
        {
            "id": event.source_id,
            "start": event.start.isoformat(),
            "mode": event.mode,
            "duration_seconds": event.duration_seconds,
            "notes": event.notes,
        }
        for event in reversed(events)
    ]


def _recent_health_events(
    snapshot: ChildSnapshot | None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if snapshot is None:
        return []

    events = snapshot.health_events[-limit:]
    return [
        {
            "id": event.source_id,
            "start": event.start.isoformat(),
            "mode": event.mode,
            "weight": event.weight,
            "height": event.height,
            "head": event.head,
            "weight_units": event.weight_units,
            "height_units": event.height_units,
            "head_units": event.head_units,
            "amount": event.amount,
            "units": event.units,
            "medication_name": event.medication_name,
            "notes": event.notes,
        }
        for event in reversed(events)
    ]


def _latest_growth_event(snapshot: ChildSnapshot | None) -> HealthEvent | None:
    if snapshot is None:
        return None
    for event in reversed(snapshot.health_events):
        if event.mode == "growth":
            return event
    return None


def _value_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
