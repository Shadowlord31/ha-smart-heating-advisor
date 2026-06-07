# Smart Heating Advisor

Home Assistant Custom Integration fuer intelligente, vorausschauende Heizungsempfehlungen.

## Features

- **Heizrelevante Aussentemperatur** – bereinigt um Wetterbedingungen, Tagestrend und Morgenvorhersage
- **Heizempfehlung** – basierend auf Innen- und Aussentemperatur, Forecast und Fensterstatus
- **Sommermodus-Erkennung** – automatisch aktiv wenn mehrere warme Tage vorhergesagt werden
- **Konfidenz-Sensor** – wie sicher ist die Empfehlung (0-100%)
- **Empfohlene Zieltemperatur**

## Entitaeten

| Entitaet | Typ | Beschreibung |
|---|---|---|
| `sensor.heizrelevante_aussentemperatur` | Sensor | Berechnete Aussentemperatur |
| `sensor.empfohlene_heiztemperatur` | Sensor | Zieltemperatur-Empfehlung |
| `sensor.heizempfehlung_konfidenz` | Sensor | Konfidenz in % |
| `sensor.heizempfehlung_begruendung` | Sensor | Textuelle Begruendung |
| `sensor.durchschnittliche_innentemperatur` | Sensor | Ø Innentemperatur |
| `sensor.minimale_innentemperatur` | Sensor | Kaeltester Raum |
| `binary_sensor.heizen_empfohlen` | BinarySensor | Heizen ja/nein |
| `binary_sensor.sommermodus_aktiv` | BinarySensor | Sommermodus aktiv |
| `binary_sensor.fenster_geoeffnet_heizung` | BinarySensor | Fenster offen |

## Installation

1. Dieses Repository als Custom Repository in HACS hinzufuegen
2. Integration installieren
3. HA neu starten
4. Unter Einstellungen → Integrationen → Smart Heating Advisor einrichten

## Konfiguration

| Parameter | Beschreibung | Standard |
|---|---|---|
| Aussentemperatursensor | Pflichtfeld | – |
| Innentemperatursensoren | Mehrere Raeume moeglich | – |
| Wetter-Entity | Fuer Mehrtages-Forecast | – |
| Fenstersensoren | Optional | – |
| Heizschwelle | Ab welcher Aussentemp. heizen | 15°C |
| Mindest-Innentemperatur | Untergrenze Innentemp. | 20°C |
| Sommermodus-Tage | Wie viele warme Tage = Sommer | 3 |
