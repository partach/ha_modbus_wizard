"""Options flow for Modbus Wizard – validated & aligned with runtime."""
from __future__ import annotations

import json
from datetime import timedelta
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    CONF_REGISTERS,
)


class ModbusWizardOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Wizard."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        # self.config_entry = config_entry
        self._registers: list[dict] = list(config_entry.options.get(CONF_REGISTERS, []))

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Settings",
                "add_register": "Add register",
                "list_registers": f"Registers ({len(self._registers)})",
            },
        )

    # ------------------------------------------------------------------
    # SETTINGS
    # ------------------------------------------------------------------

    async def async_step_settings(self, user_input=None):
        if user_input is not None:
            interval = user_input[CONF_UPDATE_INTERVAL]

            coordinator = (
                self.hass.data
                .get(DOMAIN, {})
                .get("coordinators", {})
                .get(self.config_entry.entry_id)
            )
            if coordinator:
                coordinator.update_interval = timedelta(seconds=interval)

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options={**self.config_entry.options, CONF_UPDATE_INTERVAL: interval},
            )

            return self.async_create_entry(title="", data={})

        current = self.config_entry.options.get(CONF_UPDATE_INTERVAL, 10)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(CONF_UPDATE_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=300)
                )
            }),
        )

    # ------------------------------------------------------------------
    # ADD REGISTER
    # ------------------------------------------------------------------

    async def async_step_add_register(self, user_input=None):
        errors = {}

        if user_input is not None:
            # ---- parse & validate options (SelectEntity) ----
            raw_opts = user_input.get("options")
            if raw_opts:
                try:
                    user_input["options"] = json.loads(raw_opts)
                except json.JSONDecodeError:
                    errors["options"] = "invalid_json"

            # ---- enforce size for known data types ----
            type_sizes = {
                "uint16": 1,
                "int16": 1,
                "uint32": 2,
                "int32": 2,
                "float32": 2,
                "uint64": 4,
                "int64": 4,
            }
            dtype = user_input.get("data_type")
            if dtype in type_sizes:
                user_input["size"] = type_sizes[dtype]

            if not errors:
                self._registers.append(user_input)
                self._save()
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_register",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("address"): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=65535, step=1, mode=selector.NumberSelectorMode.BOX)
                ),
                vol.Required("data_type", default="uint16"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["uint16", "int16", "uint32", "int32", "float32", "uint64", "int64"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

                vol.Required("register_type", default="auto"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["auto", "holding", "input", "coil", "discrete"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

                vol.Required("rw", default="read"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["read", "write", "rw"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

                vol.Optional("unit"): str,

                vol.Optional("options"): str,  # JSON mapping for SelectEntity

                vol.Optional("byte_order", default="big"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["big", "little"])
                ),
                vol.Optional("word_order", default="big"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["big", "little"])
                ),

                # NumberEntity bounds
                vol.Optional("min"): vol.Coerce(float),
                vol.Optional("max"): vol.Coerce(float),
                vol.Optional("step", default=1): vol.Coerce(float),
            }),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # LIST / DELETE
    # ------------------------------------------------------------------

    async def async_step_list_registers(self, user_input=None):
        if user_input is not None:
            delete = set(user_input.get("delete", []))
            if delete:
                self._registers = [
                    r for r in self._registers
                    if f"{r['name']} (@{r['address']})" not in delete
                ]
                self._save()
            return await self.async_step_init()

        labels = [f"{r['name']} (@{r['address']})" for r in self._registers]

        return self.async_show_form(
            step_id="list_registers",
            data_schema=vol.Schema({
                vol.Optional("delete"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=labels,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
        )

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _save(self) -> None:
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={**self.config_entry.options, CONF_REGISTERS: self._registers},
        )
