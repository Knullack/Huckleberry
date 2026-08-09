from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

import conftest  # noqa: F401

from custom_components.huckleberry.analytics import build_analytics
from custom_components.huckleberry.models import (
    AnalyticsSnapshot,
    ChildProfile,
    ChildSnapshot,
    DiaperEvent,
    FeedEvent,
    SleepEvent,
    SleepTimer,
)


class TestAnalytics(unittest.TestCase):
    def test_build_analytics_calculates_core_fields(self) -> None:
        now = datetime(2026, 8, 8, 18, 0, 0, tzinfo=UTC)

        sleep_events = [
            SleepEvent(
                source_id="s1",
                start=now - timedelta(hours=9),
                end=now - timedelta(hours=8, minutes=20),
                duration_seconds=40 * 60,
                offset_minutes=0,
                end_offset_minutes=0,
            ),
            SleepEvent(
                source_id="s2",
                start=now - timedelta(hours=6),
                end=now - timedelta(hours=5, minutes=20),
                duration_seconds=40 * 60,
                offset_minutes=0,
                end_offset_minutes=0,
            ),
            SleepEvent(
                source_id="s3",
                start=now - timedelta(hours=3),
                end=now - timedelta(hours=2, minutes=20),
                duration_seconds=40 * 60,
                offset_minutes=0,
                end_offset_minutes=0,
            ),
        ]

        feed_events = [
            FeedEvent(
                source_id="f1",
                start=now - timedelta(hours=7),
                amount=4.5,
                units="oz",
                mode="bottle",
            ),
            FeedEvent(
                source_id="f2",
                start=now - timedelta(hours=4, minutes=20),
                amount=5.0,
                units="oz",
                mode="bottle",
            ),
            FeedEvent(
                source_id="f3",
                start=now - timedelta(hours=1, minutes=50),
                amount=4.0,
                units="oz",
                mode="bottle",
            ),
        ]

        snapshot = ChildSnapshot(
            profile=ChildProfile(uid="child-1", name="Test Child"),
            timer=SleepTimer(
                active=True,
                paused=False,
                timer_start_time_ms=(now - timedelta(minutes=35)).timestamp() * 1000,
                timer_end_time_ms=None,
                uuid="timer-1",
            ),
            sleep_events=sleep_events,
            feed_events=feed_events,
            diaper_events=[
                DiaperEvent(
                    source_id="d1",
                    start=now - timedelta(hours=2),
                    mode="wet",
                    pee_amount=100.0,
                    poo_amount=None,
                )
            ],
            pump_events=[],
            activity_events=[],
            health_events=[],
            analytics=AnalyticsSnapshot(),
        )

        analytics = build_analytics(
            snapshot,
            night_start_hour=19,
            night_end_hour=7,
            now=now,
        )

        self.assertTrue(analytics.sleeping)
        self.assertIsNotNone(analytics.current_sleep_duration_seconds)
        if analytics.current_sleep_duration_seconds is not None:
            self.assertGreaterEqual(analytics.current_sleep_duration_seconds, 30 * 60)
            self.assertLessEqual(analytics.current_sleep_duration_seconds, 40 * 60)
        self.assertIsNotNone(analytics.average_wake_window_seconds)
        self.assertIsNotNone(analytics.average_feed_interval_seconds)
        self.assertIsNotNone(analytics.next_nap_at)
        self.assertIsNotNone(analytics.next_feed_at)
        self.assertGreaterEqual(analytics.sleep_confidence, 0.0)
        self.assertLessEqual(analytics.sleep_confidence, 1.0)
        self.assertGreaterEqual(analytics.feed_confidence, 0.0)
        self.assertLessEqual(analytics.feed_confidence, 1.0)

    def test_build_analytics_hides_stale_next_nap_prediction(self) -> None:
        now = datetime(2026, 8, 8, 18, 0, 0, tzinfo=UTC)

        sleep_events = [
            SleepEvent(
                source_id="s1",
                start=now - timedelta(hours=10),
                end=now - timedelta(hours=9, minutes=30),
                duration_seconds=30 * 60,
                offset_minutes=0,
                end_offset_minutes=0,
            ),
            SleepEvent(
                source_id="s2",
                start=now - timedelta(hours=9),
                end=now - timedelta(hours=8, minutes=30),
                duration_seconds=30 * 60,
                offset_minutes=0,
                end_offset_minutes=0,
            ),
        ]

        snapshot = ChildSnapshot(
            profile=ChildProfile(uid="child-1", name="Test Child"),
            timer=SleepTimer(
                active=False,
                paused=False,
                timer_start_time_ms=None,
                timer_end_time_ms=None,
                uuid="timer-1",
            ),
            sleep_events=sleep_events,
            feed_events=[],
            diaper_events=[],
            pump_events=[],
            activity_events=[],
            health_events=[],
            analytics=AnalyticsSnapshot(),
        )

        analytics = build_analytics(
            snapshot,
            night_start_hour=19,
            night_end_hour=7,
            now=now,
        )

        self.assertIsNone(analytics.next_nap_at)
        self.assertIsNotNone(analytics.next_nap_overdue_seconds)
        if analytics.next_nap_overdue_seconds is not None:
            self.assertGreater(analytics.next_nap_overdue_seconds, 0)
