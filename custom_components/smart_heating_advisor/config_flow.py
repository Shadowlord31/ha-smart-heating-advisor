"""Config Flow fuer Smart Heating Advisor."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_OUTDOOR_TEMP,
    CONF_INDOOR_TEMPS,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    CONF_HEATING_THRESHOLD,
    CONF_SUMMER_MODE_DAYS,
    CONF_MIN_INDOOR_TEMP,
    DEFAULT_HEATING_THRESHOLD,
    DEFAULT_SUMMER_MODE_DAYS,
    DEFAULT_MIN_INDOOR_TEMP,
)


class SmartHeatingAdvisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow - Schritt 1: Sensoren auswaehlen."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Pflichtfeld pruefen
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
            ),  # Pflicht: wird fuer Gebaeude-Waermetraegheit benoetigt
            vol.Required(CONF_WEATHER_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="weather")
            ),
            vol.Optional(CONF_WINDOW_SENSORS, default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="binary_sensor",
                    device_class="window",
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_HEATING_THRESHOLD, default=DEFAULT_HEATING_THRESHOLD
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=25, step=0.5, unit_of_measurement="°C")
            ),
            vol.Optional(
                CONF_MIN_INDOOR_TEMP, default=DEFAULT_MIN_INDOOR_TEMP
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=24, step=0.5, unit_of_measurement="°C")
            ),
            vol.Optional(
                CONF_SUMMER_MODE_DAYS, default=DEFAULT_SUMMER_MODE_DAYS
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=7, step=1, unit_of_measurement="Tage")
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartHeatingAdvisorOptionsFlow(config_entry)


class SmartHeatingAdvisorOptionsFlow(config_entries.OptionsFlow):
    """Options Flow - Einstellungen nachtraeglich aendern."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
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
                    domain="binary_sensor", device_class="window", multiple=True
                )
            ),
            vol.Optional(
                CONF_HEATING_THRESHOLD,
                default=current.get(CONF_HEATING_THRESHOLD, DEFAULT_HEATING_THRESHOLD)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=5, max=25, step=0.5, unit_of_measurement="°C")
            ),
            vol.Optional(
                CONF_MIN_INDOOR_TEMP,
                default=current.get(CONF_MIN_INDOOR_TEMP, DEFAULT_MIN_INDOOR_TEMP)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=15, max=24, step=0.5, unit_of_measurement="°C")
            ),
            vol.Optional(
                CONF_SUMMER_MODE_DAYS,
                default=current.get(CONF_SUMMER_MODE_DAYS, DEFAULT_SUMMER_MODE_DAYS)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=7, step=1, unit_of_measurement="Tage")
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
