"""Config Flow für Smart Heating Advisor."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_OUTDOOR_TEMP,
    CONF_INDOOR_TEMPS,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    CONF_INDOOR_TEMP_LABEL,
    CONF_WINDOW_LABEL,
)


def _build_schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(
            CONF_OUTDOOR_TEMP,
            default=defaults.get(CONF_OUTDOOR_TEMP)
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        vol.Optional(
            CONF_INDOOR_TEMP_LABEL,
            default=defaults.get(CONF_INDOOR_TEMP_LABEL, "")
        ): selector.LabelSelector(),
        vol.Optional(
            CONF_INDOOR_TEMPS,
            default=defaults.get(CONF_INDOOR_TEMPS, [])
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="sensor",
                device_class="temperature",
                multiple=True,
            )
        ),
        vol.Optional(
            CONF_WINDOW_LABEL,
            default=defaults.get(CONF_WINDOW_LABEL, "")
        ): selector.LabelSelector(),
        vol.Optional(
            CONF_WINDOW_SENSORS,
            default=defaults.get(CONF_WINDOW_SENSORS, [])
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain="binary_sensor",
                multiple=True,
            )
        ),
        vol.Required(
            CONF_WEATHER_ENTITY,
            default=defaults.get(CONF_WEATHER_ENTITY)
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="weather")
        ),
    })


class SmartHeatingAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            outdoor = user_input.get(CONF_OUTDOOR_TEMP)
            if not outdoor or not self.hass.states.get(outdoor):
                errors[CONF_OUTDOOR_TEMP] = "sensor_not_found"
            else:
                return self.async_create_entry(
                    title="Smart Heating Advisor",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema({}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartHeatingAdvisorOptionsFlow(config_entry)


class SmartHeatingAdvisorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
        )
