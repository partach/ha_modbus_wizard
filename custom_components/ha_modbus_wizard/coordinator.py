"""Data update coordinator for Modbus Wizard."""

from __future__ import annotations

import logging
import asyncio
from datetime import timedelta
from typing import Any, List

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

    async def async_write_registers(self, address: int, value: Any, size: int = 1) -> bool:
        """Write holding registers."""
        if size != 1:
            raise HomeAssistantError("Multi-register write not implemented yet")

        if not await self._async_connect():
            return False

        async with self._lock:
            try:
                result = await self.client.write_registers(
                    address=address,
                    values=[value],
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
                        reg.get("data_type", "uint"),
                        count,
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
    # Decoding
    # ------------------------------------------------------------------

    def _decode_value(self, values: List[int], data_type: str, size: int):
        """Basic decoder (extend later)."""
        if size == 1:
            return values[0]

        # Placeholder for future struct/float decoding
        return values
