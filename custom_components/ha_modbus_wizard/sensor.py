"""Dynamic entities for Modbus Wizard."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo #, EntityCategory
from .const import DOMAIN,CONF_NAME
import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.error(
        "sensor setup entry %s, registers=%s",
        entry.entry_id,
        entry.options.get("registers"),
    )
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    
    entities = []
    for reg in entry.options.get("registers", []):
        key = reg["name"].lower().replace(" ", "_")
        if reg["rw"] == "read":
            entities.append(ModbusWizardSensor(coordinator, entry, key, reg))
 
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        configuration_url=f"homeassistant://config/integrations/integration/{entry.entry_id}",
    )
    for entity in entities:
        entity._attr_device_info = device_info
    async_add_entities(entities,True)

class ModbusWizardSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, info):
        super().__init__(coordinator)
        self._key = key
        self._info = info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_device_class = info.get("device_class")
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.data.get(CONF_NAME, "Modbus Device"),
            "manufacturer": "Modbus",
            "model": "Wizard",
        }
        
    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
        
    @property
    def available(self):
        return self.coordinator.last_update_success
