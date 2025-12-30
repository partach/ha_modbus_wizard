from homeassistant import config_entries
#from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol
from datetime import timedelta

from .const import (
    CONF_UPDATE_INTERVAL, 
    DOMAIN,
    CONF_REGISTERS,
)

class ModbusWizardOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Wizard."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self._config_entry = config_entry
        # Use a local copy of registers to modify during the session
        self._registers = list(config_entry.options.get(CONF_REGISTERS, []))

    async def async_step_init(self, user_input=None):
        """Main options menu."""
        # This step acts as a menu to either change settings or go to register management
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                {"id": "settings", "title": "Settings"},
                {"id": "add_register", "title": "Add Register"},
                {"id": "list_registers", "title": f"Registers ({len(self._registers)})"}  # Dynamic count
        ]
        )

    async def async_step_settings(self, user_input=None):
        """Manage global settings like update interval."""
        if user_input is not None:
            # Update the coordinator immediately if it exists
            if DOMAIN in self.hass.data and self._config_entry.entry_id in self.hass.data[DOMAIN]:
                coordinator = self.hass.data[DOMAIN][self._config_entry.entry_id]
                new_interval = user_input.get(CONF_UPDATE_INTERVAL, 10)
                coordinator.update_interval = timedelta(seconds=new_interval)

            return self.async_create_entry(title="", data={
                **self._config_entry.options,
                **user_input,
                CONF_REGISTERS: self._registers
            })

        current_interval = self._config_entry.options.get(CONF_UPDATE_INTERVAL, 10)
        
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=5, max=300)
                ),
            })
        )

    async def async_step_add_register(self, user_input=None):
        """Add a new register definition."""
        if user_input is not None:
            self._registers.append(user_input)
            # Update the entry with the new list and return to init
            return self.async_create_entry(
                title="", 
                data={**self._config_entry.options, CONF_REGISTERS: self._registers}
            )

        return self.async_show_form(
            step_id="add_register",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("address"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
                vol.Required("size", default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=20, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("register_type", default="auto"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["auto", "holding", "input", "coil", "discrete"],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("data_type", default="uint"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["uint", "int", "float", "string"],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("rw", default="read"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["read", "write","rw"],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Optional("options"): str,  # User can enter JSON like: {"0": "Off", "1": "On"}
                vol.Optional("unit"): str,
            })
        )

    async def async_step_list_registers(self, user_input=None):
        """Show current registers (simple implementation)."""
        # In a real app, you might use a multi-select to delete registers here
        if user_input is not None:
            return await self.async_step_init()
        
        return self.async_show_form(
            step_id="list_registers",
            description_placeholders={
                "count": str(len(self._registers)),
                "names": "<br>".join([f"• {r['name']} (@{r['address']})" for r in self._registers]) or "None"
            },
            data_schema=vol.Schema({}), # Just an 'OK' button essentially
        )
