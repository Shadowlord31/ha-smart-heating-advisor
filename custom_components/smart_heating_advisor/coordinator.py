"""DataUpdateCoordinator for Smart Heating Advisor."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from math import sin, pi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

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
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


class SmartHeatingCoordinator(DataUpdateCoordinator):
    """Koordiniert alle Berechnungen fuer den Smart Heating Advisor."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._config = config

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _get_float(self, entity_id: str) -> float | None:
        """Gibt den State einer Entity als float zurueck."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _get_bool(self, entity_id: str) -> bool:
        """Gibt den State einer binary_sensor Entity als bool zurueck."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        return state.state == "on"

    def _avg_indoor_temp(self) -> float | None:
        """Durchschnitt aller konfigurierten Innentemperatursensoren."""
        sensors = self._config.get(CONF_INDOOR_TEMPS, [])
        values = [v for s in sensors if (v := self._get_float(s)) is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    def _min_indoor_temp(self) -> float | None:
        """Minimum aller Innentemperaturen (kaeltester Raum)."""
        sensors = self._config.get(CONF_INDOOR_TEMPS, [])
        values = [v for s in sensors if (v := self._get_float(s)) is not None]
        if not values:
            return None
        return round(min(values), 1)

    def _any_window_open(self) -> bool:
        """True wenn mindestens ein Fenster offen ist."""
        sensors = self._config.get(CONF_WINDOW_SENSORS, [])
        return any(self._get_bool(s) for s in sensors)

    # ------------------------------------------------------------------
    # Wetterbonus (identisch zu bisherigem Sensor)
    # ------------------------------------------------------------------

    WEATHER_BONUS = {
        "sunny": 3.0,
        "clear-night": -0.5,
        "partlycloudy": 2.0,
        "cloudy": 0.5,
        "fog": -0.5,
        "rainy": -1.0,
        "pouring": -1.5,
        "hail": -2.0,
        "lightning": -1.5,
        "lightning-rainy": -2.0,
        "snowy": -2.0,
        "snowy-rainy": -1.5,
        "windy": -0.5,
        "windy-variant": 0.0,
        "exceptional": -1.0,
    }

    def _weather_bonus(self, condition: str) -> float:
        return self.WEATHER_BONUS.get(condition, 0.0)

    # ------------------------------------------------------------------
    # Tagestrend (Sinus-Kurve, 6-20 Uhr)
    # ------------------------------------------------------------------

    def _day_trend(self, current: float, max_temp: float) -> float:
        now = dt_util.now()
        hour = now.hour + now.minute / 60
        if hour < 6 or hour > 20:
            return 0.0
        day_factor = sin(((hour - 6) / 14) * pi)
        return (max_temp - current) * 0.5 * day_factor

    # ------------------------------------------------------------------
    # Hauptberechnung: heizrelevante Aussentemperatur
    # ------------------------------------------------------------------

    async def _fetch_forecast(self) -> list | None:
        """Ruft den Tages-Forecast vom Weather-Entity ab."""
        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return None
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"type": "daily"},
                target={"entity_id": weather_entity},
                return_response=True,
                blocking=True,
            )
            return response.get(weather_entity, {}).get("forecast", [])
        except Exception as e:
            _LOGGER.warning("Forecast konnte nicht abgerufen werden: %s", e)
            return None

    def _calc_heating_relevant_temp(
        self,
        current: float,
        condition: str,
        forecast: list,
    ) -> float:
        """Berechnet die heizrelevante Aussentemperatur."""
        today = forecast[0] if forecast else {}
        max_temp = float(today.get("temperature", current))
        min_temp = float(today.get("templow", current))

        weather_bonus = self._weather_bonus(condition)
        day_trend = self._day_trend(current, max_temp)

        night_penalty = (
            -2.0 if min_temp < 0 else
            -1.0 if min_temp < 5 else
            -0.5 if min_temp < 8 else
            0.0
        )

        # Morgen-Vorschau: wenn die naechste Nacht kalt wird, nachmittags
        # nicht zu optimistisch sein
        tomorrow = forecast[1] if len(forecast) > 1 else {}
        min_temp_tomorrow = float(tomorrow.get("templow", min_temp))
        tomorrow_penalty = (
            -2.0 if min_temp_tomorrow < 5 else
            -1.5 if min_temp_tomorrow < 8 else
            -1.0 if min_temp_tomorrow < 12 else
            0.0
        )

        calculated = current + weather_bonus + day_trend + night_penalty + tomorrow_penalty
        # Clipping: max +-4 Grad vom aktuellen Wert
        limited = min(calculated, current + 4.0)
        limited = max(limited, current - 4.0)
        return round(limited, 1)

    # ------------------------------------------------------------------
    # Sommermodus-Erkennung
    # ------------------------------------------------------------------

    def _calc_summer_mode(self, forecast: list) -> bool:
        """
        Sommermodus aktiv wenn die naechsten N Tage alle ueber
        heating_threshold liegen (Tag-Max UND Nacht-Min).
        """
        threshold = float(self._config.get(CONF_HEATING_THRESHOLD, DEFAULT_HEATING_THRESHOLD))
        days_needed = int(self._config.get(CONF_SUMMER_MODE_DAYS, DEFAULT_SUMMER_MODE_DAYS))

        if len(forecast) < days_needed:
            return False

        for day in forecast[:days_needed]:
            day_max = float(day.get("temperature", 0))
            day_min = float(day.get("templow", 0))
            # Beide muessen ueber Schwellwert liegen
            if day_min < threshold or day_max < threshold + 3:
                return False
        return True

    # ------------------------------------------------------------------
    # Heizempfehlung
    # ------------------------------------------------------------------

    def _calc_heating_recommendation(
        self,
        heating_relevant_temp: float,
        avg_indoor: float | None,
        min_indoor: float | None,
        summer_mode: bool,
        any_window_open: bool,
    ) -> dict:
        """
        Gibt eine Heizempfehlung zurueck.

        Rueckgabe:
          recommend: bool          - Heizen empfohlen?
          reason: str              - Begruendung
          target_temp: float|None  - Empfohlene Zieltemperatur
          confidence: int          - 0-100
        """
        threshold = float(self._config.get(CONF_HEATING_THRESHOLD, DEFAULT_HEATING_THRESHOLD))
        min_indoor_threshold = float(self._config.get(CONF_MIN_INDOOR_TEMP, DEFAULT_MIN_INDOOR_TEMP))

        # Fenster offen -> kein Heizen
        if any_window_open:
            return {
                "recommend": False,
                "reason": "Fenster geoeffnet",
                "target_temp": None,
                "confidence": 95,
            }

        # Sommermodus -> kein Heizen
        if summer_mode:
            return {
                "recommend": False,
                "reason": "Sommermodus aktiv",
                "target_temp": None,
                "confidence": 90,
            }

        # Innentemperatur zu niedrig -> immer heizen
        if min_indoor is not None and min_indoor < min_indoor_threshold:
            delta = min_indoor_threshold - min_indoor
            target = round(min_indoor_threshold + 0.5, 1)
            confidence = min(100, int(70 + delta * 10))
            return {
                "recommend": True,
                "reason": f"Innentemperatur zu niedrig ({min_indoor}°C)",
                "target_temp": target,
                "confidence": confidence,
            }

        # Aussentemperatur unter Schwellwert -> heizen empfohlen
        if heating_relevant_temp < threshold:
            delta = threshold - heating_relevant_temp
            target = round(min_indoor_threshold + min(delta * 0.3, 2.0), 1)
            confidence = min(100, int(60 + delta * 8))
            return {
                "recommend": True,
                "reason": f"Heizrelevante Aussentemp. {heating_relevant_temp}°C unter Schwelle {threshold}°C",
                "target_temp": target,
                "confidence": confidence,
            }

        # Aussentemperatur im Grenzbereich (threshold bis threshold+3)
        if heating_relevant_temp < threshold + 3:
            return {
                "recommend": False,
                "reason": f"Grenzbereich ({heating_relevant_temp}°C), Beobachtung empfohlen",
                "target_temp": None,
                "confidence": 50,
            }

        return {
            "recommend": False,
            "reason": f"Aussentemperatur ausreichend ({heating_relevant_temp}°C)",
            "target_temp": None,
            "confidence": 85,
        }

    # ------------------------------------------------------------------
    # Update-Methode (wird vom Coordinator aufgerufen)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Hauptupdate - liefert alle berechneten Werte."""
        try:
            outdoor_temp = self._get_float(self._config[CONF_OUTDOOR_TEMP])
            weather_entity = self._config.get(CONF_WEATHER_ENTITY)
            weather_state = self.hass.states.get(weather_entity) if weather_entity else None
            condition = weather_state.state if weather_state else "unknown"

            forecast = await self._fetch_forecast() or []

            avg_indoor = self._avg_indoor_temp()
            min_indoor = self._min_indoor_temp()
            any_window_open = self._any_window_open()

            if outdoor_temp is None:
                raise UpdateFailed("Aussentemperatursensor nicht verfuegbar")

            heating_relevant_temp = self._calc_heating_relevant_temp(
                outdoor_temp, condition, forecast
            )
            summer_mode = self._calc_summer_mode(forecast)
            recommendation = self._calc_heating_recommendation(
                heating_relevant_temp,
                avg_indoor,
                min_indoor,
                summer_mode,
                any_window_open,
            )

            # Forecast-Daten fuer Attribute
            today_forecast = forecast[0] if forecast else {}
            tomorrow_forecast = forecast[1] if len(forecast) > 1 else {}

            return {
                "outdoor_temp": outdoor_temp,
                "heating_relevant_temp": heating_relevant_temp,
                "avg_indoor_temp": avg_indoor,
                "min_indoor_temp": min_indoor,
                "condition": condition,
                "summer_mode": summer_mode,
                "any_window_open": any_window_open,
                "recommend_heating": recommendation["recommend"],
                "recommendation_reason": recommendation["reason"],
                "target_temp": recommendation["target_temp"],
                "confidence": recommendation["confidence"],
                "today_max": today_forecast.get("temperature"),
                "today_min": today_forecast.get("templow"),
                "tomorrow_min": tomorrow_forecast.get("templow"),
                "updated_at": dt_util.now().isoformat(),
            }

        except UpdateFailed:
            raise
        except Exception as e:
            raise UpdateFailed(f"Fehler bei der Heizungsberechnung: {e}") from e
