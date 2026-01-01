# ha_modbus_wizard
ModbusWizard will help you build your modbus device without need for any yaml!

# Modbus Wizard Register Configuration Fields

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
