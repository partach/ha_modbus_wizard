"""Data update coordinator for Modbus Wizard."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
# from pymodbus.exceptions import ModbusException, ConnectionException
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

class ModbusWizardCoordinator(DataUpdateCoordinator):
    """Modbus Wizard Data Update Coordinator."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        client, 
        slave_id: int, 
        config_entry,
        update_interval: timedelta = timedelta(seconds=10),
    ):
        super().__init__(
            hass,
            _LOGGER,
            name="Modbus Wizard",
            update_interval=update_interval,
        )
        self.client = client
        self.slave_id = slave_id
        self.config_entry = config_entry
        self.connected = False
        self.update_interval = update_interval


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
        """Fetch latest data from all configured registers."""
        if not await self._async_connect():
            raise UpdateFailed("Could not connect to Modbus device")
    
        new_data = {}
        registers = self.config_entry.options.get("registers", [])
        updated_registers = [dict(reg) for reg in registers]  # Copy for modification
        options_changed = False
    
        for idx, reg in enumerate(updated_registers):
            key = reg["name"].lower().replace(" ", "_")
            address = int(reg["address"])  # just make sure these are integers else it is an issue
            count = int(reg.get("size", 1))
            reg_type = reg.get("register_type", "holding")
    
            try:
                result = None
    
                # === AUTO DETECTION ===
                if reg_type == "auto":
                    methods = [
                        ("holding", self.client.read_holding_registers),
                        ("input", self.client.read_input_registers),
                        ("coil", self.client.read_coils),
                        ("discrete", self.client.read_discrete_inputs),
                    ]
    
                    success_type = None
                    for name, method in methods:
                        try:
                            result = await method(address=address, count=count, device_id=self.slave_id)
                            if not result.isError():
                                success_type = name
                                break
                        except Exception:
                            continue
    
                    if success_type:
                        reg_type = success_type
                        updated_registers[idx]["register_type"] = success_type
                        options_changed = True
                        _LOGGER.info(
                            "Auto-detected and saved '%s' for register '%s' (addr %d)",
                            success_type, reg["name"], address
                        )
                    else:
                        _LOGGER.warning("Auto-detect failed for '%s' (addr %d)", reg["name"], address)
                        continue  # Skip this register
    
                # === DIRECT READ ===
                if result is None:
                    if reg_type == "holding":
                        result = await self.client.read_holding_registers(address=address, count=count, device_id=self.slave_id)
                    elif reg_type == "input":
                        result = await self.client.read_input_registers(address=address, count=count, device_id=self.slave_id)
                    elif reg_type == "coil":
                        result = await self.client.read_coils(address=address, count=count, device_id=self.slave_id)
                    elif reg_type == "discrete":
                        result = await self.client.read_discrete_inputs(address=address, count=count, device_id=self.slave_id)
                    else:
                        continue
    
                if result.isError():
                    _LOGGER.debug("Read failed for '%s' (%s): %s", reg["name"], reg_type, result)
                    continue
    
                # === EXTRACT AND DECODE ===
                if reg_type in ("coil", "discrete"):
                    values = result.bits[:count]
                else:
                    values = result.registers[:count]  # Safe slice
                if len(values) == 0:
                    continue
    
                decoded = self._decode_value(values, reg.get("data_type", "uint"), len(values))
                new_data[key] = decoded
    
            except Exception as err:
                _LOGGER.warning("Error updating register '%s': %s", reg["name"], err)
                continue
    
        # Save auto-detected types
        if options_changed:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, "registers": updated_registers}
            )
    
        if not new_data:
            raise UpdateFailed("No registers could be read from device")
    
        return new_data
