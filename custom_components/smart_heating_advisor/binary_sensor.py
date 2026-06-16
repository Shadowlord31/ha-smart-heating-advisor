"""BinarySensor-Entitaeten für Smart Heating Advisor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartHeatingCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SmartHeatingCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        HeatingRecommendedBinarySensor(coordinator, entry),
        SummerModeBinarySensor(coordinator, entry),
        WindowOpenBinarySensor(coordinator, entry),
    ])


class _BaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, entry, key, name, device_class):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_class = device_class
        self._entry = entry

    @property
    def is_on(self):
        return bool(self.coordinator.data.get(self._key)) if self.coordinator.data else False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Smart Heating Advisor",
            "manufacturer": "Shadowlord31",
        }


class HeatingRecommendedBinarySensor(_BaseBinarySensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="recommend_heating",
            name="Heizen empfohlen",
            device_class=None,
        )

    @property
    def icon(self):
        return "mdi:radiator" if self.is_on else "mdi:radiator-off" 

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {
            "begruendung": d.get("recommendation_reason"),
            "konfidenz": d.get("confidence"),
            "zieltemperatur": d.get("target_temp"),
        }


class SummerModeBinarySensor(_BaseBinarySensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="summer_mode",
            name="Sommermodus aktiv",
            device_class=None,
        )

    @property
    def icon(self):
        return "mdi:weather-sunny" if self.is_on else "mdi:weather-partly-cloudy"

    @property
    def extra_state_attributes(self):
        from .const import DOMAIN
        state = self.coordinator.hass.data.get(DOMAIN, {}).get(f"{self._entry.entry_id}_summer_state", {})
        return {
            "kalte_tage_in_folge": state.get("cold_days", 0),
            "hysterese_schwelle": 2,
        }


class WindowOpenBinarySensor(_BaseBinarySensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="any_window_open",
            name="Fenster geoeffnet (Heizung)",
            device_class=BinarySensorDeviceClass.WINDOW,
        )
