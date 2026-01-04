"""Data update coordinator for Modbus Wizard."""

from __future__ import annotations

import logging
import asyncio
from typing import Any
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    CONF_ENTITIES, 
    TYPE_SIZES,
    reg_key,
)
from pymodbus.client.mixin import ModbusClientMixin

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
        self.slave_id = int(slave_id)
        self.my_config_entry = config_entry

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
        register_type: str = "auto",
        raw: bool = False,
    ) -> Any | None:
        """Read and optionally decode a register with full options."""
        if not await self._async_connect():
            return None

        # Determine size from data_type if not provided
        if size is None:
            size = int(TYPE_SIZES.get(data_type.lower(), 1))
        result = None

        # === AUTO DETECTION ===
        if not register_type or register_type == "auto":
            methods = [
                ("holding", self.client.read_holding_registers),
                ("input", self.client.read_input_registers),
                ("coil", self.client.read_coils),
                ("discrete", self.client.read_discrete_inputs),
            ]

            for name, method in methods:
                try:
                    result = await method(
                        address=address,
                        count=size,
                        device_id=self.slave_id,
                    )
                    if not result.isError():
                        register_type = name  # Detected type
                        break
                except Exception as inner_err:
                    _LOGGER.debug("Auto test failed for %s at addr %d: %s", name, address, inner_err)
                    result = None

            if result is None or result.isError():
                _LOGGER.warning("Auto-detect failed for address %d (size %d)", address, size)
                return None

        # === DIRECT READ ===
        else:
            method_map = {
                "holding": self.client.read_holding_registers,
                "input": self.client.read_input_registers,
                "coil": self.client.read_coils,
                "discrete": self.client.read_discrete_inputs,
            }
            method = method_map.get(register_type.lower())
            if method is None:
                _LOGGER.error("Invalid register_type: %s", register_type)
                return None

            try:
                result = await method(
                    address=address,
                    count=size,
                    device_id=self.slave_id,
                )
            except Exception as err:
                _LOGGER.error("Read failed for %s register at %d: %s", register_type, address, err)
                return None

            if result.isError():
                return None

        # === RAW MODE ===
        if raw:
            return {
                "registers": getattr(result, "registers", []), # default data word, not part of options
                "bits": getattr(result, "bits", [])[:size],
                "detected_type": register_type,
            }

        # === DECODE VALUES ===
        if register_type in ("coil", "discrete"):
            values = result.bits[:size]
        else:
            values = result.registers[:size]

        if not values:
            return None

        return self._decode_value(
            values,
            data_type,
            byte_order,
            word_order,
        )

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Fetch latest data from configured entities."""
        if not await self._async_connect():
            _LOGGER.warning("Could not connect to Modbus device")
            return {}
    
        entities = self.my_config_entry.options.get(CONF_ENTITIES, [])
        if not entities:
            return {}
        
        updated_entities = [dict(reg) for reg in entities]
        options_changed = False
        new_data = {}
    
        async with self._lock:
            for idx, reg in enumerate(updated_entities):
                key = reg_key(reg["name"])
                address = int(reg["address"])
                count = int(reg.get("size", TYPE_SIZES.get(reg["data_type"], 1)))
                reg_type = reg.get("register_type", "holding")
    
                result = None
                try:
                    # -------- AUTO DETECT --------
                    if reg_type == "auto":
                        methods = [
                            ("holding", self.client.read_holding_registers),
                            ("input", self.client.read_input_registers),
                        ]
                        if reg.get("allow_bits", False):
                            methods += [
                                ("coil", self.client.read_coils),
                                ("discrete", self.client.read_discrete_inputs),
                            ]
                        for name, method in methods:
                            try:
                                result = await method(
                                    address=address,
                                    count=count,
                                    device_id=self.slave_id,
                                )
                                if not result.isError():
                                    if name in ("holding", "input") and not hasattr(result, "registers"):
                                        continue
                                    if name in ("coil", "discrete") and not hasattr(result, "bits"):
                                        continue                              
                                    reg_type = name
                                    updated_entities[idx]["register_type"] = name
                                    options_changed = True
                                    break
                            except Exception:
                                continue
    
                        if reg_type == "auto":
                            _LOGGER.warning("Auto-detect failed for register '%s' at address %s", reg["name"], address)
                            continue
    
                    # -------- DIRECT READ --------
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
                            _LOGGER.error("Unknown register_type '%s' for register '%s'", reg_type, reg["name"])
                            continue
    
                    if result.isError():
                        _LOGGER.warning("Read failed for '%s' (type=%s, addr=%s): %s", reg["name"], reg_type, address, result)
                        continue
    
                    # Extract values based on type
                    if reg_type in ("coil", "discrete"):
                        values = result.bits[:count]
                    else:
                        values = result.registers[:count]
    
                    if not values:
                        _LOGGER.warning("No values returned for register '%s'", reg["name"])
                        continue
    
                    # Decode the values
                    decoded = self._decode_value(
                        values,
                        reg.get("data_type", "uint16"),
                        reg.get("byte_order", "big"),
                        reg.get("word_order", "big"),
                        reg=reg,
                    )
                    
                    if decoded is not None:
                        new_data[key] = decoded
                    else:
                        _LOGGER.warning("Decode returned None for register '%s'", reg["name"])
    
                except Exception as err:
                    _LOGGER.error("Error updating register '%s': %s", reg.get("name"), err, exc_info=True)
    
        if options_changed:
            _LOGGER.info("Detected register types updated; will take effect after options reload")
    
        if not new_data:
            _LOGGER.debug("No register values produced in this update cycle")
        return new_data

    # ------------------------------------------------------------------
    # De/encoding (Using Pymodbus Mixin String-based Endianness)
    # ------------------------------------------------------------------
    def _decode_value(
        self,
        values: list[int] | list[bool],
        data_type: str,
        byte_order: str = "big",
        word_order: str = "big",
        reg: dict | None = None,
    ) -> Any | None:
        """Decode registers or bits using the modern client mixin."""
        if not values:
            return None
        
        try:
            dt = data_type.lower()
        
            # Special handling for bit-based registers (coil/discrete)
            if isinstance(values[0], bool):
                if len(values) == 1:
                    decoded = bool(values[0])
                else:
                    # Multi-bit → pack into integer (big-endian bit order)
                    decoded = int("".join("1" if b else "0" for b in values[::-1]), 2)
                
                # Don't apply scale/offset to boolean values
                return decoded
            
            # For single register types (uint16, int16), no conversion needed
            if dt in ("uint16", "int16") and len(values) == 1:
                decoded = values[0]
                # Convert uint16 to int16 if needed
                if dt == "int16" and decoded > 32767:
                    decoded = decoded - 65536
            else:
                # For multi-register types, use convert_from_registers
                # Map data_type to DATATYPE enum
                dt_map = {
                    "uint16": ModbusClientMixin.DATATYPE.UINT16,
                    "int16": ModbusClientMixin.DATATYPE.INT16,
                    "uint32": ModbusClientMixin.DATATYPE.UINT32,
                    "int32": ModbusClientMixin.DATATYPE.INT32,
                    "float32": ModbusClientMixin.DATATYPE.FLOAT32,
                    "uint64": ModbusClientMixin.DATATYPE.UINT64,
                    "int64": ModbusClientMixin.DATATYPE.INT64,
                    "string": ModbusClientMixin.DATATYPE.STRING,
                }
                target_type = dt_map.get(dt, ModbusClientMixin.DATATYPE.UINT16)
            
                try:
                    # pymodbus 3.10+ uses word_order parameter
                    # byte order is always big-endian per Modbus standard
                    decoded = self.client.convert_from_registers(
                        registers=values,
                        data_type=target_type,
                        word_order=0 if word_order.lower() == "big" else 1,  # 0=big, 1=little
                    )
                except Exception as err:
                    _LOGGER.warning("Failed to decode %s as %s: %s", values, data_type, err)
                    return None
        
            # Post-processing
            if dt == "float32" and isinstance(decoded, float):
                decoded = round(decoded, 6)
            if dt == "string" and isinstance(decoded, str):
                decoded = decoded.rstrip("\x00")
        
            # Apply scale and offset (after decoding, but NOT for booleans/strings)
            if reg is not None and isinstance(decoded, (int, float)):
                scale = reg.get("scale", 1.0)
                offset = reg.get("offset", 0.0)
                decoded = decoded * scale + offset
        
            return decoded
            
        except Exception as err:
            _LOGGER.error(
                "Error decoding register '%s' at address %s: %s",
                reg.get("name") if reg else "unknown",
                reg.get("address") if reg else "unknown",
                err
            )
            return None
    
    
    def _encode_value(
        self,
        value,
        data_type: str,
        byte_order: str = "big",
        word_order: str = "big",
        reg: dict | None = None,
    ) -> list[int]:
        """Encode value to registers using the modern client mixin."""
        dt = data_type.lower()
        
        # Reverse scale/offset before encoding
        if reg is not None:
            scale = reg.get("scale", 1.0)
            offset = reg.get("offset", 0.0)
            if scale != 0 and isinstance(value, (int, float)):
                value = (value - offset) / scale
        
        # For uint16/int16, handle directly
        if dt in ("uint16", "int16"):
            if isinstance(value, float):
                value = int(round(value))
            
            # Convert int16 to uint16 if negative
            if dt == "int16" and value < 0:
                value = value + 65536
            
            # Clamp to valid range
            value = max(0, min(65535, value))
            return [value]
        
        # For multi-register types, use convert_to_registers
        dt_map = {
            "uint32": ModbusClientMixin.DATATYPE.UINT32,
            "int32": ModbusClientMixin.DATATYPE.INT32,
            "float32": ModbusClientMixin.DATATYPE.FLOAT32,
            "uint64": ModbusClientMixin.DATATYPE.UINT64,
            "int64": ModbusClientMixin.DATATYPE.INT64,
        }
        target_type = dt_map.get(dt, ModbusClientMixin.DATATYPE.UINT16)
    
        if target_type != ModbusClientMixin.DATATYPE.FLOAT32:
            if isinstance(value, float):
                value = int(round(value))
        else:
            value = float(value)    
    
        try:
            return self.client.convert_to_registers(
                value=value,
                data_type=target_type,
                word_order=0 if word_order.lower() == "big" else 1,  # 0=big, 1=little
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to encode %s as %s (word=%s): %s",
                value, data_type, word_order, err,
            )
            return None

