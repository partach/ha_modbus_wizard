"""Number entities for Modbus Wizard."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN #, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from typing import Any
import logging
from .const import CONF_REGISTERS 

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )

    # Initial entity creation
    def update_entities():
        entities = []
        registers = entry.options.get(CONF_REGISTERS, [])
        for reg in registers:
            key = reg["name"].lower().replace(" ", "_")
            if reg.get("rw") != "read" and reg.get("data_type") in ("uint16", "int16", "uint32", "int32", "float32"):
                entities.append(ModbusWizardNumber(coordinator, entry, key, reg, device_info))
        if entities:
            async_add_entities(entities, update=True)  # Replace existing with same unique_id

    # Initial setup
    update_entities()

    # Listen for options changes to dynamically update entities
    entry.async_on_unload(
        entry.add_listener(update_entities)
    )

class ModbusWizardNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    
    def __init__(self, coordinator, entry: ConfigEntry, key: str, info: dict[str, Any], device_info: DeviceInfo):
        super().__init__(coordinator)
        self._key = key
        self._info = info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_native_min_value = info.get("min", 0)
        self._attr_native_max_value = info.get("max", 65535)
        self._attr_native_step = info.get("step", 1)
        self._attr_device_info = device_info
    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)

    async def async_set_native_value(self, value: float):
        await self.coordinator.async_write_registers(
            address=self._info["address"],
            value=value,
            data_type=self._info.get("data_type", "uint16"),
        )
        await self.coordinator.async_request_refresh()
            
    @property
    def available(self):
        return self.coordinator.last_update_success
        
    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Number %s added to hass", self._attr_name)
