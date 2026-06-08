"""Config Flow fuer Smart Heating Advisor."""
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
)


class SmartHeatingAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow - nur noch Sensor-Auswahl, Schwellen im Geraet."""

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

        schema = vol.Schema({
            vol.Required(CONF_OUTDOOR_TEMP): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(CONF_INDOOR_TEMPS): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="temperature",
                    multiple=True,
                )
            ),
            vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_WINDOW_SENSORS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    multiple=True,
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "note": "Schwellwerte koennen nach der Einrichtung direkt im Geraet angepasst werden."
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartHeatingAdvisorOptionsFlow(config_entry)


class SmartHeatingAdvisorOptionsFlow(config_entries.OptionsFlow):
    """Options Flow - nur Sensoren aenderbar."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        current = self._config_entry.data

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Required(
                CONF_OUTDOOR_TEMP, default=current.get(CONF_OUTDOOR_TEMP)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Required(
                CONF_INDOOR_TEMPS, default=current.get(CONF_INDOOR_TEMPS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="temperature", multiple=True
                )
            ),
            vol.Required(
                CONF_WEATHER_ENTITY, default=current.get(CONF_WEATHER_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(
                CONF_WINDOW_SENSORS, default=current.get(CONF_WINDOW_SENSORS, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    multiple=True,
                )
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
