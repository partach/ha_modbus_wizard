"""Dynamic entities for Modbus Wizard (HA-recommended pattern)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_REGISTERS, reg_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up dynamic Modbus Wizard sensor entities."""

    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )

    # Registry of active entities for this config entry
    entities: dict[str, ModbusWizardSensor] = {}
    ent_reg = er.async_get(hass)

    def _entity_unique_id(reg: dict[str, Any]) -> str:
        """Stable unique_id independent of display name changes."""
        return f"{entry.entry_id}_{reg['address']}_{reg.get('register_type', 'auto')}"

    async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        await _sync_entities()
    
    async def _sync_entities() -> None:
        """Create, update and remove entities based on options."""
        current_regs = entry.options.get(CONF_REGISTERS, [])
        desired_ids = set()

        # ---- ADD / KEEP ----
        new_entities: list[Entity] = []
        for reg in current_regs:
            if reg.get("rw", "read") not in ("read", "rw"):
                continue

            unique_id = _entity_unique_id(reg)
            desired_ids.add(unique_id)

            if unique_id in entities:
                # Entity already exists → nothing to do
                continue

            entity = ModbusWizardSensor(
                coordinator=coordinator,
                entry=entry,
                unique_id=unique_id,
                key=reg_key(reg["name"]),
                info=reg,
                device_info=device_info,
            )

            entities[unique_id] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)
            _LOGGER.debug("Added %d Modbus Wizard entities", len(new_entities))

        # ---- REMOVE ----
        for uid in list(entities):
            if uid not in desired_ids:
                entity = entities.pop(uid)
                if entity.entity_id:
                    ent_reg.async_remove(entity.entity_id)
                    _LOGGER.debug("Removed entity registry entry %s", entity.entity_id)
                await entity.async_remove()

        _LOGGER.info(
            "Entity sync complete — active=%d, defined=%d",
            len(entities),
            len(current_regs),
        )

    # Initial sync
    await _sync_entities()

    # Re-sync on options change
    remove_listener = entry.add_update_listener(_handle_options_update)
    entry.async_on_unload(remove_listener)


class ModbusWizardSensor(CoordinatorEntity, SensorEntity):
    """Single Modbus register sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        unique_id: str,
        key: str,
        info: dict[str, Any],
        device_info: DeviceInfo,
    ):
        super().__init__(coordinator)
        self._key = key
        self._info = info

        self._attr_unique_id = unique_id
        self._attr_name = info.get("name")
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_device_class = info.get("device_class")
        self._attr_device_info = device_info

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        _LOGGER.debug("Sensor added: %s (%s)", self.name, self.unique_id)
