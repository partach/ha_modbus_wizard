"""Number entities for Modbus Wizard."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    
    entities = [
        ModbusWizardNumber(coordinator, entry, reg["name"].lower().replace(" ", "_"), reg)
        for reg in entry.options.get("registers", [])
        if reg.get("rw") != "read" and reg.get("data_type") in ("uint16", "int16", "uint32", "int32", "float32")
    ]
    
    async_add_entities(entities)

class ModbusWizardNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry, key, info):
        super().__init__(coordinator)
        self._key = key
        self._info = info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_native_min_value = info.get("min", 0)
        self._attr_native_max_value = info.get("max", 65535)
        self._attr_native_step = info.get("step", 1)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Modbus Device"),
            "manufacturer": "Partach",
            "model": "Wizard",
        }
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

