"""Data update coordinator for Modbus Wizard."""

import logging
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator #, UpdateFailed
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
        self.self._resolved_register_types = {}

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
        new_data = {}
        registers = list(self.config_entry.options.get("registers", []))  # Copy for potential modification
    
        for idx, reg in enumerate(registers):
            key = reg["name"].lower().replace(" ", "_")
            address = reg["address"]
            count = reg.get("size", 1)
            reg_type = reg.get("register_type", "holding")
    
            result = None
    
            try:
                # === AUTO DETECTION ===
                if reg_type == "auto":
                    # Try in order of most common → least common
                    methods = [
                        ("holding", self.client.read_holding_registers),
                        ("input", self.client.read_input_registers),
                        ("coil", self.client.read_coils),
                        ("discrete", self.client.read_discrete_inputs),
                    ]
    
                    success_type = None
                    for name, method in methods:
                        try:
                            if name in ("coil", "discrete"):
                                result = await method(address=address, count=count, slave=self.slave_id)
                            else:
                                result = await method(address=address, count=count, slave=self.slave_id)
    
                            if not result.isError():
                                success_type = name
                                break
                        except Exception:
                            result = None
                            continue
    
                    if success_type:
                        reg_type = success_type
    
                        # Permanently update the register type in config if it was "auto"
                        if registers[idx]["register_type"] == "auto":
                            registers[idx]["register_type"] = success_type
                            # Update the entry options in HA
                            self.hass.config_entries.async_update_entry(
                                self.config_entry,
                                options={**self.config_entry.options, "registers": registers}
                            )
                            _LOGGER.info(
                                "Auto-detected and saved register type '%s' for '%s' (address %d)",
                                success_type,
                                reg["name"],
                                address,
                            )
                    else:
                        _LOGGER.warning(
                            "Auto-detect failed for register '%s' (address %d, size %d)",
                            reg["name"],
                            address,
                            count,
                        )
                        continue  # Skip this register
    
                # === DIRECT READ USING FINAL reg_type ===
                if result is None:
                    if reg_type == "holding":
                        result = await self.client.read_holding_registers(address, count, slave=self.slave_id)
                    elif reg_type == "input":
                        result = await self.client.read_input_registers(address, count, slave=self.slave_id)
                    elif reg_type == "coil":
                        result = await self.client.read_coils(address, count, slave=self.slave_id)
                    elif reg_type == "discrete":
                        result = await self.client.read_discrete_inputs(address, count, slave=self.slave_id)
                    else:
                        _LOGGER.warning("Invalid register type '%s' for '%s'", reg_type, reg["name"])
                        continue
    
                if result.isError():
                    _LOGGER.debug(
                        "Read error for '%s' (%s, addr %d): %s",
                        reg["name"],
                        reg_type,
                        address,
                        result,
                    )
                    continue
    
                # === EXTRACT VALUES ===
                if reg_type in ("coil", "discrete"):
                    values = result.bits[:count]
                else:
                    values = result.registers
    
                if len(values) < count:
                    _LOGGER.warning(
                        "Short read for '%s': expected %d value(s), got %d",
                        reg["name"],
                        count,
                        len(values),
                    )
                    continue
    
                # === DECODE VALUE ===
                decoded = self._decode_value(values, reg["data_type"], count)
                new_data[key] = decoded
    
            except Exception as err:
                _LOGGER.warning("Unexpected error reading register '%s': %s", reg["name"], err)
    
        return new_data
