"""Config flow for Modbus Wizard."""
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
    CONF_STOPBITS,
    CONF_BYTESIZE,
    DEFAULT_SLAVE_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_TCP_PORT,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DEFAULT_BYTESIZE,
)

import vol as cv

class ModbusWizardConfigFlow(config_entries.ConfigFlow, domain="modbus_wizard"):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=cv.Schema({
                    cv.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_SERIAL): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=[CONNECTION_TYPE_SERIAL, CONNECTION_TYPE_TCP])
                    ),
                    cv.Required(CONF_NAME, default="Modbus Hub"): cv.string,
                    cv.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): cv.positive_int,
                }),
            )

        conn_type = user_input[CONF_CONNECTION_TYPE]
        if conn_type == CONNECTION_TYPE_SERIAL:
            return await self.async_step_serial(user_input)
        else:
            return await self.async_step_tcp(user_input)

    async def async_step_serial(self, user_input=None):
        """Handle serial config."""
        if user_input is None:
            return self.async_show_form(
                step_id="serial",
                data_schema=cv.Schema({
                    cv.Required(CONF_SERIAL_PORT): cv.string,
                    cv.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
                    cv.Required(CONF_PARITY, default=DEFAULT_PARITY): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=["N", "E", "O"])
                    ),
                    cv.Required(CONF_STOPBITS, default=DEFAULT_STOPBITS): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=[1, 2])
                    ),
                    cv.Required(CONF_BYTESIZE, default=DEFAULT_BYTESIZE): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=[7, 8])
                    ),
                }),
            )

        data = {**self.context.get("user_input", {}), **user_input}
        return await self.async_test_connection(data)

    async def async_step_tcp(self, user_input=None):
        """Handle TCP config."""
        if user_input is None:
            return self.async_show_form(
                step_id="tcp",
                data_schema=cv.Schema({
                    cv.Required(CONF_HOST): cv.string,
                    cv.Required(CONF_PORT, default=DEFAULT_TCP_PORT): cv.port,
                }),
            )

        data = {**self.context.get("user_input", {}), **user_input}
        return await self.async_test_connection(data)

    async def async_test_connection(self, data):
        """Test connection."""
        conn_type = data[CONF_CONNECTION_TYPE]
        client = AsyncModbusSerialClient(**{k: data[k] for k in [CONF_SERIAL_PORT, CONF_BAUDRATE, CONF_PARITY, CONF_STOPBITS, CONF_BYTESIZE] if k in data}) if conn_type == CONNECTION_TYPE_SERIAL else AsyncModbusTcpClient(data[CONF_HOST], data[CONF_PORT])
        
        try:
            await client.connect()
            if not client.connected:
                return self.async_show_form(step_id="user", errors={"base": "cannot_connect"})
            client.close()
        except Exception:
            return self.async_show_form(step_id="user", errors={"base": "cannot_connect"})

        return self.async_create_entry(title=data[CONF_NAME], data=data)
