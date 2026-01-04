"""Options flow for Modbus Wizard – validated & aligned with runtime."""
from __future__ import annotations
import logging
import json
from datetime import timedelta
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    CONF_ENTITIES,
)
_LOGGER = logging.getLogger(__name__)

class ModbusWizardOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Modbus Wizard."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        # self.config_entry = config_entry
        self._entities: list[dict] = list(config_entry.options.get(CONF_ENTITIES, []))
        self._edit_index: int | None = None
        
    async def async_step_init(self, user_input=None):
            menu_options = {
                "settings": "Settings",
                "add_entity": "Add Entity",
                "load_template": "Load device template",
            }
            if len(self._entities) > 0:
                menu_options["list_entities"] = f"Entities ({len(self._entities)})"
                menu_options["edit_entity"] = "Edit Entity"
            return self.async_show_menu(
                step_id="init",
                menu_options=menu_options,
            )

    # ------------------------------------------------------------------
    # Edit
    # ------------------------------------------------------------------
    async def async_step_edit_entity(self, user_input=None):
        """Select which register to edit."""
        if user_input is not None:
            self._edit_index = int(user_input["register"])
            return await self.async_step_edit_entity_form()
    
        # Create dropdown options: index -> display label
        options = [
            selector.SelectOptionDict(
                value=str(i),
                label=f"{r['name']} (Address {r['address']}, {r.get('data_type', 'uint16')})"
            )
            for i, r in enumerate(self._entities)
        ]
    
        return self.async_show_form(
            step_id="edit_entity",
            data_schema=vol.Schema({
                vol.Required("register"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }),
        )
        
    # ------------------------------------------------------------------
    # EDIT REGISTER FORM
    # ------------------------------------------------------------------
    
    async def async_step_edit_entity_form(self, user_input=None):
        """Edit the selected register."""
        reg = self._entities[self._edit_index]
        errors = {}
    
        if user_input is not None:
            # Parse options JSON
            raw_opts = user_input.get("options")
            if raw_opts:
                try:
                    user_input["options"] = json.loads(raw_opts)
                except json.JSONDecodeError:
                    errors["options"] = "invalid_json"
    
            # Enforce size from datatype
            type_sizes = {
                "uint16": 1, "int16": 1,
                "uint32": 2, "int32": 2,
                "float32": 2,
                "uint64": 4, "int64": 4,
            }
            dtype = user_input.get("data_type")
            if dtype in type_sizes:
                user_input["size"] = type_sizes[dtype]

            # Ensure numeric fields are correct type
            user_input["address"] = int(user_input["address"])
            user_input["size"] = int(user_input.get("size", 1))
    
            if not errors:
                self._entities[self._edit_index] = user_input
                self._save_options({CONF_ENTITIES: self._entities})
                _LOGGER.info("Register '%s' updated", user_input.get("name"))
                return await self.async_step_init()
    
        # Prepare defaults from existing register
        defaults = {
            "name": reg.get("name"),
            "address": reg.get("address"),
            "data_type": reg.get("data_type", "uint16"),
            "register_type": reg.get("register_type", "auto"),
            "rw": reg.get("rw", "read"),
            "unit": reg.get("unit", ""),
            "scale": reg.get("scale", 1.0),
            "offset": reg.get("offset", 0.0),
            "options": json.dumps(reg.get("options", {})) if reg.get("options") else "",
            "byte_order": reg.get("byte_order", "big"),
            "word_order": reg.get("word_order", "big"),
            "allow_bits": reg.get("allow_bits", False),
            "min": reg.get("min"),
            "max": reg.get("max"),
            "step": reg.get("step", 1),
        }

        return self.async_show_form(
            step_id="edit_entity_form",
            data_schema=self._get_register_schema(defaults),
            errors=errors,
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
                _LOGGER.debug("Updated coordinator interval to %d seconds", interval)

            # Save settings - preserve ALL existing options
            self._save_options({CONF_UPDATE_INTERVAL: interval})
            
            return self.async_abort(reason="settings_updated")


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

    async def async_step_add_entity(self, user_input=None):
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
            # Ensure numeric fields are correct type
            user_input["address"] = int(user_input["address"])
            user_input["size"] = int(user_input.get("size", 1))
            
            if not errors:
                _LOGGER.debug("Adding register: %s", user_input)
                self._entities.append(user_input)
                self._save_options({CONF_ENTITIES: self._entities})
                _LOGGER.info("Register added. Total: %d", len(self._entities))
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_entity",
            data_schema=self._get_register_schema(),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # LIST / DELETE
    # ------------------------------------------------------------------

    async def async_step_list_entities(self, user_input=None):
        """List and optionally delete registers."""
        if user_input is not None:
            delete = set(user_input.get("delete", []))
            if delete:
                # Delete by index
                self._entities = [
                    r for i, r in enumerate(self._entities)
                    if str(i) not in delete
                ]
                self._save_options({CONF_ENTITIES: self._entities})
                _LOGGER.info("Deleted %d registers. Remaining: %d", len(delete), len(self._entities))
            return await self.async_step_init()

        # Create selection options with index as value
        options = [
            selector.SelectOptionDict(
                value=str(i),
                label=f"{r['name']} (Address {r['address']}, {r.get('data_type', 'uint16')})"
            )
            for i, r in enumerate(self._entities)
        ]

        return self.async_show_form(
            step_id="list_entities",
            data_schema=vol.Schema({
                vol.Optional("delete"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }),
        )

    # ------------------------------------------------------------------
    # Load Template
    # ------------------------------------------------------------------
    async def async_step_load_template(self, user_input=None):
        if user_input is not None:
            template_name = user_input["template"]
            template_path = self.hass.config.path(
                "custom_components", DOMAIN, "templates", f"{template_name}.json"
            )
    
            try:
                template_data = await self.hass.async_add_executor_job(
                    _load_template_file, template_path
                )
    
                if not isinstance(template_data, list):
                    raise ValueError("Template must be a list")
    
                existing_keys = {
                    (r.get("name"), r.get("address"))
                    for r in self._registers
                }
    
                added = 0
                for reg in template_data:
                    if not isinstance(reg, dict):
                        continue
                    if "name" not in reg or "address" not in reg:
                        continue
    
                    key = (reg["name"], reg["address"])
                    if key in existing_keys:
                        continue
    
                    self._registers.append(reg)
                    existing_keys.add(key)
                    added += 1
    
                if not added:
                    return self.async_show_form(
                        step_id="load_template",
                        errors={"base": "template_empty_or_duplicate"},
                    )
    
                self._save()
                return await self.async_step_init()
    
            except FileNotFoundError:
                return self.async_show_form(
                    step_id="load_template",
                    errors={"base": "template_not_found"},
                )
            except json.JSONDecodeError:
                return self.async_show_form(
                    step_id="load_template",
                    errors={"base": "invalid_template"},
                )
            except Exception as err:
                _LOGGER.error("Failed to load template %s: %s", template_name, err)
                return self.async_show_form(
                    step_id="load_template",
                    errors={"base": "load_failed"},
                )
    
        # ---- List templates ----
        templates_dir = self.hass.config.path(
            "custom_components", DOMAIN, "templates"
        )
    
        try:
            templates = sorted(
                f[:-5]
                for f in os.listdir(templates_dir)
                if f.endswith(".json")
            )
        except Exception:
            templates = []
    
        if not templates:
            return self.async_abort(reason="no_templates")
    
        return self.async_show_form(
            step_id="load_template",
            data_schema=vol.Schema({
                vol.Required("template"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=t,
                                label=t.replace("_", " ").title(),
                            )
                            for t in templates
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }),
        )

    
    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _load_template_file(path: str):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def _get_register_schema(self, defaults: dict | None = None) -> vol.Schema:
        """Get the register form schema with optional defaults."""
        defaults = defaults or {}
        
        return vol.Schema({
            vol.Required("name", default=defaults.get("name")): str,
            vol.Required("address", default=defaults.get("address")): 
                vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            
            vol.Required("data_type", default=defaults.get("data_type", "uint16")): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["uint16", "int16", "uint32", "int32", "float32", "uint64", "int64"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

            vol.Required("register_type", default=defaults.get("register_type", "input")): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["auto", "holding", "input", "coil", "discrete"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

            vol.Required("rw", default=defaults.get("rw", "read")): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["read", "write", "rw"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            
            vol.Optional("unit", default=defaults.get("unit", "")): str,
            vol.Optional("scale", default=defaults.get("scale", 1.0)): vol.Coerce(float),
            vol.Optional("offset", default=defaults.get("offset", 0.0)): vol.Coerce(float),
            vol.Optional("options", default=defaults.get("options", "")): str,
            
            vol.Optional("byte_order", default=defaults.get("byte_order", "big")): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["big", "little"])
                ),
            
            vol.Optional("word_order", default=defaults.get("word_order", "big")): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["big", "little"])
                ),
            
            vol.Optional("allow_bits", default=defaults.get("allow_bits", False)): bool,
            vol.Optional("min", default=defaults.get("min")): vol.Any(None,vol.Coerce(float)),
            vol.Optional("max", default=defaults.get("max")): vol.Any(None,vol.Coerce(float)),
            vol.Optional("step", default=defaults.get("step", 1)): vol.Coerce(float),
        })

    def _save_options(self, updates: dict) -> None:
        """Save the current registers list, preserving other options."""
        new_options = dict(self.config_entry.options)  # full copy
        # Update only the specified keys
        new_options.update(updates)
        for r in self._entities:
            r["address"] = int(r["address"])  # make sure we have integers for those, no floats creep through
            r["size"] = int(r.get("size", 1))
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options=new_options,
        )
        # Trigger reload so entities are recreated
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
