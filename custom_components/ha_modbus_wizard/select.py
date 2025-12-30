"""Dynamic Select entities for Modbus Wizard (HA-recommended pattern)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.components.select import SelectEntity

from .const import DOMAIN, CONF_REGISTERS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )

    entities: dict[str, ModbusWizardSelect] = {}

    def _unique_id(reg: dict[str, Any]) -> str:
        return f"{entry.entry_id}_{reg['address']}_{reg.get('register_type', 'auto')}_select"

    def _key(reg: dict[str, Any]) -> str:
        return reg["name"].lower().strip().replace(" ", "_")

    def _sync_entities() -> None:
        current_regs = entry.options.get(CONF_REGISTERS, [])
        desired_ids = set()
        new_entities: list[Entity] = []

        for reg in current_regs:
            options = reg.get("options")
            if not options:
                continue

            uid = _unique_id(reg)
            desired_ids.add(uid)

            if uid in entities:
                continue

            entity = ModbusWizardSelect(
                coordinator=coordinator,
                entry=entry,
                unique_id=uid,
                key=_key(reg),
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
                hass.async_create_task(entity.async_remove())

        _LOGGER.info("Select sync complete — active=%d", len(entities))

    _sync_entities()
    entry.async_on_unload(entry.add_listener(lambda *_: _sync_entities()))


class ModbusWizardSelect(CoordinatorEntity, SelectEntity):
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
        self._attr_device_info = device_info

        # options expected as mapping {"0": "Off", "1": "On"}
        self._value_map = {str(k): v for k, v in info.get("options", {}).items()}
        self._reverse_map = {v: k for k, v in self._value_map.items()}

        self._attr_options = list(self._reverse_map.keys())

    @property
    def current_option(self):
        raw = self.coordinator.data.get(self._key)
        return self._value_map.get(str(raw))

    async def async_select_option(self, option: str) -> None:
        value = self._reverse_map.get(option)
        if value is None:
            return

        await self.coordinator.async_write_registers(
            address=int(self._info["address"]),
            value=int(value),
            data_type=self._info.get("data_type", "uint16"),
            byte_order=self._info.get("byte_order", "big"),
            word_order=self._info.get("word_order", "big"),
        )
        await self.coordinator.async_request_refresh()
