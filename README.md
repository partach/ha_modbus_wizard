# Modbus Wizard

[![Home Assistant](https://img.shields.io/badge/Home_Assistant-00A1DF?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square)](https://hacs.xyz)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/partach/ha_modbus_wizard/validate-hacs.yml?label=HACS%20Action&style=flat-square)](https://github.com/partach/ha_modbus_wizard/actions)
[![Installs](https://img.shields.io/github/downloads/partach/ha_modbus_wizard/total?color=28A745&label=Installs&style=flat-square)](https://github.com/partach/ha_modbus_wizard/releases)
[![License](https://img.shields.io/github/license/partach/ha_modbus_wizard?color=ffca28&style=flat-square)](https://github.com/partach/ha_modbus_wizard/blob/main/LICENSE)
[![HACS validated](https://img.shields.io/badge/HACS-validated-41BDF5?style=flat-square)](https://github.com/hacs/integration)

ModbusWizard will help you test and build all your modbus devices **without need for any yaml** or Home Assistant reboots <br>
(after install of this integration;)!

WORK IN PROGRESS

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/ha-modbus-wizard-config-6.png" width="600"/>
  <br><em>Configure your entities runtime</em>
</p>

## Features
- No need for any yaml configuration!
- Serial and IP (TCP/UDP) Modbus support
- USB/Serial port selection via dropdown
- Runtime adding / changing of register (entities). No reboots!
- UI card that lets you poll (read) or write ANY register (you can play around with the device at will)
- Hassle free use of the device you control, only create entities you need if you want to keep/use sensors of that device in HA
- Multiple hubs supported, ability to add multiple modbus devices and entities per device.
- configurable refresh speeds for data
- Automations possible, read and write on modbus!
- Very easy and straight forward!
- 
## Serial and TCP Modbus
It supports modbus USB dongle and IP (TCP/UDP) Modbus connections<br>

## Installation
Options:
1. Install via HACS (is coming in the near future)
2. Install manually:
   * The integration: In UI go to `HACS`--> `custom repositories` --> `Repo`: partach/ha_modbus_wizard, `Type`: Integration
   * After HA reboot (Needed for new integrations): choose 'add integration' (in devices and services) and choose `ha_modbus_wizard` in the list.

## Installing the card
After installation of the integration you need to first reboot HA. The card will be automatically registered by the integration on start up.<br>
But a browser refresh is needed to see it for the first time...<br>
To use the card in your dashboard, go to you dashboard, edit, choose `Add card`<br>
**It can be found in the card overview at custom cards**.<br>

Or.. Choose `Manual / yaml` Add first line: `type: custom:modbus_wizard-card`. <br>
Then choose the `visual editor` to continue. From the `Device` dropdown chose your Modbus Wizard device.

## How does it work?

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-2.png" width="200" style="vertical-align: middle; margin: 0 10px;"/>
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-3.png" width="200" style="vertical-align: middle; margin: 0 10px;"/>
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-1.png" width="600" style="vertical-align: middle; margin: 0 10px;"/>
<br><em>Steps 1, 2, 3</em>
</p>

Steps:<br>
1. Tell in the first dialog if the device you want to control is a serial or modbus over IP device and indicate:
    * Where you think the first register is at (The Address, often 0),
    * How big the size / count of the register to read is (often 1 or 2)
    * Which slave id the device is at (often 1 but you can have up to 255 devices in a single network)
    * Optionally already indicate what you want as refresh rate (can be changed in options later)

2. Give the device a usefull name and provide addtional communication details
    * In case of serial: which usb port the device is located. In case of IP which protocol (TCP/UDP)
    * In case of serial: baud rate, etc. In case of IP: port number

Based on this information the integration will auto test if it can find the regiser with different read methods.<br>
If succesfull, you have reached step 3 and basically the device is installed and the card can be used to freely peek and poke te device. <br>
If not successfull there can be a problem with the settings (wrong usb, wrong port, wrong register address, ...)

## After successfull device install (and device connection)

Basically you can go 2 directions
1. Use the card to probe your device
2. If you already know the registers you want to turn into entities (sensors) you can add them.

### Route 1
The HA card (see figure below). 
After selecting the wizard device in the dropdown during creation of the card, you will be able to read / write registers at will.
This will help you find the values you need. Once you have the right data you can turn these into entities for you integration that then can be used in HA. (Route 2)
<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-card.png" width="300"/>
  <br><em>Probe your connected modbus device at will</em>
</p>
Use of the card is pretty straight forward. Enter Address of the register, type of register, press read and get the data you need. 

### Route 2
If you know your stuff you can start adding entities for the registers you want from your modbus device.
These will be stored an rembered as any other sensors you have in HA.
Per register you can already enter a lot of data the integration will use. See table below for more detail
<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-5.png" width="300"/>
  <br><em>Probe your connected modbus device at will</em>
</p>

Once you registered your register it will become available in the device entities and will be monitored just like any entity in HA.
You can also edit them or  delete them (see first picture above in the readme)

#### Modbus Wizard Register Configuration Fields

When adding or editing a register in the Modbus Wizard integration, the following fields are available:

| Field             | Type / Default              | What to Enter                                                                 | Purpose / Effect                                                                                                                       |
|-------------------|-----------------------------|-------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| **name**          | Required string             | Human-readable name (e.g., "Phase 1 Voltage")                                 | Displayed as the entity name in Home Assistant. Also used to generate the unique data key.                                          |
| **address**       | Required number (0–65535)   | Modbus register address in decimal                                            | The register address to read/write on the device.                                                                                      |
| **data_type**     | Required dropdown, default `uint16` | `uint16`, `int16`, `uint32`, `int32`, `float32`, `uint64`, `int64`            | How to interpret the raw register(s). Automatically sets the number of registers to read (`size`).                                   |
| **register_type** | Required dropdown, default `auto` | `auto`, `holding`, `input`, `coil`, `discrete`                                | Modbus function code to use. `auto` tries holding → input → coil → discrete until successful.                                        |
| **rw**            | Required dropdown, default `read` | `read`, `write`, `rw`                                                         | Controls entity type: read-only sensor, writeable number entity, or both.                                                              |
| **unit**          | Optional string             | Unit of measurement (e.g., "V", "A", "W", "kWh", "%")                         | Shown in Home Assistant (unit_of_measurement). Helps with grouping and display.                                                        |
| **scale**         | Optional float, default `1.0` | Multiplier (e.g., `0.01` for divide-by-100, `10` for multiply-by-10)          | Applied after decoding: `final_value = decoded × scale + offset`. Very common for scaled integers.                                    |
| **offset**        | Optional float, default `0.0` | Additive offset (e.g., `-40` for temperature sensors)                         | `final_value = decoded × scale + offset`.                                                                                              |
| **options**       | Optional string (JSON)      | JSON mapping, e.g. `{"0": "Off", "1": "On", "2": "Auto"}`                      | Creates a select entity with friendly labels instead of raw numeric values.                                                            |
| **byte_order**    | Optional dropdown, default `big` | `big` or `little`                                                             | Byte order inside each 16-bit word (for multi-register types like uint32/float32).                                                    |
| **word_order**    | Optional dropdown, default `big` | `big` or `little`                                                             | Order of the 16-bit words (high word first or low word first) for multi-register values.                                               |
| **allow_bits**    | Optional boolean, default `False` | Check to allow testing coil/discrete registers during auto-detection          | Enables coil/discrete attempts when `register_type` is `auto`.                                                                        |
| **min**           | Optional float              | Minimum value for a writeable number entity                                   | Lower bound for the number input slider in the UI.                                                                                     |
| **max**           | Optional float              | Maximum value for a writeable number entity                                   | Upper bound for the number input slider in the UI.                                                                                     |
| **step**          | Optional float, default `1` | Step size for number entity (e.g., `0.1`, `1`, `10`)                           | Controls granularity of adjustments in the Home Assistant UI.                                                                          |

### Quick Tips for Common Use Cases
- **Voltages/Currents**: `data_type = "uint16"`, `scale = 0.01` or `0.1`, appropriate `unit`.
- **Power (W or kW)**: Often `uint16` or `uint32` with `scale = 1` or `10`.
- **True floating-point values**: Use `float32` (reads 2 registers) and correct `byte_order`/`word_order`.
- **Status bits**: Use `coil` or `discrete` with `options` JSON for friendly names.

These fields give full flexibility for virtually any Modbus device!

## Discussion 
See [here](https://github.com/partach/ha_modbus_wizard/discussions)

## Changelog
See [CHANGELOG.md](https://github.com/partach/ha_modbus_wizard/blob/main/CHANGELOG.md)

## Issues
Report at GitHub [Issues](https://github.com/partach/ha_modbus_wizard/issues)

## Support development
If you like it and find it usefull, or want to support this and future developments, it would be greatly appreciated :)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg?style=flat-square)](https://paypal.me/therealbean)
