"""Dynamic entities for Modbus Wizard."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data["modbus_wizard"][entry.entry_id]
    
    entities = []
    for reg in entry.options.get("registers", []):
        key = reg["name"].lower().replace(" ", "_")
        if reg["rw"] == "read":
            entities.append(ModbusWizardSensor(coordinator, entry, key, reg))
        # Add number/select for write...

    async_add_entities(entities)

class ModbusWizardSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, info):
        super().__init__(coordinator)
        self._key = key
        self._info = info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_device_class = info.get("device_class")
        self._attr_native_unit_of_measurement = info.get("unit")

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
