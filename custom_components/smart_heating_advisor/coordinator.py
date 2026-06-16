"""DataUpdateCoordinator for Smart Heating Advisor."""
from __future__ import annotations

import logging
from datetime import timedelta, datetime
from math import sin, pi

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_OUTDOOR_TEMP,
    CONF_INDOOR_TEMPS,
    CONF_WEATHER_ENTITY,
    CONF_WINDOW_SENSORS,
    CONF_FEELS_LIKE_SENSOR,
    CONF_RAIN_RATE_SENSOR,
    CONF_WIND_SPEED_SENSOR,
    WIND_CHILL_THRESHOLD,
    WIND_CHILL_FACTOR,
    RAIN_BONUS_OVERRIDE,
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
    UPDATE_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

TREND_HOURS = 24  # Stunden fuer Trendberechnung
VENTILATION_FACTOR = 0.08  # Abkuehlung pro Grad Delta pro Stunde offen


class SmartHeatingCoordinator(DataUpdateCoordinator):
    """Koordiniert alle Berechnungen für den Smart Heating Advisor."""

    def __init__(self, hass: HomeAssistant, config: dict, entry_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._config = config
        self._entry_id = entry_id

    # ------------------------------------------------------------------
    # Number-Store Zugriff
    # ------------------------------------------------------------------

    def _num(self, key: str, default: float) -> float:
        """Liest einen Wert aus dem Number-Store."""
        store = self.hass.data.get(DOMAIN, {}).get(f"{self._entry_id}_numbers", {})
        return float(store.get(key, default))

    # ------------------------------------------------------------------
    # Label-Aufloesung
    # ------------------------------------------------------------------

    def _entities_by_label(self, label: str, domain: str) -> list[str]:
        """Gibt alle Entitaeten mit dem angegebenen Label und Domain zurueck."""
        registry = er.async_get(self.hass)
        return [
            e.entity_id for e in registry.entities.values()
            if label in (e.labels or set())
            and e.domain == domain
        ]

    def _resolve_indoor_sensors(self) -> list[str]:
        """Gibt manuell konfigurierte Innensensoren zurueck."""
        return self._config.get(CONF_INDOOR_TEMPS, [])

    def _resolve_window_sensors(self) -> list[str]:
        """Gibt manuell konfigurierte Fenstersensoren zurueck."""
        return self._config.get(CONF_WINDOW_SENSORS, [])

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    def _get_float(self, entity_id: str) -> float | None:
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _get_bool(self, entity_id: str) -> bool:
        state = self.hass.states.get(entity_id)
        if state is None:
            return False
        return state.state == "on"

    def _avg_indoor_temp(self) -> float | None:
        sensors = self._resolve_indoor_sensors()
        values = [v for s in sensors if (v := self._get_float(s)) is not None]
        if not values:
            return None
        return round(sum(values) / len(values), 1)

    def _min_indoor_temp(self) -> float | None:
        sensors = self._resolve_indoor_sensors()
        values = [v for s in sensors if (v := self._get_float(s)) is not None]
        if not values:
            return None
        return round(min(values), 1)

    def _any_window_open(self) -> bool:
        sensors = self._resolve_window_sensors()
        return any(self._get_bool(s) for s in sensors)

    # ------------------------------------------------------------------
    # Recorder-Zugriff für Trend
    # ------------------------------------------------------------------

    async def _get_indoor_temp_hours_ago(self, hours: float) -> float | None:
        """Gibt die durchschnittliche Innentemperatur vor X Stunden zurueck."""
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.history import get_significant_states

            sensors = self._resolve_indoor_sensors()
            if not sensors:
                return None

            start = dt_util.now() - timedelta(hours=hours + 0.5)
            end = dt_util.now() - timedelta(hours=hours - 0.5)

            instance = get_instance(self.hass)
            states = await instance.async_add_executor_job(
                get_significant_states,
                self.hass,
                start,
                end,
                sensors,
            )

            values = []
            for entity_states in states.values():
                for state in entity_states:
                    try:
                        values.append(float(state.state))
                        break
                    except (ValueError, TypeError):
                        continue

            if not values:
                return None
            return round(sum(values) / len(values), 1)

        except Exception as e:
            _LOGGER.debug("Recorder-Zugriff fehlgeschlagen: %s", e)
            return None

    async def _calc_ventilation_cooling(self, outdoor_temp: float) -> float:
        """
        Berechnet die erwartete Abkuehlung durch Lueften der letzten 24h.
        Formel: (Innen - Aussen) * Fenster_offen_Stunden * VENTILATION_FACTOR
        """
        window_sensors = self._resolve_window_sensors()
        if not window_sensors:
            return 0.0
        try:
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.history import get_significant_states

            now = dt_util.now()
            start = now - timedelta(hours=TREND_HOURS)
            instance = get_instance(self.hass)
            history = await instance.async_add_executor_job(
                get_significant_states,
                self.hass,
                start,
                now,
                window_sensors,
            )
            if not history:
                return 0.0

            total_open_seconds = 0.0
            for entity_id, states in history.items():
                if not states:
                    continue
                for i, state in enumerate(states):
                    if state.state != "on":
                        continue
                    seg_start = max(state.last_updated, start)
                    seg_end = states[i + 1].last_updated if i + 1 < len(states) else now
                    seg_end = min(seg_end, now)
                    if seg_end > seg_start:
                        total_open_seconds += (seg_end - seg_start).total_seconds()

            open_hours = total_open_seconds / 3600 / max(len(window_sensors), 1)
            current_indoor = self._avg_indoor_temp() or 20.0
            delta = max(current_indoor - outdoor_temp, 0)
            return round(min(delta * open_hours * VENTILATION_FACTOR, 3.0), 2)
        except Exception as e:
            _LOGGER.debug("Lueftungsberechnung fehlgeschlagen: %s", e)
            return 0.0

    async def _calc_building_trend(self, current_indoor: float, outdoor_temp: float) -> dict:
        """
        Fensterbereinigter 24h-Gebaeudewaermetrend.
        """
        temp_24h_ago = await self._get_indoor_temp_hours_ago(TREND_HOURS)

        if temp_24h_ago is None or current_indoor is None:
            return {
                "correction": 0.0,
                "trend_per_hour": None,
                "ventilation_cooling": 0.0,
                "corrected_trend": None,
                "available": False,
            }

        raw_trend = current_indoor - temp_24h_ago  # Gesamt-Delta in °C ueber 24h
        trend_per_hour = raw_trend / TREND_HOURS

        ventilation_cooling = await self._calc_ventilation_cooling(outdoor_temp)
        corrected_trend = raw_trend + ventilation_cooling

        if corrected_trend < -2.0:
            correction = -3.0
        elif corrected_trend < -1.0:
            correction = -2.0
        elif corrected_trend < -0.5:
            correction = -1.0
        elif corrected_trend < 0.0:
            correction = -0.5
        elif corrected_trend > 1.5:
            correction = 1.0
        elif corrected_trend > 0.5:
            correction = 0.5
        else:
            correction = 0.0

        return {
            "correction": round(correction, 2),
            "trend_per_hour": round(trend_per_hour, 3),
            "ventilation_cooling": ventilation_cooling,
            "corrected_trend": round(corrected_trend, 2),
            "available": True,
        }

    # ------------------------------------------------------------------
    # Wetterbonus
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
        """Wetterbonus – echte Regenrate hat Vorrang vor Wetterzustand."""
        rain_sensor = self._config.get(CONF_RAIN_RATE_SENSOR)
        if rain_sensor:
            rain_rate = self._get_float(rain_sensor)
            if rain_rate is not None and rain_rate > 0.1:
                return RAIN_BONUS_OVERRIDE
        return self.WEATHER_BONUS.get(condition, 0.0)

    def _wind_correction(self) -> float:
        """Windkorrektur: starker Wind kuehlt Gebaeude schneller aus."""
        wind_sensor = self._config.get(CONF_WIND_SPEED_SENSOR)
        if not wind_sensor:
            return 0.0
        wind_speed = self._get_float(wind_sensor)
        if wind_speed is None or wind_speed <= WIND_CHILL_THRESHOLD:
            return 0.0
        correction = -(wind_speed - WIND_CHILL_THRESHOLD) * WIND_CHILL_FACTOR
        return round(max(correction, -2.0), 2)

    # ------------------------------------------------------------------
    # Tagestrend
    # ------------------------------------------------------------------

    def _day_trend(self, current: float, max_temp: float) -> float:
        now = dt_util.now()
        hour = now.hour + now.minute / 60
        if hour < 6 or hour > 20:
            return 0.0
        day_factor = sin(((hour - 6) / 14) * pi)
        return (max_temp - current) * 0.5 * day_factor

    # ------------------------------------------------------------------
    # Forecast
    # ------------------------------------------------------------------

    async def _fetch_forecast(self) -> list:
        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if not weather_entity:
            return []
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
            return []

    # ------------------------------------------------------------------
    # Heizrelevante Außentemperatur
    # ------------------------------------------------------------------

    def _calc_heating_relevant_temp(
        self,
        current: float,
        condition: str,
        forecast: list,
        building_correction: float,
    ) -> dict:
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

        tomorrow = forecast[1] if len(forecast) > 1 else {}
        min_temp_tomorrow = float(tomorrow.get("templow", min_temp))
        tomorrow_penalty = (
            -2.0 if min_temp_tomorrow < 5 else
            -1.5 if min_temp_tomorrow < 8 else
            -1.0 if min_temp_tomorrow < 12 else
            0.0
        )

        wind_correction = self._wind_correction()
        calculated = (
            current
            + weather_bonus
            + day_trend
            + night_penalty
            + tomorrow_penalty
            + building_correction
            + wind_correction
        )

        limited = min(calculated, current + 4.0)
        limited = max(limited, current - 4.0)

        return {
            "value": round(limited, 1),
            "components": {
                "basis": current,
                "wetter_bonus": round(weather_bonus, 1),
                "tagestrend": round(day_trend, 2),
                "nacht_malus": night_penalty,
                "morgen_malus": tomorrow_penalty,
                "gebaeude_korrektur": building_correction,
                "wind_korrektur": wind_correction,
            }
        }

    # ------------------------------------------------------------------
    # Sommermodus
    # ------------------------------------------------------------------

    HYSTERESIS_COLD_DAYS = 2  # Anzahl Tage in Folge "kalt" bevor Sommermodus wirklich abschaltet

    def _summer_state_store(self) -> dict:
        """Persistenter Zustand fuer die Sommermodus-Hysterese."""
        return self.hass.data.setdefault(DOMAIN, {}).setdefault(
            f"{self._entry_id}_summer_state",
            {"cold_days": 0, "was_active": False, "last_eval_date": None}
        )

    SNAPSHOT_HOUR = 23
    SNAPSHOT_MINUTE = 30

    def _daymax_snapshot_store(self) -> dict:
        """
        Persistenter Speicher fuer den fixierten Tagesmax-Wert von 'heute'.
        Wird taeglich um 23:30 aus forecast[1] (morgen) neu befuellt,
        damit der Wert fuer den kommenden Tag den ganzen Tag stabil bleibt
        und nicht durch die fortschreitende Tageszeit nach unten verzerrt wird.
        """
        return self.hass.data.setdefault(DOMAIN, {}).setdefault(
            f"{self._entry_id}_daymax_snapshot",
            {"date": None, "fixed_max": None}
        )

    def _update_daymax_snapshot(self, forecast: list) -> None:
        """
        Prueft ob es Zeit fuer einen neuen Snapshot ist (kurz vor Mitternacht)
        und speichert dann forecast[1] (morgen) als fixen Wert fuer den
        kommenden Tag.
        """
        store = self._daymax_snapshot_store()
        now = dt_util.now()
        today_str = now.date().isoformat()

        is_snapshot_time = (
            now.hour == self.SNAPSHOT_HOUR and now.minute >= self.SNAPSHOT_MINUTE
        )

        if is_snapshot_time and store.get("date") != today_str:
            if len(forecast) > 1:
                tomorrow_max = float(forecast[1].get("temperature", 0))
                store["date"] = today_str
                store["fixed_max"] = tomorrow_max
                _LOGGER.debug(
                    "Tagesmax-Snapshot erstellt fuer kommenden Tag: %s°C", tomorrow_max
                )

    def _get_today_max_for_summer(self, forecast: list) -> float | None:
        """
        Gibt das stabile Tagesmaximum fuer 'heute' zurueck.
        Nutzt den gestrigen Snapshot wenn vorhanden (stabil, nicht
        tageszeit-verzerrt), sonst Fallback auf forecast[0].
        """
        store = self._daymax_snapshot_store()
        now = dt_util.now()
        today_str = now.date().isoformat()

        # Snapshot ist gueltig wenn er gestern fuer heute erstellt wurde
        if store.get("fixed_max") is not None:
            snapshot_date = store.get("date")
            # Snapshot wurde am Vortag fuer "heute" erstellt
            if snapshot_date and snapshot_date < today_str:
                return store["fixed_max"]
            # Snapshot ist von heute selbst (z.B. nach 23:30) - gehoert zu morgen, nicht nutzen
            elif snapshot_date == today_str:
                pass

        # Fallback: kein gueltiger Snapshot vorhanden, rohen Forecast-Wert nutzen
        if forecast:
            return float(forecast[0].get("temperature", 0))
        return None

    def _calc_summer_mode_raw(self, forecast: list, avg_indoor: float | None, indoor_trend: float | None) -> bool:
        """
        Rohbewertung ohne Hysterese:
        - Tagesmaximum der naechsten N Tage ueber Sommer-Tagesmax-Schwelle
          (heutiger Wert kommt aus stabilem Snapshot statt Live-Forecast)
        - Innentemperatur aktuell ueber Sommer-Mindest-Innentemperatur
        - Innentemperatur-Trend nicht stark fallend
        """
        day_max_threshold = self._num(NUMBER_SUMMER_DAY_MAX, DEFAULT_SUMMER_DAY_MAX)
        days_needed = int(self._num(NUMBER_SUMMER_MODE_DAYS, DEFAULT_SUMMER_MODE_DAYS))
        summer_min_indoor = self._num(NUMBER_SUMMER_MIN_INDOOR, DEFAULT_SUMMER_MIN_INDOOR)

        if len(forecast) < days_needed:
            return False

        self._update_daymax_snapshot(forecast)

        # Tag 0 (heute): stabiler Snapshot-Wert statt Live-Forecast
        today_max = self._get_today_max_for_summer(forecast)
        if today_max is not None and today_max < day_max_threshold:
            return False

        # Folgetage: normaler Forecast-Wert (nicht von Tageszeit-Bias betroffen)
        for day in forecast[1:days_needed]:
            day_max = float(day.get("temperature", 0))
            if day_max < day_max_threshold:
                return False

        if avg_indoor is not None and avg_indoor < summer_min_indoor:
            return False

        if indoor_trend is not None and indoor_trend < -0.4:
            return False

        return True

    def _calc_summer_mode(self, forecast: list, avg_indoor: float | None, indoor_trend: float | None) -> bool:
        """
        Sommermodus mit Hysterese: bleibt aktiv bis HYSTERESIS_COLD_DAYS Tage
        in Folge die Rohbewertung negativ war. Verhindert Flackern bei
        einzelnen kuehleren Tagen.
        """
        raw_active = self._calc_summer_mode_raw(forecast, avg_indoor, indoor_trend)
        state = self._summer_state_store()
        today = dt_util.now().date().isoformat()

        if raw_active:
            state["cold_days"] = 0
            state["was_active"] = True
            state["last_eval_date"] = today
            return True

        # Rohbewertung negativ - Hysterese pruefen
        if state["was_active"]:
            # Cold-Day-Counter nur einmal pro Kalendertag erhoehen
            if state.get("last_eval_date") != today:
                state["cold_days"] += 1
                state["last_eval_date"] = today

            if state["cold_days"] < self.HYSTERESIS_COLD_DAYS:
                # Noch nicht genug kalte Tage in Folge - Sommermodus bleibt aktiv
                return True
            else:
                # Schwelle erreicht - jetzt wirklich abschalten
                state["was_active"] = False
                state["cold_days"] = 0
                return False

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
    ) -> dict:
        threshold = self._num(NUMBER_HEATING_THRESHOLD, DEFAULT_HEATING_THRESHOLD)

        min_indoor_threshold = self._num(NUMBER_MIN_INDOOR_TEMP, DEFAULT_MIN_INDOOR_TEMP)

        if summer_mode:
            return {"recommend": False, "reason": "Sommermodus aktiv", "target_temp": min_indoor_threshold, "confidence": 90}

        if min_indoor is not None and min_indoor < min_indoor_threshold:
            delta = min_indoor_threshold - min_indoor
            target = round(min_indoor_threshold + 0.5, 1)
            confidence = min(100, int(70 + delta * 10))
            return {"recommend": True, "reason": f"Innentemperatur zu niedrig ({min_indoor}°C)", "target_temp": target, "confidence": confidence}

        if heating_relevant_temp < threshold:
            delta = threshold - heating_relevant_temp
            target = round(min_indoor_threshold + min(delta * 0.3, 2.0), 1)
            confidence = min(100, int(60 + delta * 8))
            return {"recommend": True, "reason": f"Heizrelevante Aussentemp. {heating_relevant_temp}°C unter Schwelle {threshold}°C", "target_temp": target, "confidence": confidence}

        if heating_relevant_temp < threshold + 3:
            return {"recommend": False, "reason": f"Grenzbereich ({heating_relevant_temp}°C), Beobachtung empfohlen", "target_temp": None, "confidence": 50}

        return {"recommend": False, "reason": f"Außentemperatur ausreichend ({heating_relevant_temp}°C)", "target_temp": None, "confidence": 85}

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        try:
            outdoor_temp = self._get_float(self._config[CONF_OUTDOOR_TEMP])
            if outdoor_temp is None:
                raise UpdateFailed("Außentemperatursensor nicht verfuegbar")

            weather_entity = self._config.get(CONF_WEATHER_ENTITY)
            weather_state = self.hass.states.get(weather_entity) if weather_entity else None
            condition = weather_state.state if weather_state else "unknown"

            forecast = await self._fetch_forecast()
            avg_indoor = self._avg_indoor_temp()
            min_indoor = self._min_indoor_temp()
            any_window_open = self._any_window_open()

            # Gebaeude-Trend berechnen
            building = await self._calc_building_trend(avg_indoor or 20.0, outdoor_temp)

            # Heizrelevante Außentemperatur
            heating_result = self._calc_heating_relevant_temp(
                outdoor_temp, condition, forecast, building["correction"]
            )
            heating_relevant_temp = heating_result["value"]
            components = heating_result["components"]

            summer_mode = self._calc_summer_mode(forecast, avg_indoor, building["trend_per_hour"])
            recommendation = self._calc_heating_recommendation(
                heating_relevant_temp, avg_indoor, min_indoor, summer_mode
            )

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
                "indoor_trend_per_hour": building["trend_per_hour"],
                "indoor_trend_available": building["available"],
                "building_correction": building["correction"],
                "ventilation_cooling": building["ventilation_cooling"],
                "corrected_trend": building["corrected_trend"],
                "components": components,
                "updated_at": dt_util.now().isoformat(),
                "active_indoor_sensors": self._resolve_indoor_sensors(),
                "active_window_sensors": self._resolve_window_sensors(),
                "rain_rate": self._get_float(self._config.get(CONF_RAIN_RATE_SENSOR, "")),
                "wind_speed": self._get_float(self._config.get(CONF_WIND_SPEED_SENSOR, "")),
                "feels_like": self._get_float(self._config.get(CONF_FEELS_LIKE_SENSOR, "")),
            }

        except UpdateFailed:
            raise
        except Exception as e:
            raise UpdateFailed(f"Fehler bei der Heizungsberechnung: {e}") from e
