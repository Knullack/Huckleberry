from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, TypeVar, cast
from uuid import uuid4

from homeassistant.core import HomeAssistant

from .const import DOMAIN

StoredDataT = TypeVar("StoredDataT")


class _StoreProtocol(Protocol[StoredDataT]):
    async def async_load(self) -> StoredDataT | None: ...

    async def async_save(self, data: StoredDataT) -> None: ...


try:
    from homeassistant.helpers.storage import Store as _HomeAssistantStore
except ModuleNotFoundError:  # pragma: no cover - test stub compatibility
    _HomeAssistantStore = None


class _FallbackStore[StoredDataT]:
    """Fallback in-memory Store for unit tests without Home Assistant."""

    def __init__(self, hass: HomeAssistant, version: int, key: str) -> None:
        del hass, version, key
        self._data: StoredDataT | None = None

    async def async_load(self) -> StoredDataT | None:
        return self._data

    async def async_save(self, data: StoredDataT) -> None:
        self._data = data


def _make_store(
    hass: HomeAssistant,
    version: int,
    key: str,
) -> _StoreProtocol[dict[str, Any]]:
    if _HomeAssistantStore is None:
        return _FallbackStore(hass, version, key)
    return cast(
        _StoreProtocol[dict[str, Any]],
        _HomeAssistantStore(hass, version, key),
    )


class HuckleberryStorage:
    """Persistent storage helper for normalized integration history."""

    _VERSION = 1

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: _StoreProtocol[dict[str, Any]] = _make_store(
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


class HuckleberryDeleteLogStorage:
    """Persistent 30-day delete audit storage."""

    _VERSION = 1
    _RETENTION_DAYS = 30

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: _StoreProtocol[dict[str, Any]] = _make_store(
            hass,
            self._VERSION,
            f"{DOMAIN}_{entry_id}_deleted_intervals",
        )

    async def async_append_entry(
        self,
        *,
        collection_name: str,
        child_uid: str,
        interval_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = await self._load_data()
        now = datetime.now(tz=UTC)
        entries = self._pruned_entries(data.get("entries", []), now)

        log_id = f"{int(now.timestamp() * 1000)}-{uuid4().hex[:12]}"
        expires_at = now + timedelta(days=self._RETENTION_DAYS)
        entry = {
            "log_id": log_id,
            "deleted_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "collection": collection_name,
            "child_uid": child_uid,
            "interval_id": interval_id,
            "payload": self._to_json_safe(payload),
        }
        entries.append(entry)

        await self._store.async_save(
            {
                "retention_days": self._RETENTION_DAYS,
                "entries": entries,
            }
        )
        return entry

    async def async_list_entries(
        self,
        *,
        child_uid: str | None = None,
        collection_name: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        data = await self._load_data()
        now = datetime.now(tz=UTC)
        entries = self._pruned_entries(data.get("entries", []), now)

        if entries != data.get("entries", []):
            await self._store.async_save(
                {
                    "retention_days": self._RETENTION_DAYS,
                    "entries": entries,
                }
            )

        filtered = [
            entry
            for entry in entries
            if (child_uid is None or entry.get("child_uid") == child_uid)
            and (collection_name is None or entry.get("collection") == collection_name)
        ]
        filtered.sort(key=lambda row: str(row.get("deleted_at", "")), reverse=True)
        bounded_limit = max(1, min(500, int(limit)))
        return filtered[:bounded_limit]

    async def async_get_entry(self, log_id: str) -> dict[str, Any] | None:
        entries = await self.async_list_entries(limit=500)
        for entry in entries:
            if str(entry.get("log_id")) == log_id:
                return entry
        return None

    @staticmethod
    def _to_json_safe(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC).isoformat()
            return value.astimezone(UTC).isoformat()
        if isinstance(value, Mapping):
            return {
                str(key): HuckleberryDeleteLogStorage._to_json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [HuckleberryDeleteLogStorage._to_json_safe(item) for item in value]
        return str(value)

    async def _load_data(self) -> dict[str, Any]:
        loaded = await self._store.async_load()
        if not isinstance(loaded, dict):
            return {"retention_days": self._RETENTION_DAYS, "entries": []}
        return {
            "retention_days": self._RETENTION_DAYS,
            "entries": loaded.get("entries", []),
        }

    @staticmethod
    def _pruned_entries(
        entries: Any,
        now: datetime,
    ) -> list[dict[str, Any]]:
        if not isinstance(entries, list):
            return []

        pruned: list[dict[str, Any]] = []
        for row in entries:
            if not isinstance(row, dict):
                continue
            expires_text = row.get("expires_at")
            if not isinstance(expires_text, str):
                continue
            try:
                expires_at = datetime.fromisoformat(expires_text)
            except ValueError:
                continue

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)

            if expires_at > now:
                pruned.append(row)

        return pruned
