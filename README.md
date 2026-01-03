# Modbus Wizard

[![Home Assistant](https://img.shields.io/badge/Home_Assistant-00A1DF?style=flat-square&logo=home-assistant&logoColor=white)](https://www.home-assistant.io)
[![HACS](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat-square)](https://hacs.xyz)
[![HACS Action](https://img.shields.io/github/actions/workflow/status/partach/ha_modbus_wizard/validate-hacs.yml?label=HACS%20Action&style=flat-square)](https://github.com/partach/ha_modbus_wizard/actions)
[![Installs](https://img.shields.io/github/downloads/partach/ha_modbus_wizard/total?color=28A745&label=Installs&style=flat-square)](https://github.com/partach/ha_modbus_wizard/releases)
[![License](https://img.shields.io/github/license/partach/ha_modbus_wizard?color=ffca28&style=flat-square)](https://github.com/partach/ha_modbus_wizard/blob/main/LICENSE)
[![HACS validated](https://img.shields.io/badge/HACS-validated-41BDF5?style=flat-square)](https://github.com/hacs/integration)

# Modbus Wizard for Home Assistant

**Configure and control Modbus devices entirely from the UI — no YAML, no restarts!**

Modbus Wizard lets you discover, test, and integrate Modbus devices (serial or TCP/UDP) directly in Home Assistant — all through a simple, powerful interface.

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/ha-modbus-wizard-config-6.png" width="600" alt="Runtime entity configuration"/>
  <br><em>Add and configure sensors at runtime — no reboots required</em>
</p>

**Work in progress — actively developed and improving!**

## Features

- **Zero YAML configuration** — everything done via the Home Assistant UI
- Full support for **serial (RS485/USB)** and **IP-based Modbus (TCP & UDP)**
- **Runtime entity management** — add, edit, or remove sensors without restarting HA
- Dedicated **Lovelace card** for live reading/writing any register (perfect for testing and debugging)
- Create only the entities you need — keep your setup clean and efficient
- Multiple devices supported simultaneously
- Configurable refresh intervals per device
- Full automation support — use sensors in automations, scripts, and dashboards
- Advanced options: scaling, offset, byte/word order, bit handling, and more

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-card.png" width="350" alt="Modbus Wizard Card"/>
  <br><em>Probe and control any register in real-time with the included card</em>
</p>

## Installation

### Option 1: HACS (Recommended — coming soon)
Once available in HACS default repository, install with one click.

### Option 2: Manual Install
1. Go to **HACS → Integrations → ⋮ → Custom repositories**
2. Add repository:  
   URL: `https://github.com/partach/ha_modbus_wizard`  
   Category: **Integration**
3. Click **Add**
4. Search for "Modbus Wizard" and install
5. **Restart Home Assistant**
6. Go to **Settings → Devices & Services → + Add Integration** → Search for **Modbus Wizard**

> The included Lovelace card is automatically registered on startup.  
> A browser refresh may be needed the first time to see it.

## Setup Guide

### Step 1: Add Your Modbus Device
1. Click **+ Add Integration** → Choose **Modbus Wizard**
2. Select connection type: **Serial** or **IP (TCP/UDP)**
3. Enter:
   - Slave ID (usually 1)
   - A test register address (often 0 or 30001 → use 0 in the integration)
   - Test register size (usually 1 or 2)
4. Provide connection details (port, baudrate, host, etc.)
5. The integration will auto-test connectivity

→ Success? You're ready!

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-2.png" width="200" alt="Step 1"/>
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-3.png" width="200" alt="Step 2"/>
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-1.png" width="600" alt="Step 3"/>
  <br><em>Simple 3-step device setup</em>
</p>

### Step 2: Explore with the Card (Recommended for Discovery)
Add the **Modbus Wizard Card** to a dashboard:
- Edit dashboard → Add card → Search for **"Modbus Wizard Card"**
- Select your device

Now you can:
- Read any register instantly
- Write values to test device behavior
- Experiment with data types, byte order, and scaling

Perfect for reverse-engineering undocumented devices!

### Step 3: Create Permanent Sensors
Once you know which registers you want:
- Go to your Modbus Wizard device → **Configure** → **Add register**
- Fill in name, address, data type, unit, scaling, etc.
- Advanced options available (click "Show advanced options")

<p align="center">
  <img src="https://github.com/partach/ha_modbus_wizard/blob/main/HA-modbus-wizard-config-5.png" width="400" alt="Add register form"/>
  <br><em>Full control over sensor configuration</em>
</p>

Your new sensors appear immediately — no restart needed.

You can later edit or delete them from the same options menu.

## Why Choose Modbus Wizard?

- **No more YAML hell** — perfect for devices with poor documentation
- **Fast iteration** — test registers live, then save only what you need
- **Beginner-friendly** yet powerful for advanced users
- **Full control** — bit-level access, custom scaling, endianness, raw mode



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

## Support & Feedback

This integration is under active development. Found a bug? Have a feature request?

→ Open an issue on GitHub: https://github.com/partach/ha_modbus_wizard/issues

Contributions welcome, see below!

---

**Made with ❤️ for the Home Assistant community**

## Discussion 
Once requests are there will be opened here: [here](https://github.com/partach/ha_modbus_wizard/discussions)

## Changelog
See [CHANGELOG.md](https://github.com/partach/ha_modbus_wizard/blob/main/CHANGELOG.md)

## Support development
If you like it and find it usefull, or want to support this and future developments, it would be greatly appreciated :)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg?style=flat-square)](https://paypal.me/therealbean)
