from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import conftest  # noqa: F401

from custom_components.huckleberry.api import HuckleberryClient
from custom_components.huckleberry.coordinator import (
    HuckleberryDataUpdateCoordinator,
    _optional_bool,
    _required_service_datetime,
    _validated_foods,
)


@dataclass
class _ModelDumpStub:
    uid: str
    name: str

    def model_dump(self) -> dict[str, str]:
        return {"uid": self.uid, "name": self.name}


@dataclass
class _ToDictStub:
    uid: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid}


@dataclass
class _ConfigEntryStub:
    entry_id: str
    data: dict[str, Any]
    options: dict[str, Any]


class _FakeAPI:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    async def list_pump_intervals(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_pump_intervals",
                (child_uid, start_time, end_time),
                {},
            )
        )
        return [
            {
                "id": "pump-1",
                "start": start_time.timestamp(),
                "entryMode": "leftright",
                "leftAmount": 45.0,
                "rightAmount": 55.0,
                "units": "ml",
                "duration": 600,
            }
        ]

    async def list_activity_intervals(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_activity_intervals",
                (child_uid, start_time, end_time),
                {},
            )
        )
        return [
            {
                "id": "activity-1",
                "start": start_time.timestamp(),
                "mode": "bath",
                "duration": 300,
                "notes": "Quick bath",
            }
        ]

    async def list_health_entries(
        self,
        child_uid: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_health_entries",
                (child_uid, start_time, end_time),
                {},
            )
        )
        return [
            {
                "id": "growth-1",
                "start": start_time.timestamp(),
                "mode": "growth",
                "weight": 8.2,
                "weightUnits": "kg",
            },
            {
                "id": "temp-1",
                "start": end_time.timestamp(),
                "mode": "temperature",
                "amount": 37.1,
                "units": "C",
            },
        ]

    async def get_latest_growth(self, child_uid: str) -> dict[str, Any]:
        self.calls.append(("get_latest_growth", (child_uid,), {}))
        return {
            "id": "growth-latest",
            "start": 1_725_000_000,
            "mode": "growth",
            "weight": 8.4,
            "weightUnits": "kg",
        }

    async def list_solids_curated_foods(self) -> list[dict[str, Any]]:
        self.calls.append(("list_solids_curated_foods", (), {}))
        return [{"id": "curated-1", "name": "Avocado"}]

    async def list_solids_custom_foods(
        self,
        child_uid: str,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "list_solids_custom_foods",
                (child_uid,),
                {"include_archived": include_archived},
            )
        )
        return [{"id": "custom-1", "name": "Rice"}]

    async def create_solids_custom_food(
        self,
        child_uid: str,
        name: str,
        image: str = "",
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "create_solids_custom_food",
                (child_uid,),
                {"name": name, "image": image},
            )
        )
        return {"id": "custom-2", "name": name, "image": image}

    async def ensure_session(self) -> None:
        self.calls.append(("ensure_session", (), {}))


def _build_client() -> HuckleberryClient:
    return HuckleberryClient(
        hass=None,
        email="user@example.com",
        password="secret",
        timezone="UTC",
    )


class TestApiHelpers(unittest.TestCase):
    def test_to_dict_supports_mapping_and_model_dump(self) -> None:
        mapping = {"uid": "abc"}
        dumped = HuckleberryClient._to_dict(mapping)
        self.assertEqual(dumped, {"uid": "abc"})

        model = _ModelDumpStub(uid="child-1", name="Alex")
        dumped_model = HuckleberryClient._to_dict(model)
        self.assertEqual(dumped_model["uid"], "child-1")

        to_dict_model = _ToDictStub(uid="child-2")
        dumped_to_dict = HuckleberryClient._to_dict(to_dict_model)
        self.assertEqual(dumped_to_dict["uid"], "child-2")

    def test_optional_parsers(self) -> None:
        self.assertEqual(HuckleberryClient._optional_float("3.14"), 3.14)
        self.assertIsNone(HuckleberryClient._optional_float(None))
        self.assertIsNone(HuckleberryClient._optional_float("bad"))

        self.assertEqual(HuckleberryClient._optional_str("value"), "value")
        self.assertIsNone(HuckleberryClient._optional_str("   "))
        self.assertIsNone(HuckleberryClient._optional_str(None))

    def test_extract_children_supports_child_list_and_hb_childs(self) -> None:
        client = _build_client()
        payload = {
            "childList": [
                {"cid": "child-a", "nickname": "Ava"},
                {"cid": "child-b"},
            ],
            "hbChilds": {
                "child-a": {"addedAt": "1700000000"},
                "child-c": {"addedAt": "1700000100"},
            },
        }

        children = client._extract_children(payload)
        by_uid = {child.uid: child.name for child in children}

        self.assertEqual(by_uid["child-a"], "Ava")
        self.assertIn("child-b", by_uid)
        self.assertIn("child-c", by_uid)

    def test_extract_child_uid_list_includes_known_user_fields(self) -> None:
        client = _build_client()
        payload = {
            "childUids": ["child-a"],
            "childList": [{"cid": "child-b"}],
            "hbChilds": {"child-c": {"addedAt": "1700000200"}},
            "lastChild": "child-d",
        }

        self.assertEqual(
            client._extract_child_uid_list(payload),
            [
                "child-a",
                "child-c",
                "child-b",
                "child-d",
            ],
        )

    def test_coordinator_payload_helpers(self) -> None:
        parsed_dt = _required_service_datetime("2026-08-08T12:00:00Z", "start_time")
        self.assertIsNotNone(parsed_dt.tzinfo)

        self.assertTrue(_optional_bool(True, "flag"))
        self.assertFalse(_optional_bool("false", "flag"))

        foods = _validated_foods(
            [
                {
                    "id": "curated-1",
                    "source": "curated",
                    "name": "Avocado",
                    "amount": "2 tsp",
                }
            ],
            "foods",
        )
        self.assertEqual(foods[0]["source"], "curated")

    def test_coordinator_food_helper_accepts_json(self) -> None:
        payload = (
            '[{"id":"custom-1","source":"custom","name":"Banana","amount":1.5}]'
        )
        foods = _validated_foods(payload, "foods")
        self.assertEqual(foods[0]["id"], "custom-1")

    def test_coordinator_child_names_falls_back_to_selected_children(self) -> None:
        config_entry = _ConfigEntryStub(
            entry_id="entry-1",
            data={
                "children": ["uid-a", "uid-b"],
            },
            options={},
        )

        coordinator = HuckleberryDataUpdateCoordinator(
            hass=None,
            config_entry=config_entry,
            client=None,
        )

        self.assertEqual(
            coordinator.child_names,
            {
                "uid-a": "Child 1",
                "uid-b": "Child 2",
            },
        )


class TestApiHelpersAsync(unittest.IsolatedAsyncioTestCase):
    async def test_wrapper_extended_read_methods_normalize_results(self) -> None:
        client = _build_client()
        fake_api = _FakeAPI()
        client._api = fake_api

        start_time = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
        end_time = datetime(2026, 8, 8, 13, 0, 0, tzinfo=UTC)

        pump_events = await client.list_pump_events("child-1", start_time, end_time)
        self.assertEqual(len(pump_events), 1)
        self.assertEqual(pump_events[0].total_amount, 100.0)
        self.assertEqual(pump_events[0].units, "ml")

        activity_events = await client.list_activity_events(
            "child-1",
            start_time,
            end_time,
        )
        self.assertEqual(len(activity_events), 1)
        self.assertEqual(activity_events[0].mode, "bath")

        health_events = await client.list_health_events(
            "child-1",
            start_time,
            end_time,
        )
        self.assertEqual(len(health_events), 2)
        self.assertEqual(health_events[0].mode, "growth")

        latest_growth = await client.get_latest_growth_event("child-1")
        self.assertIsNotNone(latest_growth)
        if latest_growth is not None:
            self.assertEqual(latest_growth.mode, "growth")
            self.assertEqual(latest_growth.weight, 8.4)

    async def test_wrapper_solids_and_session_methods(self) -> None:
        client = _build_client()
        fake_api = _FakeAPI()
        client._api = fake_api

        await client.ensure_session()

        curated = await client.list_solids_curated_foods()
        custom = await client.list_solids_custom_foods(
            "child-1",
            include_archived=True,
        )
        created = await client.create_solids_custom_food(
            "child-1",
            name="Oatmeal",
            image="food.png",
        )

        self.assertEqual(curated[0]["id"], "curated-1")
        self.assertEqual(custom[0]["id"], "custom-1")
        self.assertEqual(created["name"], "Oatmeal")
