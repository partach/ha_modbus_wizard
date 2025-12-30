"""Select entities for Modbus Wizard."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, CONF_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Modbus Wizard select entities."""
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title or "Modbus Wizard",
        manufacturer="Partach",
        model="Wizard",
    )
    entities = []

    # Create select entities for writable registers with predefined options
    for reg in entry.options.get("registers", []):
        key = reg["name"].lower().replace(" ", "_")
        
        # Only create select entity if:
        # 1. Register is writable
        # 2. Has predefined options
        if reg.get("rw") != "read" and reg.get("options"):
            entities.append(ModbusWizardSelect(coordinator, entry, key, reg, device_info))
    if entities:
      async_add_entities(entities, update=True)


class ModbusWizardSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Modbus select entity with predefined options."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        info: dict[str, Any],
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry = entry
        self._key = key
        self._info = info
        self._attr_device_info = device_info
        # Entity attributes
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = info["name"]
        self._attr_icon = info.get("icon")

        # Parse options - can be dict {value: label} or list ["opt1", "opt2"]
        options_data = info.get("options", {})
        if isinstance(options_data, dict):
            self._value_to_label = options_data
            self._label_to_value = {v: k for k, v in options_data.items()}
            self._attr_options = list(options_data.values())
        else:
            # List of strings - label and value are the same
            self._value_to_label = {str(i): opt for i, opt in enumerate(options_data)}
            self._label_to_value = {opt: str(i) for i, opt in enumerate(options_data)}
            self._attr_options = list(options_data)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        raw_value = self.coordinator.data.get(self._key)
        if raw_value is None:
            return None

        # Convert raw modbus value to label
        value_str = str(raw_value)
        return self._value_to_label.get(value_str, self._attr_options[0] if self._attr_options else None)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._label_to_value:
            _LOGGER.error("Invalid option '%s' for %s", option, self._attr_name)
            return

        # Get the modbus value for this option
        modbus_value = self._label_to_value[option]

        # Convert to appropriate type based on data_type
        data_type = self._info.get("data_type", "uint16")
        
        try:
            if data_type in ("uint16", "uint32", "uint"):
                modbus_value = int(modbus_value)
            elif data_type in ("int16", "int32", "int"):
                modbus_value = int(modbus_value)
            elif data_type == "float32":
                modbus_value = float(modbus_value)
        except (ValueError, TypeError):
            _LOGGER.error("Could not convert '%s' to %s", modbus_value, data_type)
            return

        # Write to modbus
        success = await self._coordinator.async_write_registers(
            address=self._info["address"],
            value=modbus_value,
            data_type=data_type,
            byte_order=self._info.get("byte_order", "big"),
            word_order=self._info.get("word_order", "big"),
        )

        if not success:
            _LOGGER.error("Failed to write option '%s' to register %d", option, self._info["address"])
            return

        # Refresh coordinator to get updated state
        await self._coordinator.async_request_refresh()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Handle entity added to hass."""
        await super().async_added_to_hass()
        _LOGGER.debug("Select %s added to hass", self._attr_name)
