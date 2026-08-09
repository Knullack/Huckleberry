from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ChildProfile:
    uid: str
    name: str


@dataclass(slots=True)
class SleepTimer:
    active: bool
    paused: bool
    timer_start_time_ms: float | None
    timer_end_time_ms: float | None
    uuid: str | None


@dataclass(slots=True)
class SleepEvent:
    source_id: str
    start: datetime
    end: datetime
    duration_seconds: int
    offset_minutes: float | None
    end_offset_minutes: float | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FeedEvent:
    source_id: str
    start: datetime
    amount: float | None
    units: str | None
    mode: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DiaperEvent:
    source_id: str
    start: datetime
    mode: str | None
    pee_amount: float | None
    poo_amount: float | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PumpEvent:
    source_id: str
    start: datetime
    entry_mode: str | None
    left_amount: float | None
    right_amount: float | None
    total_amount: float | None
    units: str | None
    duration_seconds: float | None
    notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActivityEvent:
    source_id: str
    start: datetime
    mode: str | None
    duration_seconds: float | None
    notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class HealthEvent:
    source_id: str
    start: datetime
    mode: str | None
    weight: float | None
    height: float | None
    head: float | None
    weight_units: str | None
    height_units: str | None
    head_units: str | None
    amount: float | None
    units: str | None
    medication_name: str | None
    notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalyticsSnapshot:
    sleeping: bool = False
    sleep_paused: bool = False
    current_sleep_duration_seconds: int | None = None
    naps_today: int = 0
    day_sleep_seconds_today: int = 0
    night_sleep_seconds_today: int = 0
    average_wake_window_seconds: int | None = None
    average_feed_interval_seconds: int | None = None
    next_nap_at: datetime | None = None
    next_feed_at: datetime | None = None
    next_nap_overdue_seconds: int | None = None
    next_feed_overdue_seconds: int | None = None
    sleep_confidence: float = 0.0
    feed_confidence: float = 0.0


@dataclass(slots=True)
class ChildSnapshot:
    profile: ChildProfile
    timer: SleepTimer
    sleep_events: list[SleepEvent]
    feed_events: list[FeedEvent]
    diaper_events: list[DiaperEvent]
    pump_events: list[PumpEvent]
    activity_events: list[ActivityEvent]
    health_events: list[HealthEvent]
    analytics: AnalyticsSnapshot
