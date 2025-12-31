"""Constants for the Modbus Wizard integration."""

DOMAIN = "ha_modbus_wizard"

# Connection types
CONNECTION_TYPE_SERIAL = "serial"
CONNECTION_TYPE_IP = "ip"
CONNECTION_TYPE_TCP = "tcp"
CONNECTION_TYPE_UDP = "udp"

# Common settings
CONF_SLAVE_ID = "slave_id"
CONF_CONNECTION_TYPE = "connection_type"
CONF_NAME = "name"
CONF_FIRST_REG = "first_register"
CONF_FIRST_REG_SIZE = "first_register_size"
# Serial settings
CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_BYTESIZE = "bytesize"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_REGISTERS = "registers"
# TCP settings
CONF_HOST = "host"
CONF_PORT = "port"
CONF_PROTOCOL = "protocol"

# Defaults
DEFAULT_SLAVE_ID = 1
DEFAULT_BAUDRATE = 9600
DEFAULT_TCP_PORT = 502
DEFAULT_STOPBITS = 1
DEFAULT_BYTESIZE = 8
DEFAULT_PARITY = "N"
DEFAULT_UPDATE_INTERVAL = 10

def reg_key(name: str) -> str:
    return name.lower().strip().replace(" ", "_")
