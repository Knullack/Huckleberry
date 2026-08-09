from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN


class HuckleberryStorage:
    """Persistent storage helper for normalized integration history."""

    _VERSION = 1

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            self._VERSION,
            f"{DOMAIN}_{entry_id}_history",
        )

    async def async_load(self) -> dict[str, Any]:
        loaded = await self._store.async_load()
        if loaded is None:
            return {"children": {}, "sync": {}}
        return loaded

    async def async_save(self, data: dict[str, Any]) -> None:
        await self._store.async_save(data)
