"""Switch-Entitaeten fuer Smart Heating Advisor (Wartung & Schornsteinfeger)."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_MAINTENANCE_BOOLEANS, SWITCH_CHIMNEY_SWEEP
from .coordinator import SmartHeatingCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SmartHeatingCoordinator = hass.data[DOMAIN][entry.entry_id]

    switch_store = hass.data[DOMAIN].setdefault(f"{entry.entry_id}_switches", {})
    switch_store.setdefault(SWITCH_CHIMNEY_SWEEP, False)

    entities: list[SwitchEntity] = [
        SHAChimneySweepSwitch(coordinator, entry),
    ]

    config = {**entry.data, **entry.options}
    maintenance_targets = config.get(CONF_MAINTENANCE_BOOLEANS, [])

    for target_entity_id in maintenance_targets:
        entities.append(SHAMaintenanceSwitch(coordinator, entry, target_entity_id))

    async_add_entities(entities)


class _SHASwitchBase(CoordinatorEntity, SwitchEntity):
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Smart Heating Advisor",
            "manufacturer": "Shadowlord31",
        }


class SHAChimneySweepSwitch(_SHASwitchBase):
    """Globaler Schornsteinfeger-Modus.

    Setzt bewusst NICHT selbst an Thermostaten – dieser Schalter ist nur das
    Signal. Eine eigene Automation im Haupt-HA reagiert auf den Zustand und
    fährt alle Thermostate auf Vollast. Der Zustand wird bewusst NICHT über
    Neustarts hinweg wiederhergestellt (Sicherheit: nach einem HA-Neustart
    ist der Modus immer aus und muss aktiv neu gestartet werden).
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Schornsteinfeger-Modus"
        self._attr_unique_id = f"{entry.entry_id}_{SWITCH_CHIMNEY_SWEEP}"
        self._attr_icon = "mdi:fire"

    @property
    def _store(self) -> dict:
        return self.hass.data[DOMAIN].get(f"{self._entry.entry_id}_switches", {})

    @property
    def is_on(self) -> bool:
        return bool(self._store.get(SWITCH_CHIMNEY_SWEEP, False))

    async def async_turn_on(self, **kwargs) -> None:
        _LOGGER.warning(
            "Schornsteinfeger-Modus AKTIVIERT – alle verwalteten Thermostate "
            "werden auf Vollast gefahren, bis der Schalter wieder ausgeschaltet wird."
        )
        self._store[SWITCH_CHIMNEY_SWEEP] = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        _LOGGER.info("Schornsteinfeger-Modus deaktiviert.")
        self._store[SWITCH_CHIMNEY_SWEEP] = False
        self.async_write_ha_state()


class SHAMaintenanceSwitch(_SHASwitchBase):
    """Gezielter Wartungsschalter fuer EIN Thermostat/Raum.

    Spiegelt und steuert ein bestehendes input_boolean (z.B.
    input_boolean.heizung_wz_manuell), das von den Heizungsautomationen im
    Haupt-HA bereits als Automatik-Aus-Bedingung respektiert wird. Diese
    Entitaet ruft nie direkt eine climate-Service auf – sie ist ein reiner
    Proxy auf das Ziel-Helper, damit man Wartung pro Raum bequem aus der
    SHA-Integration heraus schalten kann.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, target_entity_id: str):
        super().__init__(coordinator)
        self._entry = entry
        self._target_entity_id = target_entity_id
        self._attr_unique_id = f"{entry.entry_id}_wartung_{target_entity_id}"
        self._attr_icon = "mdi:wrench"
        self._attr_is_on = False
        self._update_name_and_state()

    def _update_name_and_state(self) -> None:
        target_state = self.hass.states.get(self._target_entity_id) if self.hass else None
        label = (
            target_state.attributes.get("friendly_name")
            if target_state
            else self._target_entity_id
        )
        self._attr_name = f"Wartung: {label}"
        if target_state is not None:
            self._attr_is_on = target_state.state == "on"

    @property
    def is_on(self) -> bool:
        return self._attr_is_on

    async def async_turn_on(self, **kwargs) -> None:
        await self.hass.services.async_call(
            "input_boolean", "turn_on",
            {"entity_id": self._target_entity_id},
            blocking=True,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self.hass.services.async_call(
            "input_boolean", "turn_off",
            {"entity_id": self._target_entity_id},
            blocking=True,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._update_name_and_state()
        self.async_write_ha_state()

        @callback
        def _target_changed(event) -> None:
            self._update_name_and_state()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._target_entity_id], _target_changed
            )
        )
