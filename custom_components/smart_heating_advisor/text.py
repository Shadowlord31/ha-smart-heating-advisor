"""Text-Entitaeten fuer Smart Heating Advisor."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_INDOOR_TEMP_LABEL,
    CONF_WINDOW_LABEL,
)
from .coordinator import SmartHeatingCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SmartHeatingCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Startwerte aus gespeicherten Options laden
    opts = entry.options
    text_store = hass.data[DOMAIN].setdefault(f"{entry.entry_id}_texts", {})
    text_store.setdefault(CONF_INDOOR_TEMP_LABEL, opts.get(CONF_INDOOR_TEMP_LABEL, ""))
    text_store.setdefault(CONF_WINDOW_LABEL, opts.get(CONF_WINDOW_LABEL, ""))

    async_add_entities([
        SHATextEntity(
            coordinator=coordinator,
            entry=entry,
            key=CONF_INDOOR_TEMP_LABEL,
            name="Innentemperaturen Label",
            icon="mdi:label",
        ),
        SHATextEntity(
            coordinator=coordinator,
            entry=entry,
            key=CONF_WINDOW_LABEL,
            name="Fensterkontakte Label",
            icon="mdi:label-outline",
        ),
    ])


class SHATextEntity(CoordinatorEntity, TextEntity):
    """Eingebbarer Label-Name direkt im Geraet."""

    def __init__(self, coordinator, entry, key, name, icon):
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        self._attr_mode = TextMode.TEXT
        self._attr_native_max = 100
        self._attr_native_min = 0

    @property
    def _store(self) -> dict:
        return self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_texts", {})

    @property
    def native_value(self) -> str:
        return self._store.get(self._key, "")

    async def async_set_value(self, value: str) -> None:
        """Wert setzen, persistieren und Coordinator neu laden."""
        self._store[self._key] = value.strip()

        new_options = dict(self._entry.options)
        new_options[self._key] = value.strip()
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
