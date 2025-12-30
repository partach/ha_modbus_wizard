"""Config flow for Modbus Wizard."""
import logging
from typing import Any
#from datetime import timedelta
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from .const import (
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_TCP,
    CONF_CONNECTION_TYPE,
    CONF_HOST,
    CONF_PORT,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_NAME,
    CONF_STOPBITS,
    CONF_BYTESIZE,
    CONF_FIRST_REG,
    CONF_FIRST_REG_SIZE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_SLAVE_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_TCP_PORT,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_BYTESIZE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class ModbusWizardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for Modbus Wizard."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    @classmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        from .options_flow import ModbusWizardOptionsFlow
        return ModbusWizardOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """First step: common settings and first register for test."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_SERIAL:
                return await self.async_step_serial()
            return await self.async_step_tcp()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Modbus Hub"): str,
                    vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_SERIAL): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=CONNECTION_TYPE_SERIAL, label="Serial (RS485/RTU)"),
                                selector.SelectOptionDict(value=CONNECTION_TYPE_TCP, label="TCP/IP (Modbus TCP)"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=255,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                     vol.Required(CONF_FIRST_REG, default=0): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=65535,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(CONF_FIRST_REG_SIZE, default=1): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=20,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=10,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=5, max=300),  # 5 seconds to 5 minutes
                    ),
                }
            ),
        )

    async def async_step_serial(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Serial-specific settings."""
        errors = {}

        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        port_options = [
            selector.SelectOptionDict(
                value=port.device,
                label=f"{port.device} - {port.description or 'Unknown'}"
                      + (f" ({port.manufacturer})" if port.manufacturer else ""),
            )
            for port in ports
        ]
        port_options.sort(key=lambda opt: opt["value"])

        if user_input is not None:
            try:
                final_data = {
                    **self._data,
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                    CONF_BAUDRATE: user_input[CONF_BAUDRATE],
                    CONF_PARITY: user_input[CONF_PARITY],
                    CONF_STOPBITS: user_input[CONF_STOPBITS],
                    CONF_BYTESIZE: user_input[CONF_BYTESIZE],
                }

                await self._async_test_connection(final_data)

                return self.async_create_entry(title=final_data[CONF_NAME], data=final_data)

            except Exception as err:
                _LOGGER.exception("Serial connection test failed: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="serial",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=self._data.get(CONF_NAME, "Modbus Hub")): str,
                    vol.Required(CONF_SERIAL_PORT): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=port_options, mode=selector.SelectSelectorMode.DROPDOWN)
                    ),
                    vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In([2400, 4800, 9600, 19200, 38400]),
                    vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(["N", "E", "O"]),
                    vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In([1, 2]),
                    vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In([7, 8]),
                }
            ),
            errors=errors,
        )

    async def async_step_tcp(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """TCP-specific settings."""
        errors = {}

        if user_input is not None:
            try:
                final_data = {
                    **self._data,
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                }

                await self._async_test_connection(final_data)

                return self.async_create_entry(title=final_data[CONF_NAME], data=final_data)

            except Exception as err:
                _LOGGER.exception("TCP connection test failed: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="tcp",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=self._data.get(CONF_NAME, "Modbus Hub")): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_TCP_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_test_connection(self, data: dict[str, Any]) -> None:
        """Test connection and try reading the first register with all register types."""
        client = None
        try:
            if data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_SERIAL:
                client = AsyncModbusSerialClient(
                    port=data[CONF_SERIAL_PORT],
                    baudrate=data[CONF_BAUDRATE],
                    parity=data.get(CONF_PARITY, DEFAULT_PARITY),
                    stopbits=data.get(CONF_STOPBITS, DEFAULT_STOPBITS),
                    bytesize=data.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
                    timeout=5,
                )
            else:
                client = AsyncModbusTcpClient(
                    host=data[CONF_HOST],
                    port=data[CONF_PORT],
                    timeout=5,
                )

            await client.connect()
            if not client.connected:
                raise ConnectionError("Failed to connect to Modbus device")

            address = int(data[CONF_FIRST_REG])
            count = int(data[CONF_FIRST_REG_SIZE])
            slave_id = int(data[CONF_SLAVE_ID])

            methods = [
                ("holding registers", client.read_holding_registers),
                ("input registers", client.read_input_registers),
                ("coils", client.read_coils),
                ("discrete inputs", client.read_discrete_inputs),
            ]

            success = False
            for name, method in methods:
                try:
                    if name in ("coils", "discrete inputs"):
                        result = await method(address=address, count=count, device_id=slave_id)
                        if not result.isError() and hasattr(result, "bits") and len(result.bits) >= count:
                            success = True
                            break
                    else:
                        result = await method(address=address, count=count, device_id=slave_id)
                        if not result.isError() and hasattr(result, "registers") and len(result.registers) == count:
                            success = True
                            break
                except Exception as inner_err:
                    _LOGGER.debug("Test read failed for %s at addr %d: %s", name, address, inner_err)

            if not success:
                raise ModbusException(
                    f"Could not read {count} value(s) from address {address} using any register type. "
                    "Check address, size, slave ID, or device compatibility."
                )

        finally:
            if client:
                try:
                   client.close()
                except Exception as err:
                    _LOGGER.debug("Error closing Modbus client: %s", err)
