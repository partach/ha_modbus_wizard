"""Dynamic Number entities for Modbus Wizard (HA-recommended pattern)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.components.number import NumberEntity
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, CONF_REGISTERS, reg_key

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )

    entities: dict[str, ModbusWizardNumber] = {}
    ent_reg = er.async_get(hass)

    def _unique_id(reg: dict[str, Any]) -> str:
        return f"{entry.entry_id}_{reg['address']}_{reg.get('register_type', 'auto')}_number"

    async def _sync_entities() -> None:
        current_regs = entry.options.get(CONF_REGISTERS, [])
        desired_ids = set()
        new_entities: list[Entity] = []

        for reg in current_regs:
            if reg.get("rw") not in ("write", "rw"):
                continue

            uid = _unique_id(reg)
            desired_ids.add(uid)

            if uid in entities:
                continue

            entity = ModbusWizardNumber(
                coordinator=coordinator,
                entry=entry,
                unique_id=uid,
                key=reg_key(reg["name"]),
                info=reg,
                device_info=device_info,
            )
            entities[uid] = entity
            new_entities.append(entity)

        if new_entities:
            async_add_entities(new_entities)

        for uid in list(entities):
            if uid not in desired_ids:
                entity = entities.pop(uid)
                if entity.entity_id:
                    ent_reg.async_remove(entity.entity_id)
                    _LOGGER.debug("Removed entity registry entry %s", entity.entity_id)
                await entity.async_remove()

       # _LOGGER.debug("Number sync complete — active=%d", len(entities))

    async def _handle_options_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
        await _sync_entities()
    
    # only happens on init:   
    await _sync_entities()
    
    remove_listener = entry.add_update_listener(_handle_options_update)
    entry.async_on_unload(remove_listener)


class ModbusWizardNumber(CoordinatorEntity, NumberEntity):
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
        self._attr_device_info = device_info

        self._attr_min_value = info.get("min")
        self._attr_max_value = info.get("max")
        self._attr_step = info.get("step", 1)
        # Add display precision - default to 2 decimal places for floats
        if info.get("data_type") == "float32":
            self._attr_suggested_display_precision = info.get("precision", 2)
        elif info.get("data_type") in ("uint16", "int16", "uint32", "int32"):
            self._attr_suggested_display_precision = 0  # No decimals for integers

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        if self._info.get("rw") not in ("write", "rw"):
            _LOGGER.warning(
                "Blocked write to read-only register %s",
                self._info.get("name"),
            )
            return
        dt = self._info.get("data_type", "uint16").lower()
        if not dt.startswith("float"):
            value = int(round(value))
        await self.coordinator.async_write_registers(
            address=int(self._info["address"]),
            value=value,
            data_type=self._info.get("data_type", "uint16"),
            byte_order=self._info.get("byte_order", "big"),
            word_order=self._info.get("word_order", "big"),
        )
        await self.coordinator.async_request_refresh()
