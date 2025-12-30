"""Data update coordinator for Modbus Wizard."""

from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
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
    ):
        type_map = {
            "uint16": (1, "decode_16bit_uint"),
            "int16": (1, "decode_16bit_int"),
            "uint32": (2, "decode_32bit_uint"),
            "int32": (2, "decode_32bit_int"),
            "float32": (2, "decode_32bit_float"),
        }
    
        if data_type not in type_map:
            raise ValueError(f"Unsupported data_type: {data_type}")
    
        count, decode_fn = type_map[data_type]
    
        result = await self.client.read_holding_registers(
            address=address,
            count=count,
            device_id=self.slave_id,
        )
    
        if result.isError():
            return None
    
        decoder = BinaryPayloadDecoder.fromRegisters(
            result.registers,
            byteorder=Endian.Big if byte_order == "big" else Endian.Little,
            wordorder=Endian.Big if word_order == "big" else Endian.Little,
        )
    
        return getattr(decoder, decode_fn)()               

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
                            result = await self.client.read_holding_registers(address, count, self.slave_id)
                        elif reg_type == "input":
                            result = await self.client.read_input_registers(address, count, self.slave_id)
                        elif reg_type == "coil":
                            result = await self.client.read_coils(address, count, self.slave_id)
                        elif reg_type == "discrete":
                            result = await self.client.read_discrete_inputs(address, count, self.slave_id)
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
        decoder = BinaryPayloadDecoder.fromRegisters(
            registers,
            byteorder=Endian.BIG if byte_order == "big" else Endian.LITTLE,
            wordorder=Endian.BIG if word_order == "big" else Endian.LITTLE,
        )
    
        if data_type == "int16":
            return decoder.decode_16bit_int()
        if data_type == "uint16":
            return decoder.decode_16bit_uint()
        if data_type == "int32":
            return decoder.decode_32bit_int()
        if data_type == "uint32":
            return decoder.decode_32bit_uint()
        if data_type == "float32":
            return round(decoder.decode_32bit_float(), 6)
    
        raise ValueError(f"Unsupported data_type: {data_type}")
        
    def _encode_value(self, value, data_type, byte_order="big", word_order="big"):
        builder = BinaryPayloadBuilder(
            byteorder=Endian.BIG if byte_order == "big" else Endian.LITTLE,
            wordorder=Endian.BIG if word_order == "big" else Endian.LITTLE,
        )
    
        if data_type == "int16":
            builder.add_16bit_int(int(value))
        elif data_type == "uint16":
            builder.add_16bit_uint(int(value))
        elif data_type == "int32":
            builder.add_32bit_int(int(value))
        elif data_type == "uint32":
            builder.add_32bit_uint(int(value))
        elif data_type == "float32":
            builder.add_32bit_float(float(value))
        else:
            raise ValueError(f"Unsupported data_type: {data_type}")
    
        return builder.to_registers()
