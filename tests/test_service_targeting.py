from __future__ import annotations

import unittest

import conftest  # noqa: F401
from homeassistant.exceptions import HomeAssistantError

from custom_components import huckleberry as huckleberry_integration


class TestServiceTargeting(unittest.TestCase):
    def test_resolve_target_uses_single_child_by_default(self) -> None:
        targets = {"uid-1": object()}
        names = {"uid-1": "Child One"}

        resolved = huckleberry_integration._resolve_target_child_uid(
            child_uid=None,
            child_name=None,
            targets=targets,
            child_names=names,
        )

        self.assertEqual(resolved, "uid-1")


    def test_resolve_target_uses_child_name_case_insensitive(self) -> None:
        targets = {"uid-1": object(), "uid-2": object()}
        names = {"uid-1": "Child One", "uid-2": "Milo"}

        resolved = huckleberry_integration._resolve_target_child_uid(
            child_uid=None,
            child_name="child one",
            targets=targets,
            child_names=names,
        )

        self.assertEqual(resolved, "uid-1")


    def test_resolve_target_rejects_ambiguous_name(self) -> None:
        targets = {"uid-1": object(), "uid-2": object()}
        names = {"uid-1": "Baby", "uid-2": "baby"}

        with self.assertRaisesRegex(HomeAssistantError, "Multiple children share"):
            huckleberry_integration._resolve_target_child_uid(
                child_uid=None,
                child_name="Baby",
                targets=targets,
                child_names=names,
            )


    def test_resolve_target_rejects_unknown_name(self) -> None:
        targets = {"uid-1": object(), "uid-2": object()}
        names = {"uid-1": "Child One", "uid-2": "Milo"}

        with self.assertRaisesRegex(HomeAssistantError, "Available children"):
            huckleberry_integration._resolve_target_child_uid(
                child_uid=None,
                child_name="Nope",
                targets=targets,
                child_names=names,
            )


    def test_resolve_target_requires_name_or_uid_when_multiple(self) -> None:
        targets = {"uid-1": object(), "uid-2": object()}
        names = {"uid-1": "Child One", "uid-2": "Milo"}

        with self.assertRaisesRegex(
            HomeAssistantError,
            "Provide child_name or child_uid",
        ):
            huckleberry_integration._resolve_target_child_uid(
                child_uid=None,
                child_name=None,
                targets=targets,
                child_names=names,
            )


    def test_resolve_target_rejects_mismatched_uid_name_pair(self) -> None:
        targets = {"uid-1": object(), "uid-2": object()}
        names = {"uid-1": "Child One", "uid-2": "Milo"}

        with self.assertRaisesRegex(HomeAssistantError, "does not match"):
            huckleberry_integration._resolve_target_child_uid(
                child_uid="uid-1",
                child_name="Milo",
                targets=targets,
                child_names=names,
            )
