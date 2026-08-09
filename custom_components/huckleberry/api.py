from __future__ import annotations

import importlib
import inspect
import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .models import (
    ActivityEvent,
    ChildProfile,
    DiaperEvent,
    FeedEvent,
    HealthEvent,
    PumpEvent,
    SleepEvent,
    SleepTimer,
)
from .storage import HuckleberryDeleteLogStorage

_LOGGER = logging.getLogger(__name__)


class HuckleberryClientError(Exception):
    """Base exception for Huckleberry client failures."""


class HuckleberryAuthenticationError(HuckleberryClientError):
    """Raised when authentication fails."""


class HuckleberryTransportError(HuckleberryClientError):
    """Raised when network or backend issues occur."""


class HuckleberryClient:
    """Thin typed wrapper around huckleberry-api public methods."""

    def __init__(
        self,
        hass: Any,
        email: str,
        password: str,
        timezone: str,
        entry_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._email = email
        self._password = password
        self._timezone = timezone
        self._entry_id = entry_id or "default"
        self._tz = ZoneInfo(timezone)
        self._api: Any | None = None
        self._delete_log_storage: HuckleberryDeleteLogStorage | None = None

    @property
    def timezone(self) -> str:
        return self._timezone

    async def authenticate(self) -> None:
        """Authenticate with Huckleberry backend."""
        if self._api is None:
            self._api = await self._build_api()

        api = self._api
        if api is None:
            raise HuckleberryClientError("Failed to initialize API client")

        try:
            await api.authenticate()
        except Exception as exc:  # pylint: disable=broad-except
            message = str(exc).lower()
            if "auth" in message or "credential" in message or "password" in message:
                raise HuckleberryAuthenticationError(str(exc)) from exc
            raise HuckleberryTransportError(str(exc)) from exc

    async def discover_children(self) -> list[ChildProfile]:
        """Discover available children for the authenticated user."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before child discovery"
            )

        payload = await self._api.get_user()
        raw = self._to_dict(payload)

        candidates = self._extract_children(raw)
        unique: dict[str, ChildProfile] = {}

        for child in candidates:
            if not child.uid:
                continue
            if child.uid in unique:
                if unique[child.uid].name.startswith("Child ") and child.name:
                    unique[child.uid] = child
                continue
            unique[child.uid] = child

        if not unique:
            child_uids = self._extract_child_uid_list(raw)
            unique = {
                uid: ChildProfile(uid=uid, name=f"Child {index + 1}")
                for index, uid in enumerate(child_uids)
            }
            if not unique:
                _LOGGER.warning(
                    "No child candidates found in user payload; keys=%s",
                    sorted(raw.keys()),
                )

        enriched: list[ChildProfile] = []
        for child in unique.values():
            try:
                details_raw = self._to_dict(await self._api.get_child(child.uid))
                details_name = self._best_name(details_raw)
                enriched.append(
                    replace(child, name=details_name if details_name else child.name)
                )
            except Exception:  # pylint: disable=broad-except
                enriched.append(child)

        return sorted(enriched, key=lambda child: child.name.lower())

    async def list_sleep_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[SleepEvent]:
        """List and normalize sleep interval events."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_sleep_intervals(
            child_uid,
            start_time,
            end_time,
        )

        events: list[SleepEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start = float(row.get("start", 0.0))
            duration = int(float(row.get("duration", 0.0)))
            start_dt = datetime.fromtimestamp(start, tz=UTC).astimezone(self._tz)
            end_dt = start_dt + timedelta(seconds=duration)
            source_id = str(row.get("id_") or row.get("id") or f"sleep-{index}")
            events.append(
                SleepEvent(
                    source_id=source_id,
                    start=start_dt,
                    end=end_dt,
                    duration_seconds=duration,
                    offset_minutes=self._optional_float(row.get("offset")),
                    end_offset_minutes=self._optional_float(row.get("end_offset")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], SleepEvent] = {}
        for event in events:
            key = self._sleep_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("sleep-")
                and not event.source_id.startswith("sleep-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def list_feed_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[FeedEvent]:
        """List and normalize feed events."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_feed_intervals(
            child_uid,
            start_time,
            end_time,
        )

        events: list[FeedEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start = float(row.get("start", 0.0))
            start_dt = datetime.fromtimestamp(start, tz=UTC).astimezone(self._tz)
            source_id = str(row.get("id_") or row.get("id") or f"feed-{index}")
            events.append(
                FeedEvent(
                    source_id=source_id,
                    start=start_dt,
                    amount=self._optional_float(row.get("amount")),
                    units=self._optional_str(row.get("units")),
                    mode=self._optional_str(row.get("mode")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], FeedEvent] = {}
        for event in events:
            key = self._feed_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("feed-")
                and not event.source_id.startswith("feed-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def list_diaper_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[DiaperEvent]:
        """List and normalize diaper events."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_diaper_intervals(
            child_uid,
            start_time,
            end_time,
        )

        events: list[DiaperEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start = float(row.get("start", 0.0))
            start_dt = datetime.fromtimestamp(start, tz=UTC).astimezone(self._tz)
            quantity = self._to_dict(row.get("quantity"))
            source_id = str(row.get("id_") or row.get("id") or f"diaper-{index}")
            events.append(
                DiaperEvent(
                    source_id=source_id,
                    start=start_dt,
                    mode=self._optional_str(row.get("mode")),
                    pee_amount=self._optional_float(quantity.get("pee")),
                    poo_amount=self._optional_float(quantity.get("poo")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], DiaperEvent] = {}
        for event in events:
            key = self._diaper_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("diaper-")
                and not event.source_id.startswith("diaper-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def list_pump_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[PumpEvent]:
        """List and normalize pump events."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_pump_intervals(
            child_uid,
            start_time,
            end_time,
        )

        events: list[PumpEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start = float(row.get("start", 0.0))
            start_dt = datetime.fromtimestamp(start, tz=UTC).astimezone(self._tz)
            source_id = str(
                row.get("id_") or row.get("_id") or row.get("id") or f"pump-{index}"
            )
            left_amount = self._optional_float(row.get("leftAmount"))
            right_amount = self._optional_float(row.get("rightAmount"))
            total_amount: float | None = None
            if left_amount is not None or right_amount is not None:
                total_amount = (left_amount or 0.0) + (right_amount or 0.0)

            events.append(
                PumpEvent(
                    source_id=source_id,
                    start=start_dt,
                    entry_mode=self._optional_str(row.get("entryMode")),
                    left_amount=left_amount,
                    right_amount=right_amount,
                    total_amount=total_amount,
                    units=self._optional_str(row.get("units")),
                    duration_seconds=self._optional_float(row.get("duration")),
                    notes=self._optional_str(row.get("notes")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], PumpEvent] = {}
        for event in events:
            key = self._pump_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("pump-")
                and not event.source_id.startswith("pump-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def list_activity_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[ActivityEvent]:
        """List and normalize activity events."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_activity_intervals(
            child_uid,
            start_time,
            end_time,
        )

        events: list[ActivityEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start = float(row.get("start", 0.0))
            start_dt = datetime.fromtimestamp(start, tz=UTC).astimezone(self._tz)
            source_id = str(
                row.get("id_")
                or row.get("_id")
                or row.get("id")
                or f"activity-{index}"
            )

            events.append(
                ActivityEvent(
                    source_id=source_id,
                    start=start_dt,
                    mode=self._optional_str(row.get("mode")),
                    duration_seconds=self._optional_float(row.get("duration")),
                    notes=self._optional_str(row.get("notes")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], ActivityEvent] = {}
        for event in events:
            key = self._activity_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("activity-")
                and not event.source_id.startswith("activity-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def list_health_events(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[HealthEvent]:
        """List and normalize health events (growth/medication/temperature)."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_events = await self._api.list_health_entries(
            child_uid,
            start_time,
            end_time,
        )

        events: list[HealthEvent] = []
        for index, entry in enumerate(self._iter_entries(raw_events)):
            row = self._to_dict(entry)
            start_value = self._optional_float(row.get("start"))
            if start_value is None:
                continue

            start_dt = datetime.fromtimestamp(start_value, tz=UTC).astimezone(self._tz)
            source_id = str(
                row.get("id_")
                or row.get("_id")
                or row.get("id")
                or f"health-{index}"
            )
            events.append(
                HealthEvent(
                    source_id=source_id,
                    start=start_dt,
                    mode=self._optional_str(row.get("mode")),
                    weight=self._optional_float(row.get("weight")),
                    height=self._optional_float(row.get("height")),
                    head=self._optional_float(row.get("head")),
                    weight_units=self._optional_str(row.get("weightUnits")),
                    height_units=self._optional_str(row.get("heightUnits")),
                    head_units=self._optional_str(row.get("headUnits")),
                    amount=self._optional_float(row.get("amount")),
                    units=self._optional_str(row.get("units")),
                    medication_name=self._optional_str(row.get("medication_name")),
                    notes=self._optional_str(row.get("notes")),
                    raw=row,
                )
            )

        deduped: dict[tuple[Any, ...], HealthEvent] = {}
        for event in events:
            key = self._health_event_key(event)
            existing = deduped.get(key)
            prefer_event = existing is None or (
                existing.source_id.startswith("health-")
                and not event.source_id.startswith("health-")
            )
            if prefer_event:
                deduped[key] = event

        return sorted(deduped.values(), key=lambda event: event.start)

    async def get_latest_growth_event(self, child_uid: str) -> HealthEvent | None:
        """Get and normalize the latest growth event."""
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        raw_entry = await self._api.get_latest_growth(child_uid)
        row = self._to_dict(raw_entry)
        if not row:
            return None

        start_value = self._optional_float(row.get("start"))
        if start_value is None:
            return None

        start_dt = datetime.fromtimestamp(start_value, tz=UTC).astimezone(self._tz)
        source_id = str(row.get("id_") or row.get("_id") or row.get("id") or "growth")
        return HealthEvent(
            source_id=source_id,
            start=start_dt,
            mode="growth",
            weight=self._optional_float(row.get("weight")),
            height=self._optional_float(row.get("height")),
            head=self._optional_float(row.get("head")),
            weight_units=self._optional_str(row.get("weightUnits")),
            height_units=self._optional_str(row.get("heightUnits")),
            head_units=self._optional_str(row.get("headUnits")),
            amount=None,
            units=None,
            medication_name=None,
            notes=None,
            raw=row,
        )

    async def get_sleep_timer(self, child_uid: str) -> SleepTimer:
        """Get live sleep timer state.

        The upstream package does not currently expose a public timer read method.
        This uses a guarded fallback to private Firestore access when available.
        If unavailable, we return an inactive timer state.
        """
        if self._api is None:
            raise HuckleberryClientError(
                "authenticate must be called before listing events"
            )

        default_timer = SleepTimer(
            active=False,
            paused=False,
            timer_start_time_ms=None,
            timer_end_time_ms=None,
            uuid=None,
        )

        firestore_getter = getattr(self._api, "_get_firestore_client", None)
        if firestore_getter is None:
            return default_timer

        try:
            firestore_client = await self._maybe_await(firestore_getter())
            sleep_ref = firestore_client.collection("sleep").document(child_uid)
            snapshot = await self._maybe_await(sleep_ref.get())
            document = self._to_dict(snapshot.to_dict())
            timer = self._to_dict(document.get("timer"))
            return SleepTimer(
                active=bool(timer.get("active", False)),
                paused=bool(timer.get("paused", False)),
                timer_start_time_ms=self._optional_float(timer.get("timerStartTime")),
                timer_end_time_ms=self._optional_float(timer.get("timerEndTime")),
                uuid=self._optional_str(timer.get("uuid")),
            )
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.debug("Falling back to inactive timer due to read error: %s", exc)
            return default_timer

    async def ensure_session(self) -> None:
        """Ensure the underlying API session is authenticated and refreshed."""
        await self._call_api("ensure_session")

    async def refresh_session_token(self) -> None:
        """Force refresh of the underlying API session token."""
        await self._call_api("refresh_session_token")

    async def start_sleep(self, child_uid: str) -> None:
        await self._call_action("start_sleep", child_uid)

    async def complete_sleep(self, child_uid: str) -> None:
        await self._call_action("complete_sleep", child_uid)

    async def cancel_sleep(self, child_uid: str) -> None:
        await self._call_action("cancel_sleep", child_uid)

    async def pause_sleep(self, child_uid: str) -> None:
        await self._call_action("pause_sleep", child_uid)

    async def resume_sleep(self, child_uid: str) -> None:
        await self._call_action("resume_sleep", child_uid)

    async def log_sleep(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        await self._call_action(
            "log_sleep",
            child_uid,
            start_time=start_time,
            end_time=end_time,
        )

    async def delete_sleep(self, child_uid: str, *, interval_id: str) -> None:
        await self._delete_interval_document(
            action_name="delete_sleep",
            collection_name="sleep",
            child_uid=child_uid,
            interval_id=interval_id,
        )

    async def list_deleted_intervals(
        self,
        child_uid: str,
        *,
        collection_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        store = self._require_delete_log_storage()
        return await store.async_list_entries(
            child_uid=child_uid,
            collection_name=collection_name,
            limit=limit,
        )

    async def restore_deleted_interval(
        self,
        child_uid: str,
        *,
        log_id: str,
    ) -> dict[str, Any]:
        if self._api is None:
            raise HuckleberryClientError("authenticate must be called before actions")

        cleaned_log_id = log_id.strip()
        if not cleaned_log_id:
            raise HuckleberryClientError("log_id is required")

        store = self._require_delete_log_storage()
        entry = await store.async_get_entry(cleaned_log_id)
        if entry is None:
            raise HuckleberryClientError(
                f"Delete log entry {cleaned_log_id} was not found"
            )

        stored_child_uid = str(entry.get("child_uid", "")).strip()
        if stored_child_uid != child_uid:
            raise HuckleberryClientError("log_id does not match the selected child")

        collection_name = str(entry.get("collection", "")).strip()
        if collection_name not in {"feed", "diaper", "sleep"}:
            raise HuckleberryClientError(
                f"Delete log entry {cleaned_log_id} has unsupported collection"
            )

        payload = entry.get("payload")
        if not isinstance(payload, Mapping):
            raise HuckleberryClientError(
                f"Delete log entry {cleaned_log_id} is missing payload data"
            )

        firestore_getter = getattr(self._api, "_get_firestore_client", None)
        if not callable(firestore_getter):
            raise HuckleberryClientError(
                "restore_deleted_interval is unavailable: "
                "no Firestore access in upstream API"
            )

        try:
            firestore_client = await self._maybe_await(firestore_getter())
            timestamp_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
            new_interval_id = f"{timestamp_ms}-{uuid4().hex[:20]}"
            interval_ref = (
                firestore_client.collection(collection_name)
                .document(child_uid)
                .collection("intervals")
                .document(new_interval_id)
            )
            await self._maybe_await(interval_ref.set(dict(payload)))
            return {
                "log_id": cleaned_log_id,
                "child_uid": child_uid,
                "collection": collection_name,
                "new_interval_id": new_interval_id,
                "restored_from_interval_id": entry.get("interval_id"),
                "deleted_at": entry.get("deleted_at"),
            }
        except Exception as exc:  # pylint: disable=broad-except
            raise HuckleberryTransportError(str(exc)) from exc

    async def start_nursing(self, child_uid: str, side: str = "left") -> None:
        await self._call_action("start_nursing", child_uid, side=side)

    async def pause_nursing(self, child_uid: str) -> None:
        await self._call_action("pause_nursing", child_uid)

    async def resume_nursing(self, child_uid: str, side: str | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if side is not None:
            kwargs["side"] = side
        await self._call_action("resume_nursing", child_uid, **kwargs)

    async def switch_nursing_side(self, child_uid: str) -> None:
        await self._call_action("switch_nursing_side", child_uid)

    async def complete_nursing(self, child_uid: str) -> None:
        await self._call_action("complete_nursing", child_uid)

    async def cancel_nursing(self, child_uid: str) -> None:
        await self._call_action("cancel_nursing", child_uid)

    async def log_nursing(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        end_time: datetime,
        side: str = "left",
        left_duration: float | None = None,
        right_duration: float | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {
            "start_time": start_time,
            "end_time": end_time,
            "side": side,
        }
        if left_duration is not None:
            kwargs["left_duration"] = left_duration
        if right_duration is not None:
            kwargs["right_duration"] = right_duration
        await self._call_action("log_nursing", child_uid, **kwargs)

    async def log_bottle(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        amount: float,
        bottle_type: str = "Formula",
        units: str = "ml",
    ) -> None:
        await self._call_action(
            "log_bottle",
            child_uid,
            start_time=start_time,
            amount=amount,
            bottle_type=bottle_type,
            units=units,
        )

    async def delete_bottle(self, child_uid: str, *, interval_id: str) -> None:
        await self._delete_interval_document(
            action_name="delete_bottle",
            collection_name="feed",
            child_uid=child_uid,
            interval_id=interval_id,
        )

    async def log_diaper(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        mode: str,
        pee_amount: str | None = None,
        poo_amount: str | None = None,
        color: str | None = None,
        consistency: str | None = None,
        diaper_rash: bool = False,
        notes: str | None = None,
    ) -> None:
        await self._call_action(
            "log_diaper",
            child_uid,
            start_time=start_time,
            mode=mode,
            pee_amount=pee_amount,
            poo_amount=poo_amount,
            color=color,
            consistency=consistency,
            diaper_rash=diaper_rash,
            notes=notes,
        )

    async def delete_diaper(self, child_uid: str, *, interval_id: str) -> None:
        await self._delete_interval_document(
            action_name="delete_diaper",
            collection_name="diaper",
            child_uid=child_uid,
            interval_id=interval_id,
        )

    async def log_potty(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        mode: str,
        how_it_happened: str,
        pee_amount: str | None = None,
        poo_amount: str | None = None,
        color: str | None = None,
        consistency: str | None = None,
        notes: str | None = None,
    ) -> None:
        await self._call_action(
            "log_potty",
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

    async def log_growth(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        weight: float | None = None,
        height: float | None = None,
        head: float | None = None,
        units: str = "metric",
    ) -> None:
        await self._call_action(
            "log_growth",
            child_uid,
            start_time=start_time,
            weight=weight,
            height=height,
            head=head,
            units=units,
        )

    async def log_pump(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        duration: float | None = None,
        left_amount: float | None = None,
        right_amount: float | None = None,
        total_amount: float | None = None,
        units: str = "ml",
        notes: str | None = None,
    ) -> None:
        await self._call_action(
            "log_pump",
            child_uid,
            start_time=start_time,
            duration=duration,
            left_amount=left_amount,
            right_amount=right_amount,
            total_amount=total_amount,
            units=units,
            notes=notes,
        )

    async def log_activity(
        self,
        child_uid: str,
        *,
        mode: str,
        start_time: datetime,
        duration: float | None = None,
        notes: str | None = None,
    ) -> None:
        await self._call_action(
            "log_activity",
            child_uid,
            mode=mode,
            start_time=start_time,
            duration=duration,
            notes=notes,
        )

    async def log_solids(
        self,
        child_uid: str,
        *,
        start_time: datetime,
        foods: list[dict[str, Any]],
        notes: str = "",
        reaction: str | None = None,
        food_note_image: str | None = None,
    ) -> None:
        await self._call_action(
            "log_solids",
            child_uid,
            start_time=start_time,
            foods=foods,
            notes=notes,
            reaction=reaction,
            food_note_image=food_note_image,
        )

    async def create_solids_custom_food(
        self,
        child_uid: str,
        *,
        name: str,
        image: str = "",
    ) -> dict[str, Any]:
        payload = await self._call_action_result(
            "create_solids_custom_food",
            child_uid,
            name=name,
            image=image,
        )
        return self._to_dict(payload)

    async def list_solids_curated_foods(self) -> list[dict[str, Any]]:
        payload = await self._call_api_result("list_solids_curated_foods")
        rows = [self._to_dict(entry) for entry in self._iter_entries(payload)]
        return [row for row in rows if row]

    async def list_solids_custom_foods(
        self,
        child_uid: str,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        payload = await self._call_action_result(
            "list_solids_custom_foods",
            child_uid,
            include_archived=include_archived,
        )
        rows = [self._to_dict(entry) for entry in self._iter_entries(payload)]
        return [row for row in rows if row]

    async def setup_sleep_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_sleep_listener", child_uid, callback=callback)

    async def setup_feed_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_feed_listener", child_uid, callback=callback)

    async def setup_health_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_health_listener", child_uid, callback=callback)

    async def setup_diaper_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_diaper_listener", child_uid, callback=callback)

    async def setup_activity_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_activity_listener", child_uid, callback=callback)

    async def setup_pump_listener(self, child_uid: str, callback: Any) -> None:
        await self._call_action("setup_pump_listener", child_uid, callback=callback)

    async def stop_all_listeners(self) -> None:
        await self._call_api("stop_all_listeners")

    async def _call_action(self, action: str, child_uid: str, **kwargs: Any) -> None:
        await self._call_action_result(action, child_uid, **kwargs)

    async def _call_action_result(
        self,
        action: str,
        child_uid: str,
        **kwargs: Any,
    ) -> Any:
        if self._api is None:
            raise HuckleberryClientError("authenticate must be called before actions")

        method = getattr(self._api, action, None)
        if method is None:
            raise HuckleberryClientError(f"Action {action} is not available")

        try:
            return await method(child_uid, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            raise HuckleberryTransportError(str(exc)) from exc

    async def _call_api(self, action: str, **kwargs: Any) -> None:
        await self._call_api_result(action, **kwargs)

    async def _call_api_result(self, action: str, **kwargs: Any) -> Any:
        if self._api is None:
            raise HuckleberryClientError("authenticate must be called before actions")

        method = getattr(self._api, action, None)
        if method is None:
            raise HuckleberryClientError(f"Action {action} is not available")

        try:
            return await method(**kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            raise HuckleberryTransportError(str(exc)) from exc

    async def _delete_interval_document(
        self,
        *,
        action_name: str,
        collection_name: str,
        child_uid: str,
        interval_id: str,
    ) -> None:
        if self._api is None:
            raise HuckleberryClientError("authenticate must be called before actions")

        cleaned_interval_id = interval_id.strip()
        if not cleaned_interval_id:
            raise HuckleberryClientError("interval_id is required")

        firestore_getter = getattr(self._api, "_get_firestore_client", None)
        if not callable(firestore_getter):
            raise HuckleberryClientError(
                f"{action_name} is unavailable: no Firestore access in upstream API"
            )

        action = getattr(self._api, action_name, None)

        try:
            firestore_client = await self._maybe_await(firestore_getter())
            interval_ref = (
                firestore_client.collection(collection_name)
                .document(child_uid)
                .collection("intervals")
                .document(cleaned_interval_id)
            )
            snapshot = await self._maybe_await(interval_ref.get())
            if not bool(getattr(snapshot, "exists", False)):
                raise HuckleberryClientError(
                    f"Interval {cleaned_interval_id} was not found"
                )

            payload = self._to_dict(snapshot.to_dict())
            await self._record_deleted_interval(
                collection_name=collection_name,
                child_uid=child_uid,
                interval_id=cleaned_interval_id,
                payload=payload,
            )

            if callable(action):
                await action(child_uid, interval_id=cleaned_interval_id)
                return

            await self._maybe_await(interval_ref.delete())
        except HuckleberryClientError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            raise HuckleberryTransportError(str(exc)) from exc

    async def _record_deleted_interval(
        self,
        *,
        collection_name: str,
        child_uid: str,
        interval_id: str,
        payload: dict[str, Any],
    ) -> None:
        store = self._require_delete_log_storage()
        entry = await store.async_append_entry(
            collection_name=collection_name,
            child_uid=child_uid,
            interval_id=interval_id,
            payload=payload,
        )
        _LOGGER.debug(
            "Stored delete backup %s for %s/%s",
            entry.get("log_id"),
            collection_name,
            interval_id,
        )

    def _require_delete_log_storage(self) -> HuckleberryDeleteLogStorage:
        storage = self._get_delete_log_storage()
        if storage is None:
            raise HuckleberryClientError("Delete log storage is unavailable")
        return storage

    def _get_delete_log_storage(self) -> HuckleberryDeleteLogStorage | None:
        if self._hass is None:
            return None
        if self._delete_log_storage is None:
            self._delete_log_storage = HuckleberryDeleteLogStorage(
                self._hass,
                self._entry_id,
            )
        return self._delete_log_storage

    async def _build_api(self) -> Any:
        from huckleberry_api import HuckleberryAPI

        aiohttp_client = importlib.import_module("homeassistant.helpers.aiohttp_client")
        session_factory = aiohttp_client.async_get_clientsession
        session = session_factory(self._hass)
        return HuckleberryAPI(
            email=self._email,
            password=self._password,
            timezone=self._timezone,
            websession=session,
        )

    @staticmethod
    async def _maybe_await(value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _iter_entries(value: Any) -> Iterable[Any]:
        if value is None:
            return []
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
            return value
        return [value]

    def _extract_children(self, payload: dict[str, Any]) -> list[ChildProfile]:
        children: list[ChildProfile] = []

        def _append_child(uid: str, name: str) -> None:
            for index, child in enumerate(children):
                if child.uid != uid:
                    continue
                if child.name.startswith("Child ") and not name.startswith("Child "):
                    children[index] = ChildProfile(uid=uid, name=name)
                return

            children.append(ChildProfile(uid=uid, name=name))

        child_list = payload.get("childList")
        if isinstance(child_list, list):
            for index, entry in enumerate(child_list):
                row = self._to_dict(entry)
                uid = self._best_uid(row)
                if not uid:
                    continue
                name = self._best_name(row) or f"Child {index + 1}"
                _append_child(uid, name)

        direct_children = payload.get("children")
        if isinstance(direct_children, list):
            for index, entry in enumerate(direct_children):
                row = self._to_dict(entry)
                uid = self._best_uid(row)
                if not uid:
                    continue
                name = self._best_name(row) or f"Child {index + 1}"
                _append_child(uid, name)

        hb_children = payload.get("hbChilds")
        if isinstance(hb_children, Mapping):
            for index, child_uid in enumerate(hb_children):
                if not isinstance(child_uid, str) or not child_uid.strip():
                    continue
                _append_child(child_uid, f"Child {index + 1}")

        for key in ("child", "currentChild", "selectedChild"):
            row = self._to_dict(payload.get(key))
            uid = self._best_uid(row)
            if uid:
                name = self._best_name(row) or "Child"
                _append_child(uid, name)

        return children

    def _extract_child_uid_list(self, payload: dict[str, Any]) -> list[str]:
        uid_list: list[str] = []
        for key in ("childUids", "childrenUids", "children_ids"):
            values = payload.get(key)
            if not isinstance(values, list):
                continue
            for uid in values:
                if isinstance(uid, str) and uid.strip():
                    uid_list.append(uid)

        hb_children = payload.get("hbChilds")
        if isinstance(hb_children, Mapping):
            for child_uid in hb_children:
                if isinstance(child_uid, str) and child_uid.strip():
                    uid_list.append(child_uid)

        child_list = payload.get("childList")
        if isinstance(child_list, list):
            for child in child_list:
                row = self._to_dict(child)
                uid = self._best_uid(row)
                if uid:
                    uid_list.append(uid)

        last_child = payload.get("lastChild")
        if isinstance(last_child, str) and last_child.strip():
            uid_list.append(last_child)

        return list(dict.fromkeys(uid_list))

    @staticmethod
    def _to_dict(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            try:
                dumped = model_dump()
                if isinstance(dumped, Mapping):
                    return dict(dumped)
            except Exception:  # pylint: disable=broad-except
                return {}
        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            try:
                dumped = to_dict()
                if isinstance(dumped, Mapping):
                    return dict(dumped)
            except Exception:  # pylint: disable=broad-except
                return {}
        if hasattr(value, "__dict__"):
            return dict(vars(value))
        return {}

    @staticmethod
    def _best_uid(payload: dict[str, Any]) -> str | None:
        for key in ("uid", "id", "cid", "childUid", "child_id", "childId"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _best_name(payload: dict[str, Any]) -> str | None:
        for key in (
            "childsName",
            "name",
            "nickname",
            "firstName",
            "firstname",
            "childName",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _sleep_event_key(event: SleepEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("sleep-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            int(event.duration_seconds),
        )

    @staticmethod
    def _feed_event_key(event: FeedEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("feed-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            event.mode,
            event.amount,
            event.units,
        )

    @staticmethod
    def _diaper_event_key(event: DiaperEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("diaper-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            event.mode,
            event.pee_amount,
            event.poo_amount,
        )

    @staticmethod
    def _pump_event_key(event: PumpEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("pump-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            event.entry_mode,
            event.total_amount,
            event.units,
        )

    @staticmethod
    def _activity_event_key(event: ActivityEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("activity-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            event.mode,
            event.duration_seconds,
        )

    @staticmethod
    def _health_event_key(event: HealthEvent) -> tuple[Any, ...]:
        if event.source_id and not event.source_id.startswith("health-"):
            return ("id", event.source_id)
        return (
            "time",
            int(event.start.timestamp()),
            event.mode,
            event.weight,
            event.height,
            event.head,
            event.amount,
            event.units,
        )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None
