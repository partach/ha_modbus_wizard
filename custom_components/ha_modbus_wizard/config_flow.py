"""Config flow for Modbus Wizard."""
import logging
from typing import Any
import serial.tools.list_ports
import voluptuous as vol
from pymodbus.exceptions import ModbusException
from homeassistant.data_entry_flow import FlowResult
from homeassistant import config_entries
from homeassistant.helpers import selector
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
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
    DEFAULT_SLAVE_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_TCP_PORT,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_BYTESIZE,
    CONF_FIRST_REG,
    CONF_FIRST_REG_SIZE,
)

_LOGGER = logging.getLogger(__name__)

class ModbusWizardConfigFlow(config_entries.ConfigFlow, domain="modbus_wizard"):
    """Handle config flow."""

    VERSION = 1
    def __init__(self):
        """Initialize the config flow."""
        self._connection_type = None
        self._user_input = {}
    
       
    async def async_step_user(self, user_input=None):
        """Handle initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_SERIAL): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=[CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_TCP])
                    ),
                    vol.Required(CONF_NAME, default="Modbus Hub"): vol.string,
                    vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.positive_int,
                    vol.Required(CONF_FIRST_REG, default=0): vol.positive_int,
                    vol.Required(CONF_FIRST_REG_SIZE, default=1): vol.positive_int,
                }),
            )
        conn_type = user_input[CONF_CONNECTION_TYPE]
        self.user_input=user_input
        if conn_type == CONNECTION_TYPE_SERIAL:
            return await self.async_step_serial(user_input)
        else:
            return await self.async_step_tcp(user_input)

    async def async_step_serial(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle serial connection configuration."""
        errors = {}

        # Discover serial ports
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        port_options = [
            selector.SelectOptionDict(
                value=port.device,
                label=(
                    f"{port.device} - {port.description or 'Unknown device'}"
                    + (f" ({port.manufacturer})" if port.manufacturer else "")
                ),
            )
            for port in ports if port.device
        ]
        port_options.sort(key=lambda x: x["value"])

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Felicity Inverter"): str,
                vol.Required(CONF_SERIAL_PORT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=port_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): vol.In(
                    [2400, 4800, 9600, 19200, 38400]
                ),
                vol.Required(CONF_PARITY, default=DEFAULT_PARITY): vol.In(
                    ["N", "E", "O"]
                ),
                vol.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): vol.In(
                    [1, 2]
                ),
                vol.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): vol.In(
                    [7, 8]
                ),
            }
        )

        if user_input is not None:
            try:
                # Merge data from previous step if we stored it, or just rely on defaults/hidden fields if simpler.
                # Here we reconstruct the full config.
                final_data = {
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_SERIAL,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_SERIAL_PORT: user_input[CONF_SERIAL_PORT],
                    CONF_SLAVE_ID: user_input[CONF_SLAVE_ID],
                    CONF_BAUDRATE: user_input[CONF_BAUDRATE],
                    CONF_PARITY: user_input[CONF_PARITY],
                    CONF_STOPBITS: user_input[CONF_STOPBITS],
                    CONF_BYTESIZE: user_input[CONF_BYTESIZE],
                    CONF_FIRST_REG: user_input[CONF_FIRST_REG],
                    CONF_FIRST_REG_SIZE: user_input[CONF_FIRST_REG_SIZE],
                }
                self.user_input.update(final_data)
                await self._async_test_serial_connection(final_data)

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=final_data,
                    options=self._get_default_options(),
                )

            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ModbusException:
                errors["base"] = "read_error"
            except ValueError:
                errors["base"] = "read_error"
            except Exception as err:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error during Felicity serial setup: %s", err)

        return self.async_show_form(step_id="serial", data_schema=data_schema, errors=errors)

    async def async_step_tcp(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle TCP connection configuration."""
        errors = {}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Felicity Inverter"): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_TCP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
            }
        )

        if user_input is not None:
            try:
                final_data = {
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_TCP,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PORT: user_input[CONF_PORT],
                    CONF_SLAVE_ID: user_input[CONF_SLAVE_ID],
                    CONF_FIRST_REG: user_input[CONF_FIRST_REG],
                    CONF_FIRST_REG_SIZE: user_input[CONF_FIRST_REG_SIZE],
                }
                self.user_input.update(final_data)                

                await self._async_test_tcp_connection(final_data)

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=final_data,
                    options=self._get_default_options(),
                )

            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ModbusException:
                errors["base"] = "read_error"
            except ValueError:
                errors["base"] = "read_error"
            except Exception as err:
                errors["base"] = "unknown"
                _LOGGER.exception("Unexpected error during Felicity TCP setup: %s", err)

        return self.async_show_form(step_id="tcp", data_schema=data_schema, errors=errors)

    async def _async_test_serial_connection(self, data: dict[str, Any]) -> None:
        """Test serial connection to the Felicity meter."""
        client = None
        try:
            client = AsyncModbusSerialClient(
                port=data[CONF_SERIAL_PORT],
                baudrate=data[CONF_BAUDRATE],
                parity=data.get(CONF_PARITY, DEFAULT_PARITY),
                stopbits=data.get(CONF_STOPBITS, DEFAULT_STOPBITS),
                bytesize=data.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
                timeout=5,
            )
            
            await client.connect()
            if not client.connected:
                raise ConnectionError("Failed to open serial port")
            test_register_value= self.user_input[CONF_FIRST_REG]    
            reg_size = self.user_input[CONF_FIRST_REG_SIZE]
            result = await client.read_holding_registers(
                address=test_register_value, count=reg_size, device_id=data[CONF_SLAVE_ID]
            )
            
            if result.isError():
                raise ModbusException(f"Modbus read error: {result}")
                
            if len(result.registers) != 1:
                raise ValueError("Invalid response: expected 1 register")
    
        finally:
            if client is not None:
                try:
                    await client.close()
                except Exception as err:
                    _LOGGER.debug("Error closing Modbus Serial client: %s", err)

    async def _async_test_tcp_connection(self, data: dict[str, Any]) -> None:
        """Test TCP connection to the Felicity meter."""
        client = None
        try:
            client = AsyncModbusTcpClient(
                host=data[CONF_HOST],
                port=data[CONF_PORT],
                timeout=5,
            )
            await client.connect()
            if not client.connected:
                raise ConnectionError(f"Failed to connect to {data[CONF_HOST]}:{data[CONF_PORT]}")
    
            test_register_value= self.user_input[CONF_FIRST_REG]    
            reg_size = self.user_input[CONF_FIRST_REG_SIZE]
            result = await client.read_holding_registers(
                address=test_register_value, count=reg_size, device_id=data[CONF_SLAVE_ID]
            )
    
            if result.isError():
                raise ModbusException(f"Modbus read error: {result}")
    
            if len(result.registers) != 1:
                # Note: Testing 1 register here for consistency with serial test
                raise ValueError("Invalid response: expected 1 register")
    
        finally:
            if client is not None:
                try:
                    await client.close()
                except Exception as err:
                    _LOGGER.debug("Error closing Modbus TCP client: %s", err)
