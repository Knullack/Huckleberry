from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _install_module_stubs() -> None:
    """Install lightweight import stubs used by unit tests.

    The tests in this repository validate pure helpers and analytics logic.
    They should not require a full Home Assistant runtime to import modules.
    """

    if "voluptuous" not in sys.modules:
        vol = ModuleType("voluptuous")

        def _schema(value: Any, *args: Any, **kwargs: Any) -> Any:
            return value

        def _required(value: Any, *args: Any, **kwargs: Any) -> Any:
            return value

        def _all(*validators: Any) -> Any:
            return validators[0] if validators else None

        def _coerce(target_type: Any) -> Any:
            return target_type

        def _range(*args: Any, **kwargs: Any) -> Any:
            def _validator(value: Any) -> Any:
                return value

            return _validator

        vol.Schema = _schema  # type: ignore[attr-defined]
        vol.Required = _required  # type: ignore[attr-defined]
        vol.All = _all  # type: ignore[attr-defined]
        vol.Coerce = _coerce  # type: ignore[attr-defined]
        vol.Range = _range  # type: ignore[attr-defined]
        sys.modules["voluptuous"] = vol

    if "homeassistant" not in sys.modules:
        homeassistant = ModuleType("homeassistant")
        config_entries = ModuleType("homeassistant.config_entries")
        const = ModuleType("homeassistant.const")
        core = ModuleType("homeassistant.core")
        exceptions = ModuleType("homeassistant.exceptions")
        helpers = ModuleType("homeassistant.helpers")
        config_validation = ModuleType("homeassistant.helpers.config_validation")
        update_coordinator = ModuleType("homeassistant.helpers.update_coordinator")
        util = ModuleType("homeassistant.util")
        util_dt = ModuleType("homeassistant.util.dt")

        class ConfigEntry:  # noqa: D401
            """Minimal config entry stub."""

        class Platform(StrEnum):
            """Minimal platform enum stub."""

            SENSOR = "sensor"
            BUTTON = "button"
            DATETIME = "datetime"
            NUMBER = "number"
            SELECT = "select"
            SWITCH = "switch"
            TEXT = "text"

        class HomeAssistant:  # noqa: D401
            """Minimal Home Assistant stub."""

        class ServiceCall:  # noqa: D401
            """Minimal service call stub."""

        class ConfigEntryAuthFailed(Exception):
            """Config entry auth failure."""

        class ConfigEntryNotReady(Exception):
            """Config entry not ready."""

        class HomeAssistantError(Exception):
            """Home Assistant base error."""

        class UpdateFailed(Exception):
            """Coordinator update failure."""

        class DataUpdateCoordinator:  # noqa: D401
            """Minimal DataUpdateCoordinator stub."""

            @classmethod
            def __class_getitem__(cls, item: Any) -> type[DataUpdateCoordinator]:
                return cls

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.data: dict[str, Any] | None = None
                self.name = kwargs.get("name", "")
                self.last_update_success = True
                self.last_exception: Exception | None = None

            async def async_refresh(self) -> None:
                return None

            async def async_config_entry_first_refresh(self) -> None:
                return None

        def _now() -> datetime:
            return datetime.now(tz=UTC)

        def _cv_string(value: str) -> str:
            return value

        config_entries.ConfigEntry = ConfigEntry  # type: ignore[attr-defined]
        const.CONF_EMAIL = "email"  # type: ignore[attr-defined]
        const.Platform = Platform  # type: ignore[attr-defined]
        core.HomeAssistant = HomeAssistant  # type: ignore[attr-defined]
        core.ServiceCall = ServiceCall  # type: ignore[attr-defined]
        exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed  # type: ignore[attr-defined]
        exceptions.ConfigEntryNotReady = ConfigEntryNotReady  # type: ignore[attr-defined]
        exceptions.HomeAssistantError = HomeAssistantError  # type: ignore[attr-defined]
        config_validation.string = _cv_string  # type: ignore[attr-defined]
        update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator  # type: ignore[attr-defined]
        update_coordinator.UpdateFailed = UpdateFailed  # type: ignore[attr-defined]
        util_dt.now = _now  # type: ignore[attr-defined]

        helpers.__path__ = []
        helpers.config_validation = config_validation  # type: ignore[attr-defined]
        helpers.update_coordinator = update_coordinator  # type: ignore[attr-defined]
        util.dt = util_dt  # type: ignore[attr-defined]

        sys.modules["homeassistant"] = homeassistant
        sys.modules["homeassistant.config_entries"] = config_entries
        sys.modules["homeassistant.const"] = const
        sys.modules["homeassistant.core"] = core
        sys.modules["homeassistant.exceptions"] = exceptions
        sys.modules["homeassistant.helpers"] = helpers
        sys.modules["homeassistant.helpers.config_validation"] = config_validation
        sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
        sys.modules["homeassistant.util"] = util
        sys.modules["homeassistant.util.dt"] = util_dt


_install_module_stubs()


@pytest.fixture
def fixtures_path() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_sleep_timer(fixtures_path: Path) -> dict[str, object]:
    with (fixtures_path / "sample_sleep_timer.json").open(
        "r",
        encoding="utf-8",
    ) as handle:
        return json.load(handle)
