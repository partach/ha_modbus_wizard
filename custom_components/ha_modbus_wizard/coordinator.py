"""Data update coordinator for Modbus Wizard."""

from __future__ import annotations

import logging
import asyncio
from typing import Any
from datetime import timedelta
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
            type_sizes = {
                "uint16": 1, "int16": 1,
                "uint32": 2, "int32": 2, "float32": 2,
                "uint64": 4, "int64": 4,
            }
            size = type_sizes.get(data_type.lower(), 1)

        async with self._lock:
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
                        unit=self.slave_id,
                    )
                except Exception as err:
                    _LOGGER.error("Read failed for %s register at %d: %s", register_type, address, err)
                    return None

                if result.isError():
                    return None

            # === RAW MODE ===
            if raw:
                return {
                    "registers": getattr(result, "registers", []),
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
        """Fetch latest data from configured registers."""
        if not await self._async_connect():
            raise UpdateFailed("Could not connect to Modbus device")

        registers = self.my_config_entry.options.get("registers", [])
        if not registers:
            _LOGGER.info("No registers yet defined")
            return {}
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
                self.my_config_entry,
                options={**self.my_config_entry.options, "registers": updated_registers},
            )

        if not new_data:
            raise UpdateFailed("No registers could be read")

        return new_data

    # ------------------------------------------------------------------
    # De/encoding (Using Pymodbus Mixin String-based Endianness)
    # ------------------------------------------------------------------
    def _decode_value(self, registers, data_type, byte_order="big", word_order="big"):
        """Decode registers using client mixin with string-based orders."""
        if not isinstance(registers, list) or len(registers) == 0:
            return registers

        dt = self.client.DATATYPE
        dt_map = {
            "uint16": dt.UINT16,
            "int16": dt.INT16,
            "uint32": dt.UINT32,
            "int32": dt.INT32,
            "float32": dt.FLOAT32,
            "uint64": dt.UINT64,
            "int64": dt.INT64,
        }
        
        target_type = dt_map.get(data_type, dt.UINT16)
        
        # Pymodbus 3.x mixin accepts "big" or "little" strings directly
        decoded = self.client.convert_from_registers(
            registers,
            data_type=target_type,
            byte_order=byte_order.lower(),
            word_order=word_order.lower(),
        )

        if data_type == "float32" and isinstance(decoded, (int, float)):
            return round(decoded, 6)
        return decoded

    def _encode_value(self, value, data_type, byte_order="big", word_order="big"):
        """Encode value to registers using client mixin with string-based orders."""
        dt = self.client.DATATYPE
        dt_map = {
            "uint16": dt.UINT16,
            "int16": dt.INT16,
            "uint32": dt.UINT32,
            "int32": dt.INT32,
            "float32": dt.FLOAT32,
        }

        target_type = dt_map.get(data_type, dt.UINT16)

        return self.client.convert_to_registers(
            value,
            data_type=target_type,
            byte_order=byte_order.lower(),
            word_order=word_order.lower(),
        )

