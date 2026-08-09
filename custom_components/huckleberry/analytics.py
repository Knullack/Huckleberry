from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import StatisticsError, mean, median, pstdev

from .models import AnalyticsSnapshot, ChildSnapshot


def _in_night_window(hour: int, night_start_hour: int, night_end_hour: int) -> bool:
    if night_start_hour == night_end_hour:
        return True

    if night_start_hour < night_end_hour:
        return night_start_hour <= hour < night_end_hour

    return hour >= night_start_hour or hour < night_end_hour


def _confidence_from_series(values: list[int]) -> float:
    if len(values) < 2:
        return 0.25 if values else 0.0

    avg = mean(values)
    if avg <= 0:
        return 0.0

    try:
        variability = pstdev(values) / avg
    except StatisticsError:
        variability = 1.0

    sample_factor = min(1.0, len(values) / 21.0)
    variability_factor = max(0.0, 1.0 - variability)
    score = 0.2 + (0.5 * sample_factor) + (0.3 * variability_factor)
    return max(0.0, min(0.99, score))


def _resolve_next_prediction(
    *,
    last_event_time: datetime,
    interval_seconds: int,
    now: datetime,
) -> tuple[datetime | None, int | None]:
    prediction = last_event_time + timedelta(seconds=interval_seconds)
    overdue_seconds = int((now - prediction).total_seconds())

    if overdue_seconds <= 0:
        return prediction, None

    # If prediction is only slightly overdue, mark it as due now rather than past.
    if overdue_seconds <= 30 * 60:
        return now, overdue_seconds

    return None, overdue_seconds


def build_analytics(
    snapshot: ChildSnapshot,
    night_start_hour: int,
    night_end_hour: int,
    now: datetime,
) -> AnalyticsSnapshot:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    sleep_events = sorted(snapshot.sleep_events, key=lambda event: event.start)
    feed_events = sorted(snapshot.feed_events, key=lambda event: event.start)

    analytics = AnalyticsSnapshot(
        sleeping=snapshot.timer.active,
        sleep_paused=snapshot.timer.paused,
    )

    if snapshot.timer.active and snapshot.timer.timer_start_time_ms is not None:
        start_seconds = snapshot.timer.timer_start_time_ms / 1000.0
        elapsed = int(max(0.0, now.timestamp() - start_seconds))
        analytics.current_sleep_duration_seconds = elapsed

    wake_windows: list[int] = []
    for index in range(1, len(sleep_events)):
        previous_end = sleep_events[index - 1].end
        current_start = sleep_events[index].start
        wake_window = int((current_start - previous_end).total_seconds())
        if wake_window > 0:
            wake_windows.append(wake_window)

    if wake_windows:
        analytics.average_wake_window_seconds = int(median(wake_windows))

    feed_intervals: list[int] = []
    for index in range(1, len(feed_events)):
        interval = int(
            (
                feed_events[index].start - feed_events[index - 1].start
            ).total_seconds()
        )
        if interval > 0:
            feed_intervals.append(interval)

    if feed_intervals:
        analytics.average_feed_interval_seconds = int(median(feed_intervals))

    local_today = now.date()
    for event in sleep_events:
        if event.start.date() != local_today:
            continue
        if _in_night_window(event.start.hour, night_start_hour, night_end_hour):
            analytics.night_sleep_seconds_today += event.duration_seconds
        else:
            analytics.day_sleep_seconds_today += event.duration_seconds
            analytics.naps_today += 1

    if sleep_events and analytics.average_wake_window_seconds is not None:
        last_sleep = sleep_events[-1]
        (
            analytics.next_nap_at,
            analytics.next_nap_overdue_seconds,
        ) = _resolve_next_prediction(
            last_event_time=last_sleep.end,
            interval_seconds=analytics.average_wake_window_seconds,
            now=now,
        )

    if feed_events and analytics.average_feed_interval_seconds is not None:
        last_feed = feed_events[-1]
        (
            analytics.next_feed_at,
            analytics.next_feed_overdue_seconds,
        ) = _resolve_next_prediction(
            last_event_time=last_feed.start,
            interval_seconds=analytics.average_feed_interval_seconds,
            now=now,
        )

    analytics.sleep_confidence = _confidence_from_series(wake_windows)
    analytics.feed_confidence = _confidence_from_series(feed_intervals)

    return analytics
