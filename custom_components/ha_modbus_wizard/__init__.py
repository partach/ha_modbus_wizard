"""The Modbus Wizard integration."""
import os
import shutil
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from homeassistant.exceptions import HomeAssistantError
from datetime import timedelta
from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_CONNECTION_TYPE,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_SERIAL_PORT,
    CONF_SLAVE_ID,
    CONF_STOPBITS,
    CONNECTION_TYPE_SERIAL,
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
    config = entry.data
    connection_type = config.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_SERIAL)
    
    # Get or create shared hub
    hubs = hass.data.setdefault(DOMAIN, {}).setdefault("hubs", {})
    if connection_type == CONNECTION_TYPE_SERIAL:
        port = config[CONF_SERIAL_PORT]
        baudrate = config.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
        parity = config.get(CONF_PARITY, DEFAULT_PARITY)
        stopbits = config.get(CONF_STOPBITS, DEFAULT_STOPBITS)
        bytesize = config.get(CONF_BYTESIZE, DEFAULT_BYTESIZE)
        hub_key = f"serial_{port}_{baudrate}_{parity}_{stopbits}_{bytesize}"
        
        if hub_key not in hubs:
            hubs[hub_key] = ModbusSerialHub(hass, port, baudrate, parity, stopbits, bytesize)
    else:  # TCP
        host = config[CONF_HOST]
        port = config[CONF_PORT]
        hub_key = f"tcp_{host}_{port}"
        
        if hub_key not in hubs:
            hubs[hub_key] = ModbusTcpHub(hass, host, port)

    hub = hubs[hub_key]
    update_interval = config_entry.options.get(CONF_UPDATE_INTERVAL, 10)
    # Create coordinator
    coordinator = ModbusWizardCoordinator(
        hass=hass,
        client=hub.client,
        slave_id=config[CONF_SLAVE_ID],
        config_entry=entry,
        timedelta(seconds=update_interval),
    )
    
    # Store config and hub_key
    coordinator.config = config
    coordinator.hub_key = hub_key

    # First refresh
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Setup services if not done
    if "services_setup" not in hass.data[DOMAIN]:
        await async_setup_services(hass)
        hass.data[DOMAIN]["services_setup"] = True

    #copy card and register it
    await async_install_frontend_resource(hass)
    await async_register_card(hass, entry)
    
    return True

async def async_setup_services(hass: HomeAssistant) -> None:

    def _get_hub():
      # Single hub assumption, needs an update!
      return next(iter(hass.data[DOMAIN].values()))
    # decide what to do with this one or top one.
    def _get_hub_from_call(hass, call):
        entity_id = next(iter(call.data.get("entity_id", [])), None)
        if not entity_id:
            raise HomeAssistantError("No entity_id provided")
    
        entity = hass.states.get(entity_id)
        if not entity:
            raise HomeAssistantError("Entity not found")
    
        entry_id = entity.attributes.get("config_entry_id")
        if not entry_id:
            raise HomeAssistantError("Entity not linked to config entry")
        return hass.data[DOMAIN][entry_id]
        
    async def handle_write_register(call: ServiceCall):
        address = call.data["address"]
        value = call.data["value"]
        size = call.data.get("size", 1)
        
        hub = _get_hub()
        success = await hub.async_write_registers(address, value, size)
        if success:
            _LOGGER.info("Wrote value %s to address %s", value, address)
            await hub.async_request_refresh()
        else:
            raise HomeAssistantError(f"Failed to write to address {address}")
    
    async def handle_read_register(call: ServiceCall):
        address = call.data["address"]
        size = call.data.get("size", 1)
    
        hub = _get_hub()
        value = await hub.async_read_registers(address, size)
    
        if value is None:
            raise HomeAssistantError("Read failed")
    
        return {"value": value}
        
    hass.services.async_register(DOMAIN, "write_register", handle_write_register)
    hass.services.async_register(DOMAIN, "read_register", handle_read_register)



async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if coordinator:
        hub_key = coordinator.hub_key
        # Close hub if no other entries
        remaining_entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id != entry.entry_id]
        if not any(hass.data[DOMAIN].get(e.entry_id).hub_key == hub_key for e in remaining_entries if hass.data[DOMAIN].get(e.entry_id)):
            hub = hass.data[DOMAIN]["hubs"].pop(hub_key, None)
            if hub:
                await hub.close()

    return True

class ModbusSerialHub:
    """Manages serial connection."""
    def __init__(
        self,
        hass: HomeAssistant,
        port: str,
        baudrate: int,
        parity: str,
        stopbits: int,
        bytesize: int,
    ):
        """Initialize the serial hub."""
        self.hass = hass
        self.port = port
        self.baudrate = baudrate
        self.parity = parity
        self.stopbits = stopbits
        self.bytesize = bytesize
        self.client = AsyncModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            bytesize=bytesize,
            timeout=5,
        )

    async def close(self):
        """Close the connection safely."""
        if self.client is not None:
            if self.client.connected:
                try:
                    self.client.close()
                except Exception as err:
                    _LOGGER.exception("Unexpected error closing modbus connection for serial: %s", err)
            self.client = None

class ModbusTcpHub:
    """Manages TCP connection."""
    def __init__(self, hass: HomeAssistant, host: str, port: int):
        """Initialize the TCP hub."""
        self.hass = hass
        self.host = host
        self.port = port
        self.client = AsyncModbusTcpClient(
            host=host,
            port=port,
            timeout=5,
        )

    async def close(self):
        """Close the connection safely."""
        if self.client is not None:
            if self.client.connected:
                try:
                    self.client.close()
                except Exception as err:
                    _LOGGER.exception("Unexpected error closing modbus connection for tcp: %s", err)
            self.client = None
