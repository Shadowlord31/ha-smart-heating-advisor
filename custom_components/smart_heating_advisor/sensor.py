"""Sensor-Entitaeten für Smart Heating Advisor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
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
        HeatingRelevantTempSensor(coordinator, entry),
        RecommendedTargetTempSensor(coordinator, entry),
        HeatingConfidenceSensor(coordinator, entry),
        HeatingReasonSensor(coordinator, entry),
        AvgIndoorTempSensor(coordinator, entry),
        MinIndoorTempSensor(coordinator, entry),
        IndoorTrendSensor(coordinator, entry),
    ])


class _BaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, name, unit, device_class, state_class):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._entry = entry

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key) if self.coordinator.data else None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Smart Heating Advisor",
            "manufacturer": "Shadowlord31",
        }


class HeatingRelevantTempSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="heating_relevant_temp",
            name="Heizrelevante Außentemperatur",
            unit="°C",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        c = d.get("components", {})
        return {
            "echte_aussentemperatur": d.get("outdoor_temp"),
            "wetterzustand": d.get("condition"),
            "tages_max": d.get("today_max"),
            "tages_min": d.get("today_min"),
            "morgen_min": d.get("tomorrow_min"),
            "wetter_bonus": c.get("wetter_bonus"),
            "tagestrend": c.get("tagestrend"),
            "nacht_malus": c.get("nacht_malus"),
            "morgen_malus": c.get("morgen_malus"),
            "gebaeude_korrektur": c.get("gebaeude_korrektur"),
            "wind_korrektur": c.get("wind_korrektur"),
            "regenrate": d.get("rain_rate"),
            "windgeschwindigkeit": d.get("wind_speed"),
            "gefuehlte_aussentemperatur": d.get("feels_like"),
            "trend_verfuegbar": d.get("indoor_trend_available"),
            "rohtrend_24h": d.get("indoor_trend_per_hour"),
            "bereinigter_trend_24h": d.get("corrected_trend"),
            "lüftungskorrektur": d.get("ventilation_cooling"),
            "aktive_innensensoren": d.get("active_indoor_sensors"),
            "aktive_fenstersensoren": d.get("active_window_sensors"),
            "aktualisiert": d.get("updated_at"),
        }


class RecommendedTargetTempSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="target_temp",
            name="Empfohlene Heiztemperatur",
            unit="°C",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        )


class HeatingConfidenceSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="confidence",
            name="Heizempfehlung Konfidenz",
            unit="%",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
        )


class HeatingReasonSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="recommendation_reason",
            name="Heizempfehlung Begruendung",
            unit=None,
            device_class=None,
            state_class=None,
        )


class AvgIndoorTempSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="avg_indoor_temp",
            name="Durchschnittliche Innentemperatur",
            unit="°C",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        )


class MinIndoorTempSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="min_indoor_temp",
            name="Minimale Innentemperatur",
            unit="°C",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
        )


class IndoorTrendSensor(_BaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(
            coordinator, entry,
            key="indoor_trend_per_hour",
            name="Innentemperatur Trend",
            unit="°C/h",
            device_class=None,
            state_class=SensorStateClass.MEASUREMENT,
        )

    @property
    def icon(self):
        val = self.native_value
        if val is None:
            return "mdi:thermometer-lines"
        if val < -0.3:
            return "mdi:thermometer-chevron-down"
        if val > 0.3:
            return "mdi:thermometer-chevron-up"
        return "mdi:thermometer-lines"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {
            "verfuegbar": d.get("indoor_trend_available"),
            "gebaeude_korrektur": d.get("building_correction"),
        }
