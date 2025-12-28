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
                await self.client.connect()
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

    async def _async_update_data(self) -> dict:
        """Fetch data from registers in options."""
        if not await self._async_connect():
            raise UpdateFailed("Cannot connect")

        registers = self.config_entry.options.get("registers", [])
        new_data = {}

        for reg in registers:
            address = reg["address"]
            size = reg["size"]
            key = reg["name"].lower().replace(" ", "_")
            
            try:
                result = await self.client.read_holding_registers(address, size, device_id=self.slave_id)
                if result.isError():
                    continue
                
                raw = 0  # Decode based on data_type
                if reg["data_type"] == "uint" and size == 1:
                    raw = result.registers[0]
                # Add more decoding...
                
                new_data[key] = raw
            except Exception as err:
                _LOGGER.warning("Read error for %s: %s", key, err)

        return new_data
