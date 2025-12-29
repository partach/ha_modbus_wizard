"""Data update coordinator for Modbus Wizard."""

import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
# from pymodbus.exceptions import ModbusException, ConnectionException

_LOGGER = logging.getLogger(__name__)

class ModbusWizardCoordinator(DataUpdateCoordinator):
    """Modbus Wizard Data Update Coordinator."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        client, 
        slave_id: int, 
        config_entry,
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Modbus Wizard",
            update_interval=timedelta(seconds=10),  # From options later
        )
        self.client = client
        self.slave_id = slave_id
        self.config_entry = config_entry
        self.connected = False

    async def _async_connect(self) -> bool:
        if not self.connected:
            try:
                self.client.connect()
                self.connected = self.client.connected
            except Exception as err:
                _LOGGER.error("Failed to connect: %s", err)
                return False
        return self.connected

    async def async_write_registers(self, address: int, value, size: int = 1) -> bool:
        """Write to registers."""
        # Generalize value to list based on size/type
        values = [value] if size == 1 else []  # Implement packing
        try:
            result = await self.client.write_registers(address, values, device_id=self.slave_id)
            return not result.isError()
        except Exception as err:
            _LOGGER.error("Write error: %s", err)
            return False

    async def async_read_registers(self, address: int, size: int = 1):
        """Read holding registers."""
        try:
            result = await self.client.read_holding_registers(
                address=address,
                count=size,
                device_id=self.slave_id,
            )
    
            if result.isError():
                return None
    
            # Return scalar for size=1, list otherwise
            if size == 1:
                return result.registers[0]
    
            return result.registers

        except Exception as err:
            _LOGGER.error("Read error: %s", err)
            return None
            
    async def _async_update_data(self) -> dict:
        new_data = {}
    
        registers = self.config_entry.options.get("registers", [])
        for reg in registers:
            key = reg["name"].lower().replace(" ", "_")
            address = reg["address"]
            size = reg["size"]
            reg_type = reg["register_type"]
    
            try:
                if reg_type == "holding":
                    result = await self.client.read_holding_registers(address, size, slave=self.slave_id)
                elif reg_type == "input":
                    result = await self.client.read_input_registers(address, size, slave=self.slave_id)
                elif reg_type == "coil":
                    result = await self.client.read_coils(address, size, slave=self.slave_id)
                elif reg_type == "discrete":
                    result = await self.client.read_discrete_inputs(address, size, slave=self.slave_id)
                else:
                    _LOGGER.warning("Invalid register type %s for %s", reg_type, key)
                    continue
    
                if result.isError():
                    _LOGGER.warning("Read error for %s at %d", key, address)
                    continue
    
                # Decode based on data_type (your existing logic, e.g., uint/int/float)
                if reg_type in ("holding", "input"):
                    values = result.registers  # words
                else:
                    values = result.bits  # bits (for coil/discrete)
    
                # Apply decoding (expand as needed for bits vs words)
                decoded = self._decode_value(values, reg["data_type"], size)
                new_data[key] = decoded
    
            except Exception as err:
                _LOGGER.warning("Update failed for %s: %s", key, err)
    
        return new_data
