from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)

try:
    from homeassistant.core import SupportsResponse
except ImportError:  # pragma: no cover - compatibility with older Home Assistant cores
    SupportsResponse = None

from .api import (
    HuckleberryAuthenticationError,
    HuckleberryClient,
    HuckleberryClientError,
    HuckleberryTransportError,
)
from .const import (
    ATTR_CHILD_NAME,
    ATTR_CHILD_UID,
    CONF_PASSWORD,
    CONF_TIMEZONE,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PLATFORMS,
    SERVICE_CREATE_SOLIDS_CUSTOM_FOOD,
    SERVICE_LIST_SOLIDS_CURATED_FOODS,
    SERVICE_LIST_SOLIDS_CUSTOM_FOODS,
    SERVICE_NAMES,
    SERVICE_START_SLEEP,
)
from .coordinator import HuckleberryDataUpdateCoordinator

SERVICES_WITH_OPTIONAL_CHILD_TARGET = {
    SERVICE_LIST_SOLIDS_CURATED_FOODS,
}

SERVICES_WITH_RESPONSE_PAYLOAD = {
    SERVICE_CREATE_SOLIDS_CUSTOM_FOOD,
    SERVICE_LIST_SOLIDS_CURATED_FOODS,
    SERVICE_LIST_SOLIDS_CUSTOM_FOODS,
}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up from yaml (unused for this integration)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Huckleberry from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = HuckleberryClient(
        hass=hass,
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        timezone=entry.data[CONF_TIMEZONE],
    )

    try:
        await client.authenticate()
    except HuckleberryAuthenticationError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except HuckleberryTransportError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    except HuckleberryClientError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    coordinator = HuckleberryDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=client,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    await coordinator.async_initialize_runtime_features()

    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is not None:
        coordinator: HuckleberryDataUpdateCoordinator = entry_data[DATA_COORDINATOR]
        await coordinator.async_shutdown_runtime_features()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        await _async_unregister_services(hass)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_START_SLEEP):
        return

    async def _service_handler(call: ServiceCall) -> dict[str, Any] | None:
        child_uid = _optional_service_text(
            call.data.get(ATTR_CHILD_UID),
            ATTR_CHILD_UID,
        )
        child_name = _optional_service_text(
            call.data.get(ATTR_CHILD_NAME),
            ATTR_CHILD_NAME,
        )

        service = call.service
        payload = {
            key: value
            for key, value in call.data.items()
            if key not in {ATTR_CHILD_UID, ATTR_CHILD_NAME}
        }

        targets = _available_service_targets(hass)
        child_names = _available_service_child_names(hass)

        if (
            call.service in SERVICES_WITH_OPTIONAL_CHILD_TARGET
            and child_uid is None
            and child_name is None
        ):
            if not targets:
                raise HomeAssistantError(
                    "No configured Huckleberry children were found"
                )
            child_uid = next(iter(targets.keys()))
        else:
            child_uid = _resolve_target_child_uid(
                child_uid=child_uid,
                child_name=child_name,
                targets=targets,
                child_names=child_names,
            )

        coordinator = targets.get(child_uid)
        if coordinator is None:
            raise HomeAssistantError(
                f"No configured entry manages child UID {child_uid}."
            )

        return await coordinator.async_execute_service(service, child_uid, payload)

    for service_name in SERVICE_NAMES:
        register_kwargs: dict[str, Any] = {}
        if SupportsResponse is not None:
            register_kwargs["supports_response"] = (
                SupportsResponse.OPTIONAL
                if service_name in SERVICES_WITH_RESPONSE_PAYLOAD
                else SupportsResponse.NONE
            )

        hass.services.async_register(
            DOMAIN,
            service_name,
            _service_handler,
            **register_kwargs,
        )


async def _async_unregister_services(hass: HomeAssistant) -> None:
    for service_name in SERVICE_NAMES:
        if hass.services.has_service(DOMAIN, service_name):
            hass.services.async_remove(DOMAIN, service_name)


def _available_service_targets(
    hass: HomeAssistant,
) -> dict[str, HuckleberryDataUpdateCoordinator]:
    targets: dict[str, HuckleberryDataUpdateCoordinator] = {}
    for data in hass.data.get(DOMAIN, {}).values():
        coordinator: HuckleberryDataUpdateCoordinator = data[DATA_COORDINATOR]
        for child_uid in coordinator.selected_children:
            if child_uid and child_uid not in targets:
                targets[child_uid] = coordinator
    return targets


def _available_service_child_names(hass: HomeAssistant) -> dict[str, str]:
    names: dict[str, str] = {}
    for data in hass.data.get(DOMAIN, {}).values():
        coordinator: HuckleberryDataUpdateCoordinator = data[DATA_COORDINATOR]
        known_names = coordinator.child_names
        for child_uid in coordinator.selected_children:
            if not child_uid or child_uid in names:
                continue
            names[child_uid] = known_names.get(child_uid, child_uid)
    return names


def _resolve_target_child_uid(
    *,
    child_uid: str | None,
    child_name: str | None,
    targets: Mapping[str, object],
    child_names: Mapping[str, str],
) -> str:
    if child_uid is not None:
        if child_uid not in targets:
            raise HomeAssistantError(
                f"No configured entry manages child UID {child_uid}."
            )

        if child_name is not None:
            resolved_name = child_names.get(child_uid, child_uid)
            if _normalized_name(child_name) != _normalized_name(resolved_name):
                raise HomeAssistantError(
                    "child_name does not match the provided child_uid"
                )
        return child_uid

    if child_name is not None:
        normalized = _normalized_name(child_name)
        matches = [
            uid
            for uid in targets
            if _normalized_name(child_names.get(uid, uid)) == normalized
        ]

        if not matches:
            available = _available_name_summary(targets, child_names)
            message = f"No configured child found with name '{child_name}'."
            if available:
                message = f"{message} Available children: {available}."
            raise HomeAssistantError(message)

        if len(matches) > 1:
            raise HomeAssistantError(
                "Multiple children share that child_name. "
                "Provide child_uid instead."
            )

        return matches[0]

    if not targets:
        raise HomeAssistantError("No configured Huckleberry children were found")

    if len(targets) > 1:
        available = _available_name_summary(targets, child_names)
        message = "Multiple children are configured. Provide child_name or child_uid."
        if available:
            message = f"{message} Available children: {available}."
        raise HomeAssistantError(message)

    return next(iter(targets.keys()))


def _available_name_summary(
    targets: Mapping[str, object],
    child_names: Mapping[str, str],
) -> str:
    values = {child_names.get(uid, uid) for uid in targets}
    return ", ".join(sorted(values))


def _normalized_name(value: str) -> str:
    return value.strip().casefold()


def _optional_service_text(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HomeAssistantError(f"{field_name} must be a string")
    cleaned = value.strip()
    return cleaned or None
