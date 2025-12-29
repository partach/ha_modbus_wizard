"""Options flow for Modbus Wizard."""
from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol

class ModbusWizardOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.registers = self.config_entry.options.get("registers", [])

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                description_placeholders={"registers": str(len(self.registers))},
                data_schema=vol.Schema({}),
            )
        
        # Redirect to add_register
        return await self.async_step_add_register()

    async def async_step_add_register(self, user_input=None):
        """Add a new register."""
        if user_input is not None:
            self.registers.append(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, options={"registers": self.registers}
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_register",
            data_schema=vol.Schema({
                vol.Required("name"): vol.string,
                vol.Required("address"): vol.positive_int,
                vol.Required("size", default=1): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=4)
                ),
                vol.Required("register_type", default="holding"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            "auto", # automatically try to get a match.
                            "holding",    # read/write words
                            "input",      # read-only words
                            "coil",       # read/write bits
                            "discrete",   # read-only bits
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required("data_type", default="uint"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["uint", "int", "float", "string"])
                ),
                vol.Optional("device_class"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["voltage", "current", "power", "energy", "battery"])  # Add more
                ),
                vol.Required("rw", default="read"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["read", "write"])
                ),
                vol.Optional("unit"): vol.string,
            }),
        )
