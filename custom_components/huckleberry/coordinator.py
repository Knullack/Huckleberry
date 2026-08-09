from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

try:
    from homeassistant.helpers.event import async_track_time_interval
except ModuleNotFoundError:  # pragma: no cover - test stub compatibility
    def async_track_time_interval(
        hass: HomeAssistant,
        action: Callable[[datetime], None],
        interval: timedelta,
    ) -> Callable[[], None]:
        """Fallback no-op scheduler when Home Assistant event helper is unavailable."""
        del hass, action, interval

        def _unsubscribe() -> None:
            return None

        return _unsubscribe

from .analytics import build_analytics
from .api import (
    HuckleberryAuthenticationError,
    HuckleberryClient,
    HuckleberryTransportError,
)
from .const import (
    ATTR_AMOUNT,
    ATTR_BOTTLE_TYPE,
    ATTR_COLOR,
    ATTR_CONSISTENCY,
    ATTR_DIAPER_RASH,
    ATTR_DURATION_SECONDS,
    ATTR_END_TIME,
    ATTR_FOOD_NOTE_IMAGE,
    ATTR_FOODS,
    ATTR_GROWTH_UNITS,
    ATTR_HEAD,
    ATTR_HEIGHT,
    ATTR_HOW_IT_HAPPENED,
    ATTR_IMAGE,
    ATTR_INCLUDE_ARCHIVED,
    ATTR_LEFT_AMOUNT,
    ATTR_LEFT_DURATION_SECONDS,
    ATTR_MODE,
    ATTR_NOTES,
    ATTR_PEE_AMOUNT,
    ATTR_POO_AMOUNT,
    ATTR_REACTION,
    ATTR_RIGHT_AMOUNT,
    ATTR_RIGHT_DURATION_SECONDS,
    ATTR_SIDE,
    ATTR_START_TIME,
    ATTR_TOTAL_AMOUNT,
    ATTR_UNITS,
    ATTR_WEIGHT,
    CONF_CHILD_NAMES,
    CONF_CHILDREN,
    CONF_ENABLE_REALTIME_LISTENERS,
    CONF_LOOKBACK_HOURS,
    CONF_NIGHT_END_HOUR,
    CONF_NIGHT_START_HOUR,
    CONF_SESSION_HEARTBEAT_MINUTES,
    CONF_UPDATE_INTERVAL_SECONDS,
    DEFAULT_ENABLE_REALTIME_LISTENERS,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_NIGHT_END_HOUR,
    DEFAULT_NIGHT_START_HOUR,
    DEFAULT_SESSION_HEARTBEAT_MINUTES,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    SERVICE_CANCEL_NURSING,
    SERVICE_CANCEL_SLEEP,
    SERVICE_COMPLETE_NURSING,
    SERVICE_COMPLETE_SLEEP,
    SERVICE_CREATE_SOLIDS_CUSTOM_FOOD,
    SERVICE_LIST_SOLIDS_CURATED_FOODS,
    SERVICE_LIST_SOLIDS_CUSTOM_FOODS,
    SERVICE_LOG_ACTIVITY,
    SERVICE_LOG_BOTTLE,
    SERVICE_LOG_DIAPER,
    SERVICE_LOG_GROWTH,
    SERVICE_LOG_NURSING,
    SERVICE_LOG_POTTY,
    SERVICE_LOG_PUMP,
    SERVICE_LOG_SLEEP,
    SERVICE_LOG_SOLIDS,
    SERVICE_PAUSE_NURSING,
    SERVICE_PAUSE_SLEEP,
    SERVICE_RESUME_NURSING,
    SERVICE_RESUME_SLEEP,
    SERVICE_START_NURSING,
    SERVICE_START_SLEEP,
    SERVICE_SWITCH_NURSING_SIDE,
)
from .models import (
    ActivityEvent,
    AnalyticsSnapshot,
    ChildProfile,
    ChildSnapshot,
    DiaperEvent,
    FeedEvent,
    HealthEvent,
    PumpEvent,
    SleepEvent,
    SleepTimer,
)

_LOGGER = logging.getLogger(__name__)


class HuckleberryDataUpdateCoordinator(DataUpdateCoordinator[dict[str, ChildSnapshot]]):
    """Coordinate Huckleberry data updates across configured children."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: HuckleberryClient,
    ) -> None:
        self.config_entry = config_entry
        self.client = client
        self._listeners_started = False
        self._listener_refresh_scheduled = False
        self._session_unsubscribe: Callable[[], None] | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL_SECONDS),
        )

    @property
    def selected_children(self) -> list[str]:
        option_value = self.config_entry.options.get(CONF_CHILDREN)
        data_value = self.config_entry.data.get(CONF_CHILDREN, [])
        if isinstance(option_value, list):
            return option_value
        if isinstance(data_value, list):
            return data_value
        return []

    @property
    def child_names(self) -> dict[str, str]:
        names: dict[str, str] = {}
        data_names = self.config_entry.data.get(CONF_CHILD_NAMES, {})
        option_names = self.config_entry.options.get(CONF_CHILD_NAMES, {})
        if isinstance(data_names, dict):
            names.update({str(key): str(value) for key, value in data_names.items()})
        if isinstance(option_names, dict):
            names.update({str(key): str(value) for key, value in option_names.items()})

        selected = [str(uid) for uid in self.selected_children if str(uid).strip()]
        for index, uid in enumerate(selected):
            if uid not in names:
                names[uid] = f"Child {index + 1}"

        return names

    @property
    def listeners_enabled(self) -> bool:
        value = self.config_entry.options.get(
            CONF_ENABLE_REALTIME_LISTENERS,
            self.config_entry.data.get(
                CONF_ENABLE_REALTIME_LISTENERS,
                DEFAULT_ENABLE_REALTIME_LISTENERS,
            ),
        )
        return bool(value)

    @property
    def session_heartbeat_minutes(self) -> int:
        value = self.config_entry.options.get(
            CONF_SESSION_HEARTBEAT_MINUTES,
            self.config_entry.data.get(
                CONF_SESSION_HEARTBEAT_MINUTES,
                DEFAULT_SESSION_HEARTBEAT_MINUTES,
            ),
        )
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return DEFAULT_SESSION_HEARTBEAT_MINUTES
        return max(5, min(60, minutes))

    async def async_initialize_runtime_features(self) -> None:
        """Enable optional runtime helpers after first refresh."""
        self._start_session_heartbeat()
        if self.listeners_enabled:
            await self._start_realtime_listeners()

    async def async_shutdown_runtime_features(self) -> None:
        """Stop listener and heartbeat runtime helpers."""
        if self._session_unsubscribe is not None:
            self._session_unsubscribe()
            self._session_unsubscribe = None

        if self._listeners_started:
            try:
                await self.client.stop_all_listeners()
            except HuckleberryTransportError as exc:
                _LOGGER.debug("Failed to stop listeners cleanly: %s", exc)
            self._listeners_started = False

    def _start_session_heartbeat(self) -> None:
        if self._session_unsubscribe is not None:
            return

        interval = timedelta(minutes=self.session_heartbeat_minutes)

        def _schedule_tick(_: datetime) -> None:
            self.hass.async_create_task(self._async_session_heartbeat_tick())

        self._session_unsubscribe = async_track_time_interval(
            self.hass,
            _schedule_tick,
            interval,
        )

    async def _async_session_heartbeat_tick(self) -> None:
        try:
            await self.client.ensure_session()
        except HuckleberryAuthenticationError as exc:
            _LOGGER.warning("Session heartbeat authentication failure: %s", exc)
        except HuckleberryTransportError as exc:
            _LOGGER.debug("Session heartbeat transport issue: %s", exc)

    async def _start_realtime_listeners(self) -> None:
        if self._listeners_started:
            return

        for child_uid in self.selected_children:
            callbacks = {
                "sleep": self._listener_callback("sleep", child_uid),
                "feed": self._listener_callback("feed", child_uid),
                "diaper": self._listener_callback("diaper", child_uid),
                "activity": self._listener_callback("activity", child_uid),
                "pump": self._listener_callback("pump", child_uid),
                "health": self._listener_callback("health", child_uid),
            }

            for stream, callback in callbacks.items():
                try:
                    if stream == "sleep":
                        await self.client.setup_sleep_listener(child_uid, callback)
                    elif stream == "feed":
                        await self.client.setup_feed_listener(child_uid, callback)
                    elif stream == "diaper":
                        await self.client.setup_diaper_listener(child_uid, callback)
                    elif stream == "activity":
                        await self.client.setup_activity_listener(child_uid, callback)
                    elif stream == "pump":
                        await self.client.setup_pump_listener(child_uid, callback)
                    elif stream == "health":
                        await self.client.setup_health_listener(child_uid, callback)
                except HuckleberryTransportError as exc:
                    _LOGGER.warning(
                        "Failed to start %s listener for %s: %s",
                        stream,
                        child_uid,
                        exc,
                    )

        self._listeners_started = True

    def _listener_callback(self, stream: str, child_uid: str) -> Callable[[Any], None]:
        def _on_update(_: Any) -> None:
            _LOGGER.debug("Realtime %s update for %s", stream, child_uid)
            self.hass.loop.call_soon_threadsafe(self._schedule_listener_refresh)

        return _on_update

    def _schedule_listener_refresh(self) -> None:
        if self._listener_refresh_scheduled:
            return

        self._listener_refresh_scheduled = True
        self.hass.async_create_task(self._async_listener_refresh())

    async def _async_listener_refresh(self) -> None:
        try:
            await self.async_refresh()
        finally:
            self._listener_refresh_scheduled = False

    async def _async_update_data(self) -> dict[str, ChildSnapshot]:
        interval_seconds = int(
            self.config_entry.options.get(
                CONF_UPDATE_INTERVAL_SECONDS,
                DEFAULT_UPDATE_INTERVAL_SECONDS,
            )
        )
        self.update_interval = timedelta(seconds=max(60, interval_seconds))

        lookback_hours = int(
            self.config_entry.options.get(
                CONF_LOOKBACK_HOURS,
                DEFAULT_LOOKBACK_HOURS,
            )
        )
        night_start_hour = int(
            self.config_entry.options.get(
                CONF_NIGHT_START_HOUR,
                DEFAULT_NIGHT_START_HOUR,
            )
        )
        night_end_hour = int(
            self.config_entry.options.get(
                CONF_NIGHT_END_HOUR,
                DEFAULT_NIGHT_END_HOUR,
            )
        )

        now = dt_util.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        start_time = now - timedelta(hours=max(1, lookback_hours))
        snapshots: dict[str, ChildSnapshot] = {}

        try:
            await self.client.ensure_session()

            for child_uid in self.selected_children:
                timer_task = self.client.get_sleep_timer(child_uid)
                sleep_task = self.client.list_sleep_events(child_uid, start_time, now)
                feed_task = self.client.list_feed_events(child_uid, start_time, now)
                diaper_task = self.client.list_diaper_events(child_uid, start_time, now)
                pump_task = self.client.list_pump_events(child_uid, start_time, now)
                activity_task = self.client.list_activity_events(
                    child_uid,
                    start_time,
                    now,
                )
                health_task = self.client.list_health_events(child_uid, start_time, now)

                (
                    timer,
                    sleep_events,
                    feed_events,
                    diaper_events,
                    pump_events,
                    activity_events,
                    health_events,
                ) = await asyncio.gather(
                    timer_task,
                    sleep_task,
                    feed_task,
                    diaper_task,
                    pump_task,
                    activity_task,
                    health_task,
                )

                typed_timer = cast(SleepTimer, timer)
                typed_sleep_events = cast(list[SleepEvent], sleep_events)
                typed_feed_events = cast(list[FeedEvent], feed_events)
                typed_diaper_events = cast(list[DiaperEvent], diaper_events)
                typed_pump_events = cast(list[PumpEvent], pump_events)
                typed_activity_events = cast(list[ActivityEvent], activity_events)
                typed_health_events = cast(list[HealthEvent], health_events)

                profile = ChildProfile(
                    uid=child_uid,
                    name=self.child_names.get(child_uid, f"Child {child_uid[:6]}"),
                )
                snapshot = ChildSnapshot(
                    profile=profile,
                    timer=typed_timer,
                    sleep_events=typed_sleep_events,
                    feed_events=typed_feed_events,
                    diaper_events=typed_diaper_events,
                    pump_events=typed_pump_events,
                    activity_events=typed_activity_events,
                    health_events=typed_health_events,
                    analytics=AnalyticsSnapshot(),
                )
                snapshot.analytics = build_analytics(
                    snapshot,
                    night_start_hour=night_start_hour,
                    night_end_hour=night_end_hour,
                    now=now,
                )

                snapshots[child_uid] = snapshot

            return snapshots

        except HuckleberryAuthenticationError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except HuckleberryTransportError as exc:
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:  # pylint: disable=broad-except
            raise UpdateFailed(str(exc)) from exc

    def get_snapshot(self, child_uid: str) -> ChildSnapshot | None:
        if not self.data:
            return None
        return self.data.get(child_uid)

    async def async_execute_service(
        self,
        service_name: str,
        child_uid: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if child_uid not in self.selected_children:
            raise HomeAssistantError(
                f"Unknown child UID {child_uid}. "
                "Verify selected children in integration options."
            )

        payload = payload or {}
        snapshot = self.get_snapshot(child_uid)
        timer = snapshot.timer if snapshot is not None else _inactive_sleep_timer()
        response: dict[str, Any] | None = None
        mutates_state = True

        if service_name == SERVICE_START_SLEEP and timer.active:
            raise HomeAssistantError(
                "Cannot start sleep: child already has an active sleep timer"
            )
        if service_name in (
            SERVICE_COMPLETE_SLEEP,
            SERVICE_CANCEL_SLEEP,
            SERVICE_PAUSE_SLEEP,
        ) and not timer.active:
            raise HomeAssistantError("Cannot perform action: no active sleep timer")
        if service_name == SERVICE_PAUSE_SLEEP and timer.paused:
            raise HomeAssistantError("Cannot pause sleep: timer is already paused")
        if service_name == SERVICE_RESUME_SLEEP and (
            not timer.active or not timer.paused
        ):
            raise HomeAssistantError("Cannot resume sleep: no paused timer is active")

        if service_name == SERVICE_START_SLEEP:
            await self.client.start_sleep(child_uid)
        elif service_name == SERVICE_COMPLETE_SLEEP:
            await self.client.complete_sleep(child_uid)
        elif service_name == SERVICE_CANCEL_SLEEP:
            await self.client.cancel_sleep(child_uid)
        elif service_name == SERVICE_PAUSE_SLEEP:
            await self.client.pause_sleep(child_uid)
        elif service_name == SERVICE_RESUME_SLEEP:
            await self.client.resume_sleep(child_uid)
        elif service_name == SERVICE_LOG_SLEEP:
            start_time = _required_service_datetime(
                payload.get(ATTR_START_TIME),
                ATTR_START_TIME,
            )
            end_time = _required_service_datetime(
                payload.get(ATTR_END_TIME),
                ATTR_END_TIME,
            )
            if end_time <= start_time:
                raise HomeAssistantError("end_time must be after start_time")

            await self.client.log_sleep(
                child_uid,
                start_time=start_time,
                end_time=end_time,
            )
        elif service_name == SERVICE_START_NURSING:
            side = _validated_choice(
                payload.get(ATTR_SIDE, "left"),
                ATTR_SIDE,
                {"left", "right"},
            )
            await self.client.start_nursing(child_uid, side=side)
        elif service_name == SERVICE_PAUSE_NURSING:
            await self.client.pause_nursing(child_uid)
        elif service_name == SERVICE_RESUME_NURSING:
            side_value = payload.get(ATTR_SIDE)
            resume_side: str | None = None
            if side_value is not None:
                resume_side = _validated_choice(
                    side_value,
                    ATTR_SIDE,
                    {"left", "right"},
                )
            await self.client.resume_nursing(child_uid, side=resume_side)
        elif service_name == SERVICE_SWITCH_NURSING_SIDE:
            await self.client.switch_nursing_side(child_uid)
        elif service_name == SERVICE_COMPLETE_NURSING:
            await self.client.complete_nursing(child_uid)
        elif service_name == SERVICE_CANCEL_NURSING:
            await self.client.cancel_nursing(child_uid)
        elif service_name == SERVICE_LOG_NURSING:
            start_time = _required_service_datetime(
                payload.get(ATTR_START_TIME),
                ATTR_START_TIME,
            )
            end_time = _required_service_datetime(
                payload.get(ATTR_END_TIME),
                ATTR_END_TIME,
            )
            if end_time <= start_time:
                raise HomeAssistantError("end_time must be after start_time")

            side = _validated_choice(
                payload.get(ATTR_SIDE, "left"),
                ATTR_SIDE,
                {"left", "right"},
            )
            left_duration = _optional_non_negative_float(
                payload.get(ATTR_LEFT_DURATION_SECONDS),
                ATTR_LEFT_DURATION_SECONDS,
            )
            right_duration = _optional_non_negative_float(
                payload.get(ATTR_RIGHT_DURATION_SECONDS),
                ATTR_RIGHT_DURATION_SECONDS,
            )
            if (left_duration is None) != (right_duration is None):
                raise HomeAssistantError(
                    "left_duration_seconds and right_duration_seconds "
                    "must both be provided"
                )

            await self.client.log_nursing(
                child_uid,
                start_time=start_time,
                end_time=end_time,
                side=side,
                left_duration=left_duration,
                right_duration=right_duration,
            )
        elif service_name == SERVICE_LOG_BOTTLE:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            amount = _required_positive_float(payload.get(ATTR_AMOUNT), ATTR_AMOUNT)
            bottle_type = _validated_choice(
                payload.get(ATTR_BOTTLE_TYPE, "Formula"),
                ATTR_BOTTLE_TYPE,
                {
                    "Breast Milk",
                    "Formula",
                    "Tube Feeding",
                    "Cow Milk",
                    "Goat Milk",
                    "Soy Milk",
                    "Other",
                },
            )
            units = _validated_choice(
                payload.get(ATTR_UNITS, "ml"),
                ATTR_UNITS,
                {"ml", "oz"},
            )
            await self.client.log_bottle(
                child_uid,
                start_time=start_time,
                amount=amount,
                bottle_type=bottle_type,
                units=units,
            )
        elif service_name == SERVICE_LOG_DIAPER:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            mode = _validated_choice(
                payload.get(ATTR_MODE),
                ATTR_MODE,
                {"pee", "poo", "both", "dry"},
            )
            pee_amount = _optional_choice(
                payload.get(ATTR_PEE_AMOUNT),
                ATTR_PEE_AMOUNT,
                {"little", "medium", "big"},
            )
            poo_amount = _optional_choice(
                payload.get(ATTR_POO_AMOUNT),
                ATTR_POO_AMOUNT,
                {"little", "medium", "big"},
            )
            color = _optional_choice(
                payload.get(ATTR_COLOR),
                ATTR_COLOR,
                {"yellow", "brown", "black", "green", "red", "gray"},
            )
            consistency = _optional_choice(
                payload.get(ATTR_CONSISTENCY),
                ATTR_CONSISTENCY,
                {"solid", "loose", "runny", "mucousy", "hard", "pebbles", "diarrhea"},
            )
            notes = _optional_string(payload.get(ATTR_NOTES), ATTR_NOTES)
            await self.client.log_diaper(
                child_uid,
                start_time=start_time,
                mode=mode,
                pee_amount=pee_amount,
                poo_amount=poo_amount,
                color=color,
                consistency=consistency,
                diaper_rash=_optional_bool(
                    payload.get(ATTR_DIAPER_RASH),
                    ATTR_DIAPER_RASH,
                ),
                notes=notes,
            )
        elif service_name == SERVICE_LOG_POTTY:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            mode = _validated_choice(
                payload.get(ATTR_MODE),
                ATTR_MODE,
                {"pee", "poo", "both", "dry"},
            )
            how_it_happened = _validated_choice(
                payload.get(ATTR_HOW_IT_HAPPENED),
                ATTR_HOW_IT_HAPPENED,
                {"satButDry", "wentPotty", "accident"},
            )
            pee_amount = _optional_choice(
                payload.get(ATTR_PEE_AMOUNT),
                ATTR_PEE_AMOUNT,
                {"little", "medium", "big"},
            )
            poo_amount = _optional_choice(
                payload.get(ATTR_POO_AMOUNT),
                ATTR_POO_AMOUNT,
                {"little", "medium", "big"},
            )
            color = _optional_choice(
                payload.get(ATTR_COLOR),
                ATTR_COLOR,
                {"yellow", "brown", "black", "green", "red", "gray"},
            )
            consistency = _optional_choice(
                payload.get(ATTR_CONSISTENCY),
                ATTR_CONSISTENCY,
                {"solid", "loose", "runny", "mucousy", "hard", "pebbles", "diarrhea"},
            )
            notes = _optional_string(payload.get(ATTR_NOTES), ATTR_NOTES)
            await self.client.log_potty(
                child_uid,
                start_time=start_time,
                mode=mode,
                how_it_happened=how_it_happened,
                pee_amount=pee_amount,
                poo_amount=poo_amount,
                color=color,
                consistency=consistency,
                notes=notes,
            )
        elif service_name == SERVICE_LOG_GROWTH:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            weight = _optional_non_negative_float(payload.get(ATTR_WEIGHT), ATTR_WEIGHT)
            height = _optional_non_negative_float(payload.get(ATTR_HEIGHT), ATTR_HEIGHT)
            head = _optional_non_negative_float(payload.get(ATTR_HEAD), ATTR_HEAD)
            if weight is None and height is None and head is None:
                raise HomeAssistantError(
                    "At least one of weight, height, or head is required"
                )

            units = _validated_choice(
                payload.get(ATTR_GROWTH_UNITS, "metric"),
                ATTR_GROWTH_UNITS,
                {"metric", "imperial"},
            )
            await self.client.log_growth(
                child_uid,
                start_time=start_time,
                weight=weight,
                height=height,
                head=head,
                units=units,
            )
        elif service_name == SERVICE_LOG_PUMP:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            duration = _optional_non_negative_float(
                payload.get(ATTR_DURATION_SECONDS),
                ATTR_DURATION_SECONDS,
            )
            left_amount = _optional_non_negative_float(
                payload.get(ATTR_LEFT_AMOUNT),
                ATTR_LEFT_AMOUNT,
            )
            right_amount = _optional_non_negative_float(
                payload.get(ATTR_RIGHT_AMOUNT),
                ATTR_RIGHT_AMOUNT,
            )
            total_amount = _optional_non_negative_float(
                payload.get(ATTR_TOTAL_AMOUNT),
                ATTR_TOTAL_AMOUNT,
            )
            units = _validated_choice(
                payload.get(ATTR_UNITS, "ml"),
                ATTR_UNITS,
                {"ml", "oz"},
            )
            notes = _optional_string(payload.get(ATTR_NOTES), ATTR_NOTES)

            if total_amount is not None and (
                left_amount is not None or right_amount is not None
            ):
                raise HomeAssistantError(
                    "Provide either total_amount or left_amount/right_amount, not both"
                )

            if total_amount is None and (
                left_amount is None or right_amount is None
            ):
                raise HomeAssistantError(
                    "Provide total_amount or both left_amount and right_amount"
                )

            await self.client.log_pump(
                child_uid,
                start_time=start_time,
                duration=duration,
                left_amount=left_amount,
                right_amount=right_amount,
                total_amount=total_amount,
                units=units,
                notes=notes,
            )
        elif service_name == SERVICE_LOG_ACTIVITY:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            mode = _validated_choice(
                payload.get(ATTR_MODE),
                ATTR_MODE,
                {
                    "bath",
                    "tummyTime",
                    "storyTime",
                    "screenTime",
                    "skinToSkin",
                    "outdoorPlay",
                    "indoorPlay",
                    "brushTeeth",
                },
            )
            duration = _optional_non_negative_float(
                payload.get(ATTR_DURATION_SECONDS),
                ATTR_DURATION_SECONDS,
            )
            notes = _optional_string(payload.get(ATTR_NOTES), ATTR_NOTES)
            await self.client.log_activity(
                child_uid,
                mode=mode,
                start_time=start_time,
                duration=duration,
                notes=notes,
            )
        elif service_name == SERVICE_LOG_SOLIDS:
            start_time = _service_datetime(payload.get(ATTR_START_TIME), dt_util.now())
            foods = _validated_foods(payload.get(ATTR_FOODS), ATTR_FOODS)
            notes = _optional_string(payload.get(ATTR_NOTES), ATTR_NOTES) or ""
            reaction = _optional_choice(
                payload.get(ATTR_REACTION),
                ATTR_REACTION,
                {"LOVED", "MEH", "HATED", "ALLERGIC"},
            )
            food_note_image = _optional_string(
                payload.get(ATTR_FOOD_NOTE_IMAGE),
                ATTR_FOOD_NOTE_IMAGE,
            )
            await self.client.log_solids(
                child_uid,
                start_time=start_time,
                foods=foods,
                notes=notes,
                reaction=reaction,
                food_note_image=food_note_image,
            )
        elif service_name == SERVICE_CREATE_SOLIDS_CUSTOM_FOOD:
            name = _required_string(payload.get("name"), "name")
            image = _optional_string(payload.get(ATTR_IMAGE), ATTR_IMAGE) or ""
            created = await self.client.create_solids_custom_food(
                child_uid,
                name=name,
                image=image,
            )
            response = {
                "child_uid": child_uid,
                "food": created,
            }
        elif service_name == SERVICE_LIST_SOLIDS_CURATED_FOODS:
            mutates_state = False
            foods = await self.client.list_solids_curated_foods()
            response = {
                "count": len(foods),
                "foods": foods,
            }
        elif service_name == SERVICE_LIST_SOLIDS_CUSTOM_FOODS:
            mutates_state = False
            include_archived = _optional_bool(
                payload.get(ATTR_INCLUDE_ARCHIVED),
                ATTR_INCLUDE_ARCHIVED,
            )
            foods = await self.client.list_solids_custom_foods(
                child_uid,
                include_archived=include_archived,
            )
            response = {
                "child_uid": child_uid,
                "count": len(foods),
                "foods": foods,
            }
        else:
            raise HomeAssistantError(f"Unsupported service {service_name}")

        if mutates_state:
            await self.async_refresh()

        return response


def _inactive_sleep_timer() -> SleepTimer:
    return SleepTimer(
        active=False,
        paused=False,
        timer_start_time_ms=None,
        timer_end_time_ms=None,
        uuid=None,
    )


def _service_datetime(value: Any, default_now: datetime) -> datetime:
    if value is None:
        resolved = default_now
    elif isinstance(value, datetime):
        resolved = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            resolved = default_now
        else:
            if text.endswith("Z"):
                text = f"{text[:-1]}+00:00"
            try:
                resolved = datetime.fromisoformat(text)
            except ValueError as exc:
                raise HomeAssistantError(
                    "start_time must be a valid ISO-8601 datetime"
                ) from exc
    else:
        raise HomeAssistantError("start_time must be a datetime or ISO-8601 string")

    if resolved.tzinfo is None:
        return resolved.replace(tzinfo=UTC)
    return resolved


def _required_service_datetime(value: Any, field_name: str) -> datetime:
    if value is None:
        raise HomeAssistantError(f"{field_name} is required")
    if isinstance(value, str) and not value.strip():
        raise HomeAssistantError(f"{field_name} is required")
    return _service_datetime(value, dt_util.now())


def _required_positive_float(value: Any, field_name: str) -> float:
    if value is None or value == "":
        raise HomeAssistantError(f"{field_name} is required")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HomeAssistantError(f"{field_name} must be a number") from exc

    if number <= 0:
        raise HomeAssistantError(f"{field_name} must be greater than 0")

    return number


def _optional_non_negative_float(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HomeAssistantError(f"{field_name} must be a number") from exc

    if number < 0:
        raise HomeAssistantError(f"{field_name} must be non-negative")
    return number


def _optional_bool(value: Any, field_name: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise HomeAssistantError(f"{field_name} must be a boolean")


def _validated_choice(value: Any, field_name: str, allowed_values: set[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HomeAssistantError(f"{field_name} is required")

    normalized = value.strip()
    if normalized not in allowed_values:
        choices = ", ".join(sorted(allowed_values))
        raise HomeAssistantError(f"{field_name} must be one of: {choices}")
    return normalized


def _optional_choice(
    value: Any,
    field_name: str,
    allowed_values: set[str],
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _validated_choice(value, field_name, allowed_values)


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HomeAssistantError(f"{field_name} must be a string")
    cleaned = value.strip()
    return cleaned or None


def _required_string(value: Any, field_name: str) -> str:
    cleaned = _optional_string(value, field_name)
    if cleaned is None:
        raise HomeAssistantError(f"{field_name} is required")
    return cleaned


def _validated_foods(value: Any, field_name: str) -> list[dict[str, Any]]:
    parsed_value = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise HomeAssistantError(f"{field_name} is required")
        try:
            parsed_value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HomeAssistantError(f"{field_name} must be valid JSON") from exc

    if not isinstance(parsed_value, list) or not parsed_value:
        raise HomeAssistantError(f"{field_name} must be a non-empty list")

    foods: list[dict[str, Any]] = []
    for index, item in enumerate(parsed_value):
        if not isinstance(item, Mapping):
            raise HomeAssistantError(f"{field_name}[{index}] must be an object")

        food_id = _required_string(item.get("id"), f"{field_name}[{index}].id")
        source = _validated_choice(
            item.get("source"),
            f"{field_name}[{index}].source",
            {"curated", "custom"},
        )
        name = _required_string(item.get("name"), f"{field_name}[{index}].name")

        amount = item.get("amount")
        if amount is None:
            raise HomeAssistantError(f"{field_name}[{index}].amount is required")
        if not isinstance(amount, (str, int, float)):
            raise HomeAssistantError(
                f"{field_name}[{index}].amount must be a string or number"
            )

        foods.append(
            {
                "id": food_id,
                "source": source,
                "name": name,
                "amount": amount,
            }
        )

    return foods
