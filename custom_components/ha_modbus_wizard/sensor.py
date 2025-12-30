"""Dynamic entities for Modbus Wizard."""
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_REGISTERS #, CONF_NAME
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):

    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )    
    def update_entities():
        entities = []
        registers = entry.options.get(CONF_REGISTERS, [])
        for reg in registers:
            key = reg["name"].lower().replace(" ", "_")
            if reg.get("rw", "read") == "read":
                entities.append(ModbusWizardSensor(coordinator, entry, key, reg, device_info))
        if entities:
            async_add_entities(entities, update=True)  # Replace existing with same unique_id
        _LOGGER.info("update_entities called — registers: %s", len(entry.options.get(CONF_REGISTERS, [])))

    # Initial setup
    update_entities()
    # Whenever options change (user adds/deletes registers) → recreate entities
    entry.async_on_unload(entry.add_listener(update_entities))
    
class ModbusWizardSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        info: dict[str, Any],
        device_info: DeviceInfo,
    ):
        super().__init__(coordinator)
        self._key = key
        self._info = info
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_device_class = info.get("device_class")
        self._attr_native_unit_of_measurement = info.get("unit")
        self._attr_entity_category = None
        self._attr_device_info = device_info
#        if info.get("state_class"):
#            self._attr_state_class = getattr(SensorStateClass, info["state_class"].upper())
    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)
        
    @property
    def available(self):
        return self.coordinator.last_update_success and self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Sensor %s added to hass", self._attr_name)
