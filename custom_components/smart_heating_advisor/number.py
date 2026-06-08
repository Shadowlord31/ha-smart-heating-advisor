"""Number-Entitaeten für Smart Heating Advisor."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DEFAULT_HEATING_THRESHOLD,
    DEFAULT_SUMMER_MODE_DAYS,
    DEFAULT_MIN_INDOOR_TEMP,
    DEFAULT_SUMMER_DAY_MAX,
    DEFAULT_SUMMER_MIN_INDOOR,
    NUMBER_HEATING_THRESHOLD,
    NUMBER_SUMMER_MODE_DAYS,
    NUMBER_MIN_INDOOR_TEMP,
    NUMBER_SUMMER_DAY_MAX,
    NUMBER_SUMMER_MIN_INDOOR,
)
from .coordinator import SmartHeatingCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SmartHeatingCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        SHANumberEntity(
            coordinator=coordinator,
            entry=entry,
            key=NUMBER_HEATING_THRESHOLD,
            name="Heizschwelle Außentemperatur",
            icon="mdi:thermometer-alert",
            min_value=5.0,
            max_value=25.0,
            step=0.5,
            unit="°C",
            default=DEFAULT_HEATING_THRESHOLD,
        ),
        SHANumberEntity(
            coordinator=coordinator,
            entry=entry,
            key=NUMBER_MIN_INDOOR_TEMP,
            name="Mindest-Innentemperatur",
            icon="mdi:home-thermometer",
            min_value=15.0,
            max_value=24.0,
            step=0.5,
            unit="°C",
            default=DEFAULT_MIN_INDOOR_TEMP,
        ),
        SHANumberEntity(
            coordinator=coordinator,
            entry=entry,
            key=NUMBER_SUMMER_DAY_MAX,
            name="Sommer Tagesmax-Schwelle",
            icon="mdi:weather-sunny",
            min_value=15.0,
            max_value=30.0,
            step=0.5,
            unit="°C",
            default=DEFAULT_SUMMER_DAY_MAX,
        ),
        SHANumberEntity(
            coordinator=coordinator,
            entry=entry,
            key=NUMBER_SUMMER_MIN_INDOOR,
            name="Sommer Mindest-Innentemperatur",
            icon="mdi:home-thermometer-outline",
            min_value=15.0,
            max_value=24.0,
            step=0.5,
            unit="°C",
            default=DEFAULT_SUMMER_MIN_INDOOR,
        ),
        SHANumberEntity(
            coordinator=coordinator,
            entry=entry,
            key=NUMBER_SUMMER_MODE_DAYS,
            name="Sommermodus Anzahl Tage",
            icon="mdi:calendar-range",
            min_value=1.0,
            max_value=7.0,
            step=1.0,
            unit="Tage",
            default=float(DEFAULT_SUMMER_MODE_DAYS),
        ),
    ]

    # Startwerte aus persistierten options laden (Vorrang) dann config dann Default
    opts = entry.options
    number_store = hass.data[DOMAIN].setdefault(f"{entry.entry_id}_numbers", {})

    number_store[NUMBER_HEATING_THRESHOLD] = float(opts.get(NUMBER_HEATING_THRESHOLD, DEFAULT_HEATING_THRESHOLD))
    number_store[NUMBER_MIN_INDOOR_TEMP] = float(opts.get(NUMBER_MIN_INDOOR_TEMP, DEFAULT_MIN_INDOOR_TEMP))
    number_store[NUMBER_SUMMER_DAY_MAX] = float(opts.get(NUMBER_SUMMER_DAY_MAX, DEFAULT_SUMMER_DAY_MAX))
    number_store[NUMBER_SUMMER_MIN_INDOOR] = float(opts.get(NUMBER_SUMMER_MIN_INDOOR, DEFAULT_SUMMER_MIN_INDOOR))
    number_store[NUMBER_SUMMER_MODE_DAYS] = float(opts.get(NUMBER_SUMMER_MODE_DAYS, DEFAULT_SUMMER_MODE_DAYS))

    async_add_entities(entities)


class SHANumberEntity(CoordinatorEntity, NumberEntity):
    """Einstellbarer Zahlenwert direkt im Geraet."""

    def __init__(self, coordinator, entry, key, name, icon, min_value, max_value, step, unit, default):
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = NumberMode.BOX
        self._default = default

    @property
    def _store(self) -> dict:
        return self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_numbers", {})

    @property
    def native_value(self) -> float:
        return self._store.get(self._key, self._default)

    async def async_set_native_value(self, value: float) -> None:
        """Wert setzen, persistieren und Coordinator neu laden."""
        self._store[self._key] = value

        # In entry.options persistieren damit Werte nach Neustart erhalten bleiben
        new_options = dict(self._entry.options)
        new_options[self._key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)

        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Smart Heating Advisor",
            "manufacturer": "Shadowlord31",
        }
