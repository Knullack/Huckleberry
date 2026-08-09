from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

TO_REDACT = {
    "email",
    "password",
    "token",
    "refresh_token",
    "access_token",
    "children",
    "child_names",
    "child_uid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    data = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "name": coordinator.name,
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "children_count": len(coordinator.data or {}),
            "managed_children": [
                {
                    "name": snapshot.profile.name,
                    "sleep_events": len(snapshot.sleep_events),
                    "feed_events": len(snapshot.feed_events),
                    "diaper_events": len(snapshot.diaper_events),
                    "pump_events": len(snapshot.pump_events),
                    "activity_events": len(snapshot.activity_events),
                    "health_events": len(snapshot.health_events),
                    "sleeping": snapshot.analytics.sleeping,
                }
                for snapshot in (coordinator.data or {}).values()
            ],
        },
    }

    return async_redact_data(data, TO_REDACT)
