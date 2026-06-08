# Smart Heating Advisor

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Shadowlord31/ha-smart-heating-advisor.svg)](https://github.com/Shadowlord31/ha-smart-heating-advisor/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A smart Home Assistant custom integration that provides **weather-aware, forecast-based heating recommendations** — taking into account outdoor temperature, weather conditions, daily forecasts, indoor temperature trends, and window states.

---

## 🇩🇪 Deutsch

### Was ist Smart Heating Advisor?

Smart Heating Advisor ist eine Home Assistant Custom Integration die intelligent berechnet ob und wie viel geheizt werden soll. Dabei werden nicht nur die aktuelle Außentemperatur berücksichtigt, sondern auch Wettervorhersage, Tagesverlauf, Gebäude-Wärmeträgheit und Fensterstatus.

### Wie funktioniert die Berechnung?

Die Kernberechnung ermittelt eine **heizrelevante Außentemperatur** die smarter ist als die reine Außentemperatur:

| Faktor | Beschreibung |
|---|---|
| **Wetterbonus** | Sonnig → +3°C / Regen → -1°C / Schnee → -2°C usw. |
| **Tagestrend** | Wird es heute noch wärmer? Sinuskurve 6–20 Uhr |
| **Nacht-Malus** | Kalte Nacht heute → bis -2°C Abschlag |
| **Morgen-Vorschau** | Kalte Nacht morgen → bis -2°C Abschlag |
| **Gebäude-Wärmeträgheit** | Fällt Innentemp. schnell → bis -3°C Korrektur |

Der Sommermodus verhindert dass die Heizung in warmen Monaten anspringt — auch wenn einzelne Nächte kühler sind.

### Entitäten

| Entität | Typ | Beschreibung |
|---|---|---|
| `sensor.heizrelevante_aussentemperatur` | Sensor | Berechnete Außentemperatur inkl. aller Faktoren |
| `sensor.empfohlene_heiztemperatur` | Sensor | Empfohlene Ziel-Raumtemperatur |
| `sensor.heizempfehlung_konfidenz` | Sensor | Konfidenz der Empfehlung (0–100 %) |
| `sensor.heizempfehlung_begruendung` | Sensor | Textuelle Begründung der Empfehlung |
| `sensor.durchschnittliche_innentemperatur` | Sensor | Durchschnitt aller Innentemperatursensoren |
| `sensor.minimale_innentemperatur` | Sensor | Kältester Raum |
| `sensor.innentemperatur_trend` | Sensor | Temperaturtrend der letzten 3h (°C/h) |
| `binary_sensor.heizen_empfohlen` | BinarySensor | Heizen ja/nein |
| `binary_sensor.sommermodus_aktiv` | BinarySensor | Sommermodus aktiv |
| `binary_sensor.fenster_geoeffnet_heizung` | BinarySensor | Mindestens ein Fenster offen |

### Steuerelemente (direkt im Gerät einstellbar)

| Steuerelement | Standard | Beschreibung |
|---|---|---|
| Heizschwelle Außentemperatur | 15 °C | Ab welcher heizrelevanter Außentemp. geheizt wird |
| Mindest-Innentemperatur | 20 °C | Untergrenze für Innentemperatur |
| Sommer Tagesmax-Schwelle | 20 °C | Ab welchem Tagesmaximum ein Tag als "warm" gilt |
| Sommer Mindest-Innentemperatur | 19 °C | Wohnung muss noch warm genug sein für Sommermodus |
| Sommermodus Anzahl Tage | 3 | Wie viele aufeinanderfolgende warme Tage = Sommermodus |

### Installation via HACS

1. HACS öffnen → Integrationen → ⋮ → **Benutzerdefinierte Repositories**
2. URL eingeben: `https://github.com/Shadowlord31/ha-smart-heating-advisor`
3. Kategorie: **Integration** → Hinzufügen
4. Integration suchen und **Installieren**
5. Home Assistant neu starten
6. Einstellungen → Integrationen → **Smart Heating Advisor** einrichten

### Konfiguration

Bei der Einrichtung werden folgende Felder abgefragt:

| Feld | Pflicht | Beschreibung |
|---|---|---|
| Außentemperatursensor | ✅ | Ein einzelner Temperatursensor außen |
| Innentemperatursensoren | ☑️ | Mehrere Räume möglich, wird für Trendberechnung genutzt |
| Fensterkontakte | ➖ | Optional, verhindert Heizen bei offenem Fenster |
| Wetter-Entity | ✅ | Weather-Entity für Mehrtages-Forecast |

### Anforderungen

- Home Assistant 2024.4.1 oder neuer
- HACS 2.0.0 oder neuer
- Mindestens ein Außentemperatursensor
- Eine Weather-Entity mit Tages-Forecast

---

## 🇬🇧 English

### What is Smart Heating Advisor?

Smart Heating Advisor is a Home Assistant custom integration that intelligently calculates whether and how much heating is needed. It considers not just the current outdoor temperature, but also weather forecasts, time of day, building thermal inertia, and window states.

### How does the calculation work?

The core calculation determines a **heating-relevant outdoor temperature** that is smarter than the raw outdoor temperature:

| Factor | Description |
|---|---|
| **Weather Bonus** | Sunny → +3°C / Rain → -1°C / Snow → -2°C etc. |
| **Day Trend** | Will it get warmer today? Sine curve from 6–20h |
| **Night Penalty** | Cold night tonight → up to -2°C adjustment |
| **Tomorrow Preview** | Cold night tomorrow → up to -2°C adjustment |
| **Building Inertia** | Indoor temp falling fast → up to -3°C correction |

Summer mode prevents heating from activating during warm months — even if individual nights are cooler.

### Entities

| Entity | Type | Description |
|---|---|---|
| `sensor.heating_relevant_outdoor_temp` | Sensor | Calculated outdoor temp including all factors |
| `sensor.recommended_heating_temperature` | Sensor | Recommended target room temperature |
| `sensor.heating_recommendation_confidence` | Sensor | Confidence of recommendation (0–100 %) |
| `sensor.heating_recommendation_reason` | Sensor | Text explanation of the recommendation |
| `sensor.average_indoor_temperature` | Sensor | Average of all indoor temperature sensors |
| `sensor.minimum_indoor_temperature` | Sensor | Coldest room |
| `sensor.indoor_temperature_trend` | Sensor | Temperature trend last 3h (°C/h) |
| `binary_sensor.heating_recommended` | BinarySensor | Heating yes/no |
| `binary_sensor.summer_mode_active` | BinarySensor | Summer mode active |
| `binary_sensor.window_open_heating` | BinarySensor | At least one window open |

### Controls (adjustable directly on the device page)

| Control | Default | Description |
|---|---|---|
| Heating Threshold Outdoor Temp | 15 °C | Below this heating-relevant temp, heating is recommended |
| Minimum Indoor Temperature | 20 °C | Lower limit for indoor temperature |
| Summer Day Max Threshold | 20 °C | Daily maximum above which a day counts as "warm" |
| Summer Minimum Indoor Temp | 19 °C | Indoor must still be warm enough for summer mode |
| Summer Mode Days | 3 | How many consecutive warm days trigger summer mode |

### Installation via HACS

1. Open HACS → Integrations → ⋮ → **Custom Repositories**
2. Enter URL: `https://github.com/Shadowlord31/ha-smart-heating-advisor`
3. Category: **Integration** → Add
4. Search for the integration and click **Download**
5. Restart Home Assistant
6. Go to Settings → Integrations → set up **Smart Heating Advisor**

### Configuration

During setup the following fields are shown:

| Field | Required | Description |
|---|---|---|
| Outdoor Temperature Sensor | ✅ | A single outdoor temperature sensor |
| Indoor Temperature Sensors | ☑️ | Multiple rooms possible, used for trend calculation |
| Window Contacts | ➖ | Optional, prevents heating with open windows |
| Weather Entity | ✅ | Weather entity with daily forecast support |

### Requirements

- Home Assistant 2024.4.1 or newer
- HACS 2.0.0 or newer
- At least one outdoor temperature sensor
- A weather entity with daily forecast support

---

## License

MIT License — see [LICENSE](LICENSE) for details.
