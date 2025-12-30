"""Data update coordinator for Modbus Wizard."""

from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from pymodbus.constants import Endian
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    async def _async_connect(self) -> bool:
        """Ensure Modbus client is connected."""
        if self.client.connected:
            return True

        try:
            await self.client.connect()
            return self.client.connected
        except Exception as err:
            _LOGGER.error("Failed to connect to Modbus device: %s", err)
            return False

    # ------------------------------------------------------------------
    # Services API
    # ------------------------------------------------------------------

    async def async_write_registers(
        self,
        address: int,
        value,
        data_type: str = "uint16",
        byte_order: str = "big",
        word_order: str = "big",
    ) -> bool:
        try:
            registers = self._encode_value(
                value,
                data_type,
                byte_order,
                word_order,
            )
    
            result = await self.client.write_registers(
                address=address,
                values=registers,
                device_id=self.slave_id,
            )
    
            return not result.isError()
    
        except Exception as err:
            _LOGGER.error("Write error at %s: %s", address, err)
            return False

    async def async_read_registers(self, address: int, size: int = 1):
        """Read holding registers."""
        if not await self._async_connect():
            return None

        async with self._lock:
            try:
                result = await self.client.read_holding_registers(
                    address=address,
                    count=size,
                    device_id=self.slave_id,
                )

                if result.isError():
                    return None

                return result.registers[0] if size == 1 else result.registers

            except Exception as err:
                _LOGGER.error("Read error at %s: %s", address, err)
                return None

    async def async_read_typed(
        self,
        address: int,
        data_type: str,
        byte_order: str = "big",
        word_order: str = "big",
        size: int | None = None,
        register_type: str = "holding",
        raw: bool = False,
    ):
        """Read and optionally decode a register with full options."""
        if not await self._async_connect():
            return None
    
        # Determine size from data_type if not provided
        if size is None:
            type_sizes = {
                "uint16": 1, "int16": 1,
                "uint32": 2, "int32": 2, "float32": 2,
                "uint64": 4, "int64": 4,
            }
            size = type_sizes.get(data_type, 1)
    
        async with self._lock:
            result = None
    
            # Auto or direct type
            if register_type == "auto":
                # Reuse your auto-detect logic here (or call a helper)
                result = await self._auto_read(address, size)
            else:
                method_map = {
                    "holding": self.client.read_holding_registers,
                    "input": self.client.read_input_registers,
                    "coil": self.client.read_coils,
                    "discrete": self.client.read_discrete_inputs,
                }
                method = method_map.get(register_type)
                if not method:
                    _LOGGER.error("Invalid register_type: %s", register_type)
                    return None
                result = await method(address=address, count=size, unit=self.slave_id)
    
            if result.isError():
                return None
    
            if raw:
                return {
                    "registers": result.registers if hasattr(result, "registers") else [],
                    "bits": result.bits if hasattr(result, "bits") else [],
                }
    
            values = result.registers if hasattr(result, "registers") else result.bits[:size]
    
            return self._decode_value(values, data_type, byte_order, word_order)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Fetch latest data from configured registers."""
        if not await self._async_connect():
            raise UpdateFailed("Could not connect to Modbus device")

        registers = self.config_entry.options.get("registers", [])
        updated_registers = [dict(reg) for reg in registers]
        options_changed = False
        new_data = {}

        async with self._lock:
            for idx, reg in enumerate(updated_registers):
                try:
                    key = reg["name"].lower().replace(" ", "_")
                    address = int(reg["address"])
                    count = int(reg.get("size", 1))
                    reg_type = reg.get("register_type", "holding")

                    result = None

                    # -------- AUTO DETECT --------
                    if reg_type == "auto":
                        for name, method in (
                            ("holding", self.client.read_holding_registers),
                            ("input", self.client.read_input_registers),
                            ("coil", self.client.read_coils),
                            ("discrete", self.client.read_discrete_inputs),
                        ):
                            try:
                                result = await method(
                                    address=address,
                                    count=count,
                                    device_id=self.slave_id,
                                )
                                if not result.isError():
                                    reg_type = name
                                    updated_registers[idx]["register_type"] = name
                                    options_changed = True
                                    break
                            except Exception:
                                continue

                        if reg_type == "auto":
                            continue

                    # -------- DIRECT READ --------
                    if result is None:
                        if reg_type == "holding":
                            result = await self.client.read_holding_registers(address, count, device_id=self.slave_id)
                        elif reg_type == "input":
                            result = await self.client.read_input_registers(address, count, device_id=self.slave_id)
                        elif reg_type == "coil":
                            result = await self.client.read_coils(address, count, device_id=self.slave_id)
                        elif reg_type == "discrete":
                            result = await self.client.read_discrete_inputs(address, count, device_id=self.slave_id)
                        else:
                            continue

                    if result.isError():
                        continue

                    values = (
                        result.bits[:count]
                        if reg_type in ("coil", "discrete")
                        else result.registers[:count]
                    )

                    if not values:
                        continue

                    new_data[key] = self._decode_value(
                        values,
                        reg.get("data_type", "uint16"),
                        reg.get("byte_order", "big"),
                        reg.get("word_order", "big"),
                    )

                except Exception as err:
                    _LOGGER.warning("Error updating register '%s': %s", reg.get("name"), err)

        if options_changed:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, "registers": updated_registers},
            )

        if not new_data:
            raise UpdateFailed("No registers could be read")

        return new_data

    # ------------------------------------------------------------------
    # De/encoding
    # ------------------------------------------------------------------
    def _decode_value(self, registers, data_type, byte_order="big", word_order="big"):
        """Decode registers using client mixin."""
        # Simple bit-based types (Coils/Discrete) don't need decoding
        if not isinstance(registers, list) or len(registers) == 0:
            return registers

        # Determine Pymodbus DATATYPE Enum
        dt_map = {
            "uint16": self.client.DATATYPE.UINT16,
            "int16": self.client.DATATYPE.INT16,
            "uint32": self.client.DATATYPE.UINT32,
            "int32": self.client.DATATYPE.INT32,
            "float32": self.client.DATATYPE.FLOAT32,
            "uint": self.client.DATATYPE.UINT16 if len(registers) == 1 else self.client.DATATYPE.UINT32,
            "int": self.client.DATATYPE.INT16 if len(registers) == 1 else self.client.DATATYPE.INT32,
        }
        
        target_type = dt_map.get(data_type, self.client.DATATYPE.UINT16)
        
        decoded = self.client.convert_from_registers(
            registers,
            data_type=target_type,
            byte_order=Endian.BIG if byte_order == "big" else Endian.LITTLE,
            word_order=Endian.BIG if word_order == "big" else Endian.LITTLE,
        )

        if data_type == "float32":
            return round(decoded, 6)
        return decoded

    def _encode_value(self, value, data_type, byte_order="big", word_order="big"):
        """Encode value to registers using client mixin."""
        dt_map = {
            "uint16": self.client.DATATYPE.UINT16,
            "int16": self.client.DATATYPE.INT16,
            "uint32": self.client.DATATYPE.UINT32,
            "int32": self.client.DATATYPE.INT32,
            "float32": self.client.DATATYPE.FLOAT32,
        }

        target_type = dt_map.get(data_type, self.client.DATATYPE.UINT16)

        return self.client.convert_to_registers(
            value,
            data_type=target_type,
            byte_order=Endian.BIG if byte_order == "big" else Endian.LITTLE,
            word_order=Endian.BIG if word_order == "big" else Endian.LITTLE,
        )
