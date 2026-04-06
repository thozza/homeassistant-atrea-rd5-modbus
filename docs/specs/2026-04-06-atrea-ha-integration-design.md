# Atrea RD5 Home Assistant Integration — Design Spec

## Problem Statement

The Atrea RD5 HVAC unit exposes a Modbus TCP API. The goal is a clean, self-contained
Home Assistant custom integration that provides read-only sensor entities for temperatures,
ventilation mode, and ventilation power — with a scalable architecture that can support tens
of registers as the integration grows.

## Scope (v1)

**In scope:**
- 5 temperature sensors (internal air path sensors from Input registers)
- 1 ventilation power sensor (current requested power, Holding register)
- 1 ventilation mode sensor (current operation mode, Holding register, enum)
- Config flow UI for connection setup with real connection validation
- Batch Modbus reads for efficiency

**Out of scope (future):**
- Write support (set mode, set power)
- Binary sensors (filter status, frost alerts)
- Additional sensors (humidity, pressure diff, CP Touch, fan output voltages, external TU1/TU2)
- Fan / Climate platform entities

## Architecture

### File Structure

```
custom_components/atrea_rd5_modbus/
├── __init__.py          # Integration setup: creates coordinator, forwards to sensor platform
├── coordinator.py       # DataUpdateCoordinator: owns pymodbus client, batch reads
├── const.py             # Register map definitions, domain, defaults
├── sensor.py            # Sensor platform: 7 sensor entities
├── config_flow.py       # UI config flow with connection validation
├── manifest.json        # pymodbus requirement, no modbus integration dependency
├── icon.png             # Integration icon (256×256) — copied from repo root
├── icon@2x.png          # High-DPI icon (512×512) — copied from repo root
└── strings.json
    translations/
        en.json
```

Root-level icon files (`icon.png`, `icon@2x.png`, `logo.png`) are kept in the repo root for
reference/branding. The `icon.png` and `icon@2x.png` files must also be placed inside the
integration folder for HA to display them.

### Data Flow

1. User runs Config Flow → enters host/port/slave_id/scan_interval → validation attempts real Modbus connection → config entry created.
2. `async_setup_entry` in `__init__.py` creates `AtreaCoordinator`, calls `async_config_entry_first_refresh()`.
3. On each poll, coordinator groups register map entries by (register_type, contiguous address ranges), issues one Modbus request per batch, decodes and stores `dict[key → value]`.
4. Sensor entities extend `CoordinatorEntity`, read their key from coordinator data.
5. On `async_unload_entry`, coordinator closes pymodbus client.

## Register Map (v1)

All addresses match the Atrea RD5 Modbus TCP specification (document dated 9.5.2017).

| Key | Address | Modbus Type | Description | Conversion |
|-----|---------|------------|-------------|------------|
| `temp_oda` | 10211 | Input | T-ODA — outdoor air temperature | `signed10(val)` |
| `temp_sup` | 10212 | Input | T-SUP — supply air temperature | `signed10(val)` |
| `temp_eta` | 10213 | Input | T-ETA — extract air temperature (entering unit) | `signed10(val)` |
| `temp_eha` | 10214 | Input | T-EHA — exhaust air temperature (leaving unit) | `signed10(val)` |
| `temp_ida` | 10215 | Input | T-IDA — indoor/room temperature | `signed10(val)` |
| `power` | 10704 | Holding | Current requested ventilation power | raw (0–100%) |
| `mode` | 10705 | Holding | Current operation mode | enum (0–7) |

**Temperature encoding** (per spec):
```
signed10(val):
  if val <= 32767: return val / 10.0    # positive: 1..1300 → 0.1..130.0°C
  else:            return (val - 65536) / 10.0  # negative: 65036..65535 → −50.0..−0.1°C
```

**Mode enum mapping:**
```
0 → "Off"
1 → "Automatic"
2 → "Ventilation"
3 → "Circulation+Ventilation"
4 → "Circulation"
5 → "Night cooling"
6 → "Redistribution"
7 → "Overpressure"
```

## Coordinator Design

### Connection Management

- Uses `pymodbus.client.AsyncModbusTcpClient`.
- Client is created and connected in `__init__.py` before the coordinator's first refresh.
- The client is passed to the coordinator (not created by it) so it can also be used in config flow validation.
- On unload, `client.close()` is called.
- pymodbus maintains a persistent TCP connection across polls — no reconnect per poll.
- If connection is lost, pymodbus reconnects automatically on the next request.

### Batch Read Algorithm

At coordinator init time, the register map is compiled into **batch groups**:

```
Group registers by type (Input vs Holding).
Within each type, sort by address.
Merge registers with consecutive addresses into one range.
Result: list of BatchGroup(type, start_addr, count, [keys in order])
```

For v1 this yields:
- Batch 1: Input registers 10211–10215 (count=5) → keys: temp_oda, temp_sup, temp_eta, temp_eha, temp_ida
- Batch 2: Holding registers 10704–10705 (count=2) → keys: power, mode

On each `_async_update_data()`:
1. For each batch group, issue one Modbus read request.
2. Map results back using `address - batch_start_address` as offset.
3. Apply conversion function → store as `data[key] = converted_value`.
4. If one batch fails: log warning, set affected keys to `None` (partial update).
5. If all batches fail: raise `UpdateFailed`.

### Extensibility

To add a new sensor in the future:
1. Add one entry to `REGISTER_MAP` in `const.py` with address, type, and conversion.
2. Add one entry to `SENSOR_DESCRIPTIONS` in `sensor.py`.
3. The coordinator batch grouping is recomputed automatically at startup.

## Sensor Platform

### Sensor Definitions

| Entity | Sensor Key | Device Class | Unit | State Class | Notes |
|--------|-----------|-------------|------|-------------|-------|
| T-ODA Outdoor Air | `temp_oda` | `TEMPERATURE` | °C | `MEASUREMENT` | |
| T-SUP Supply Air | `temp_sup` | `TEMPERATURE` | °C | `MEASUREMENT` | |
| T-ETA Extract Air | `temp_eta` | `TEMPERATURE` | °C | `MEASUREMENT` | |
| T-EHA Exhaust Air | `temp_eha` | `TEMPERATURE` | °C | `MEASUREMENT` | |
| T-IDA Indoor Air | `temp_ida` | `TEMPERATURE` | °C | `MEASUREMENT` | |
| Ventilation Power | `power` | (none) | % | `MEASUREMENT` | see note below |
| Ventilation Mode | `mode` | `ENUM` | (none) | (none) | enum options list |

All entities:
- Unique ID: `{entry_id}_{key}`
- Device info: linked to single device "Atrea RD5 @ {host}"
- Available: `coordinator.last_update_success and data[key] is not None`

### Power Sensor

`device_class` is intentionally `None` — there is no HA `SensorDeviceClass` that semantically
matches a ventilation power level percentage. Candidates like `POWER` (expects Watts),
`POWER_FACTOR` (electrical concept), `BATTERY`, or `HUMIDITY` all carry incorrect semantics
despite accepting `%` as a unit.

**History graphs are unaffected.** `SensorStateClass.MEASUREMENT` (already set) is what drives
long-term statistics recording and line graph rendering in HA — `device_class` is not required
for this. The `%` unit will display correctly in the UI without a device class.

### Mode Sensor

Uses `SensorDeviceClass.ENUM` with explicit `options` list. State changes are tracked in HA
history as a timeline (not a numeric graph), allowing full audit of mode changes over time.

## Config Flow

Fields:
- `host` (required): IP address of the Atrea RD5 device
- `port` (optional, default 502): Modbus TCP port
- `slave_id` (optional, default 1): Modbus slave/unit ID
- `scan_interval` (optional, default 30): Poll interval in seconds

Validation step: creates a temporary `AsyncModbusTcpClient`, attempts to read one register
(H10705 — mode), then closes. On failure: shows "cannot_connect" error in form.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Connection fails at startup | Raise `ConfigEntryNotReady`; HA retries with backoff |
| One batch read fails during poll | Log warning; affected entity states → `None` (unavailable) |
| All batches fail during poll | Raise `UpdateFailed`; all entities → unavailable |
| Connection drops between polls | pymodbus reconnects transparently on next request |
| Invalid/out-of-range register value | Conversion returns `None`; entity → unavailable |

## Testing

- Unit tests for the `signed10()` conversion function (positive, zero, negative, boundary values)
- Unit tests for batch group compilation from register map
- Integration tests with mocked pymodbus client (using `pytest-homeassistant-custom-component`)
- Config flow tests: success path, connection failure path
