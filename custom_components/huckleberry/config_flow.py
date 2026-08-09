from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .api import (
    HuckleberryAuthenticationError,
    HuckleberryClient,
    HuckleberryClientError,
    HuckleberryTransportError,
)
from .const import (
    CONF_CHILD_NAMES,
    CONF_CHILDREN,
    CONF_ENABLE_REALTIME_LISTENERS,
    CONF_LOOKBACK_HOURS,
    CONF_NIGHT_END_HOUR,
    CONF_NIGHT_START_HOUR,
    CONF_PASSWORD,
    CONF_SESSION_HEARTBEAT_MINUTES,
    CONF_TIMEZONE,
    CONF_UPDATE_INTERVAL_SECONDS,
    DEFAULT_ENABLE_REALTIME_LISTENERS,
    DEFAULT_LOOKBACK_HOURS,
    DEFAULT_NIGHT_END_HOUR,
    DEFAULT_NIGHT_START_HOUR,
    DEFAULT_SESSION_HEARTBEAT_MINUTES,
    DEFAULT_TIMEZONE,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)
from .models import ChildProfile


class HuckleberryConfigFlow(  # type: ignore[call-arg]
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for Huckleberry."""

    VERSION = 1

    _user_input: dict[str, Any] | None = None
    _children: list[ChildProfile]
    _reauth_entry: config_entries.ConfigEntry | None

    def __init__(self) -> None:
        self._children = []
        self._reauth_entry = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            self._user_input = {
                CONF_EMAIL: email,
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_TIMEZONE: user_input[CONF_TIMEZONE],
            }

            client = HuckleberryClient(
                hass=self.hass,
                email=email,
                password=user_input[CONF_PASSWORD],
                timezone=user_input[CONF_TIMEZONE],
            )

            try:
                await client.authenticate()
                self._children = await client.discover_children()
            except HuckleberryAuthenticationError:
                errors["base"] = "invalid_auth"
            except HuckleberryTransportError:
                errors["base"] = "cannot_connect"
            except HuckleberryClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if not errors:
                if not self._children:
                    errors["base"] = "no_children"
                else:
                    return await self.async_step_select_children()

        timezone_default = self.hass.config.time_zone or DEFAULT_TIMEZONE
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_TIMEZONE, default=timezone_default): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_children(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        errors: dict[str, str] = {}

        child_map = {child.uid: child.name for child in self._children}
        default_children = list(child_map)

        if user_input is not None:
            selected = list(user_input[CONF_CHILDREN])
            if not selected:
                errors["base"] = "select_at_least_one_child"
            elif self._user_input is not None:
                await self.async_set_unique_id(self._user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()

                child_names = {
                    uid: child_map.get(uid, f"Child {uid[:6]}") for uid in selected
                }
                data = {
                    **self._user_input,
                    CONF_CHILDREN: selected,
                    CONF_CHILD_NAMES: child_names,
                }
                return self.async_create_entry(title="Huckleberry", data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_CHILDREN, default=default_children): cv.multi_select(
                    child_map
                )
            }
        )

        return self.async_show_form(
            step_id="select_children",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        email = entry_data.get(CONF_EMAIL)
        for entry in self._async_current_entries():
            if entry.data.get(CONF_EMAIL) == email:
                self._reauth_entry = entry
                break

        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if self._reauth_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}

        if user_input is not None:
            email = self._reauth_entry.data[CONF_EMAIL]
            timezone = user_input.get(
                CONF_TIMEZONE,
                self._reauth_entry.data[CONF_TIMEZONE],
            )
            password = user_input[CONF_PASSWORD]

            client = HuckleberryClient(
                hass=self.hass,
                email=email,
                password=password,
                timezone=timezone,
            )

            try:
                await client.authenticate()
            except HuckleberryAuthenticationError:
                errors["base"] = "invalid_auth"
            except HuckleberryTransportError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

            if not errors:
                data = dict(self._reauth_entry.data)
                data[CONF_PASSWORD] = password
                data[CONF_TIMEZONE] = timezone
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data=data,
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_TIMEZONE,
                    default=self._reauth_entry.data.get(
                        CONF_TIMEZONE,
                        DEFAULT_TIMEZONE,
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return HuckleberryOptionsFlow(config_entry)


class HuckleberryOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Huckleberry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        child_names = self._resolve_child_names()

        if user_input is not None:
            selected = list(user_input[CONF_CHILDREN])
            selected_names = {
                uid: child_names.get(uid, f"Child {uid[:6]}") for uid in selected
            }

            data = dict(user_input)
            data[CONF_CHILDREN] = selected
            data[CONF_CHILD_NAMES] = selected_names
            return self.async_create_entry(title="", data=data)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_CHILDREN,
                    default=self._config_entry.options.get(
                        CONF_CHILDREN,
                        self._config_entry.data.get(CONF_CHILDREN, list(child_names)),
                    ),
                ): cv.multi_select(child_names),
                vol.Required(
                    CONF_UPDATE_INTERVAL_SECONDS,
                    default=self._config_entry.options.get(
                        CONF_UPDATE_INTERVAL_SECONDS,
                        DEFAULT_UPDATE_INTERVAL_SECONDS,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                vol.Required(
                    CONF_LOOKBACK_HOURS,
                    default=self._config_entry.options.get(
                        CONF_LOOKBACK_HOURS,
                        DEFAULT_LOOKBACK_HOURS,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=12, max=720)),
                vol.Required(
                    CONF_NIGHT_START_HOUR,
                    default=self._config_entry.options.get(
                        CONF_NIGHT_START_HOUR,
                        DEFAULT_NIGHT_START_HOUR,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required(
                    CONF_NIGHT_END_HOUR,
                    default=self._config_entry.options.get(
                        CONF_NIGHT_END_HOUR,
                        DEFAULT_NIGHT_END_HOUR,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
                vol.Required(
                    CONF_ENABLE_REALTIME_LISTENERS,
                    default=self._config_entry.options.get(
                        CONF_ENABLE_REALTIME_LISTENERS,
                        DEFAULT_ENABLE_REALTIME_LISTENERS,
                    ),
                ): bool,
                vol.Required(
                    CONF_SESSION_HEARTBEAT_MINUTES,
                    default=self._config_entry.options.get(
                        CONF_SESSION_HEARTBEAT_MINUTES,
                        DEFAULT_SESSION_HEARTBEAT_MINUTES,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    def _resolve_child_names(self) -> dict[str, str]:
        names: dict[str, str] = {}

        data_names = self._config_entry.data.get(CONF_CHILD_NAMES, {})
        option_names = self._config_entry.options.get(CONF_CHILD_NAMES, {})
        if isinstance(data_names, dict):
            names.update({str(key): str(value) for key, value in data_names.items()})
        if isinstance(option_names, dict):
            names.update({str(key): str(value) for key, value in option_names.items()})

        if names:
            return names

        children = self._config_entry.data.get(CONF_CHILDREN, [])
        if isinstance(children, list):
            return {uid: f"Child {index + 1}" for index, uid in enumerate(children)}

        return {}
