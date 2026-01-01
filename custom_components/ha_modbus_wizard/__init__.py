"""The Modbus Wizard integration."""
import os
import shutil
import logging
from homeassistant.helpers import device_registry as dr
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient, AsyncModbusUdpClient
from homeassistant.exceptions import HomeAssistantError
from datetime import timedelta
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_PROTOCOL,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONF_UPDATE_INTERVAL,
    CONF_NAME,
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_IP,
    CONNECTION_TYPE_UDP,
    DEFAULT_BAUDRATE,
    DEFAULT_BYTESIZE,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    DOMAIN,
)
from .coordinator import ModbusWizardCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT]

async def async_install_frontend_resource(hass: HomeAssistant):
    """Ensure the frontend JS file is copied to the www/community folder."""
    
    def install():
        # Source path: custom_components/ha_felicity/frontend/
        source_path = hass.config.path("custom_components", DOMAIN, "frontend", "ha_modbus_wizard.js")
        
        # Target path: www/community/
        target_dir = hass.config.path("www", "community", DOMAIN)
        target_path = os.path.join(target_dir, "ha_modbus_wizard.js")

        try:
            # 1. Ensure the destination directory exists
            if not os.path.exists(target_dir):
                _LOGGER.debug("Creating directory: %s", target_dir)
                os.makedirs(target_dir, exist_ok=True)

            # 2. Check if source exists and copy
            if os.path.exists(source_path):
                # Using copy2 to preserve metadata (timestamps)
                shutil.copy2(source_path, target_path)
                _LOGGER.info("Updated frontend resource: %s", target_path)
            else:
                _LOGGER.warning("Frontend source file missing at %s", source_path)
                
        except Exception as err:
            _LOGGER.error("Failed to install frontend resource: %s", err)

    # Offload the blocking file operations to the executor thread
    await hass.async_add_executor_job(install)

async def async_register_card(hass: HomeAssistant, entry: ConfigEntry):
    """Register the custom card as a Lovelace resource."""
    lovelace_data = hass.data.get("lovelace")
    if not lovelace_data:
        _LOGGER.debug("Unable to get lovelace data (new api 2026.2)")
        return  # YAML mode or Lovelace not loaded

    resources = lovelace_data.resources
    if not resources:
        _LOGGER.debug("Unable to get resources (new api 2026.2)")
        return  # YAML mode or not loaded

    if not resources.loaded:
        await resources.async_load()

    card_url = f"/hacsfiles/{DOMAIN}/{DOMAIN}.js"

    # Check if already registered
    for item in resources.async_items():
        if item["url"] == card_url:
            _LOGGER.debug("Card already registered: %s", card_url)
            return  # already there

    await resources.async_create_item({
        "res_type": "module",
        "url": card_url,
    })
    _LOGGER.debug("Card registered: %s", card_url)
    
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Modbus Wizard from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("connections", {})
    hass.data[DOMAIN].setdefault("coordinators", {})

    config = entry.data
    connection_type = config.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_SERIAL)
    protocol = config.get(CONF_PROTOCOL, CONNECTION_TYPE_TCP)

    # ----------------------------------------------------------------
    # Get or create shared Modbus connection
    # ----------------------------------------------------------------
    if connection_type == CONNECTION_TYPE_SERIAL:
        key = (
            f"serial:"
            f"{config[CONF_SERIAL_PORT]}:"
            f"{config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)}:"
            f"{config.get(CONF_PARITY, DEFAULT_PARITY)}:"
            f"{config.get(CONF_STOPBITS, DEFAULT_STOPBITS)}:"
            f"{config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)}"
        )

        if key not in hass.data[DOMAIN]["connections"]:
            hass.data[DOMAIN]["connections"][key] = AsyncModbusSerialClient(
                port=config[CONF_SERIAL_PORT],
                baudrate=config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE),
                parity=config.get(CONF_PARITY, DEFAULT_PARITY),
                stopbits=config.get(CONF_STOPBITS, DEFAULT_STOPBITS),
                bytesize=config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE),
                timeout=5,
            )
    elif connection_type == CONNECTION_TYPE_IP and protocol == CONNECTION_TYPE_UDP:
        key = f"tcp:{config[CONF_HOST]}:{config[CONF_PORT]}"

        if key not in hass.data[DOMAIN]["connections"]:
            hass.data[DOMAIN]["connections"][key] = AsyncModbusUdpClient(
                host=config[CONF_HOST],
                port=config[CONF_PORT],
                timeout=5,
            )
    else:  # UDP
        key = f"tcp:{config[CONF_HOST]}:{config[CONF_PORT]}"

        if key not in hass.data[DOMAIN]["connections"]:
            hass.data[DOMAIN]["connections"][key] = AsyncModbusTcpClient(
                host=config[CONF_HOST],
                port=config[CONF_PORT],
                timeout=5,
            )

    client = hass.data[DOMAIN]["connections"][key]

    # ----------------------------------------------------------------
    # Create coordinator (ONE per config entry)
    # ----------------------------------------------------------------
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, 10)

    coordinator = ModbusWizardCoordinator(
        hass=hass,
        client=client,
        slave_id=config[CONF_SLAVE_ID],
        config_entry=entry,
        update_interval=timedelta(seconds=update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN]["coordinators"][entry.entry_id] = coordinator
    # CREATE DEVICE REGISTRY ENTRY
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data.get(CONF_NAME, "Modbus Device"),
        manufacturer="Modbus",
        model="Wizard",
        configuration_url=f"homeassistant://config/integrations/integration/{entry.entry_id}",
    )
    # ----------------------------------------------------------------
    # Platforms
    # ----------------------------------------------------------------
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ----------------------------------------------------------------
    # Services (register once)
    # ----------------------------------------------------------------
    if not hass.data[DOMAIN].get("services_registered"):
        await async_setup_services(hass)
        hass.data[DOMAIN]["services_registered"] = True

    # ----------------------------------------------------------------
    # Frontend
    # ----------------------------------------------------------------
    await async_install_frontend_resource(hass)
    await async_register_card(hass, entry)
    
    return True

async def async_setup_services(hass: HomeAssistant) -> None:

    def _get_coordinator(call: ServiceCall) -> ModbusWizardCoordinator:
        entity_id = call.data.get("entity_id")
        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        if not entity_id:
            raise HomeAssistantError("entity_id is required")
        if not entity_id:
            raise HomeAssistantError("entity_id required")

        state = hass.states.get(entity_id)
        if not state:
            raise HomeAssistantError("Entity not found")

        entry_id = state.attributes.get("config_entry_id")
        if not entry_id:
            raise HomeAssistantError("Entity not linked to config entry")

        coordinator = hass.data[DOMAIN]["coordinators"].get(entry_id)
        if not coordinator:
            raise HomeAssistantError("Coordinator not found")

        return coordinator
        
    async def handle_write_register(call: ServiceCall):
        coordinator = _get_coordinator(call)
    
        success = await coordinator.async_write_registers(
            address=int(call.data["address"]),
            value=call.data["value"],
            data_type=call.data.get("data_type", "uint16"),
            byte_order=call.data.get("byte_order", "big"),
            word_order=call.data.get("word_order", "big"),
        )
    
        if not success:
            raise HomeAssistantError("Write failed")
    
    async def handle_read_register(call: ServiceCall):
        """Service to read a Modbus register and return decoded value."""
        # Required
        address = int(call.data["address"])
    
        # Optional with defaults
        register_type = call.data.get("register_type", "holding").lower()  # holding, input, coil, discrete, auto
        data_type = call.data.get("data_type", "uint16")
        size = int(call.data.get("size", 1))  # Override size (e.g., for float32 = 2)
        byte_order = call.data.get("byte_order", "big")
        word_order = call.data.get("word_order", "big")
        raw = call.data.get("raw", False)  # Return raw registers if True
    
        coordinator = _get_coordinator(call)
        if coordinator is None:
            raise HomeAssistantError("No coordinator found for this device")
    
        # Use the full polling logic for consistency (handles auto-detect, etc.)
        # Or call a new helper — but reuse existing logic if possible
    
        value = await coordinator.async_read_typed(
            address=address,
            data_type=data_type,
            byte_order=byte_order,
            word_order=word_order,
            size=size,
            register_type=register_type,  # ← Pass type
            raw=raw,
        )
    
        if value is None:
            raise HomeAssistantError(f"Failed to read address {address}")
    
        return {"value": value}
        
    # register the services    
    hass.services.async_register(DOMAIN, "write_register", handle_write_register)
    hass.services.async_register(DOMAIN, "read_register", handle_read_register)



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    coordinator = hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    # Close connection if unused
    if coordinator:
        client = coordinator.client
        still_used = any(
            c.client is client
            for c in hass.data[DOMAIN]["coordinators"].values()
        )

        if not still_used:
            try:
                if client.connected:
                    await client.close()
            except Exception as err:
                _LOGGER.debug("Error closing Modbus client: %s", err)

    return True
