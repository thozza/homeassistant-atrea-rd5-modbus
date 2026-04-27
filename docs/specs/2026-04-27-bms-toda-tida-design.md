# BMS T-ODA / T-IDA support — Design

**Date:** 2026-04-27
**Status:** Approved (pending implementation plan)

## Goal

Add support for the Atrea RD5 "Sending T-IDA, T-ODA from BMS" feature
(Czech: *Zasílání T-IDA, T-ODA z BMS*) so a Home Assistant user can:

1. View and configure the T-ODA and T-IDA temperature source on the HVAC
   (internal sensor vs. BMS / from another sensor).
2. Push T-ODA and T-IDA values from HA to the HVAC, e.g. driven by an
   automation that reads another HA temperature sensor.

The HVAC declares a sensor fault if a BMS-sourced value is not refreshed
within 90s; the design must keep the user inside that constraint.

## Spec excerpt

| Register | R/W | Range | Meaning |
|----------|-----|-------|---------|
| C10510 | R/W | 0/1 | T-ODA source: 0 = internal HVAC sensor, 1 = BMS (Modbus) |
| H10213 | R/W | 0..65535 | T-ODA value written from BMS (signed10 encoding) |
| H10514 | R/W | 0..3 | T-IDA source: 0=CP, 1=T-ETA, 2=TRKn, 3=BMS |
| H10214 | R/W | 0..65535 | T-IDA value written from BMS (signed10 encoding) |

> The value must be refreshed periodically. If no value is sent to the
> corresponding registers for more than 90s, the HVAC unit declares a
> temperature sensor fault.

## Architectural decisions

### Write-on-set, no internal push loop

The BMS temperature `number` entities write to the HVAC immediately on
`async_set_native_value`. The integration does **not** maintain its own
periodic push loop. The 90s watchdog is satisfied by the user's HA
automation (which is what produces the value to be sent in the first
place — typically reading another temperature sensor).

This matches the official `homeassistant.components.modbus` integration's
pattern for writable entities and keeps the integration simple.

**HA-restart edge case** — `RestoreNumber` recovers the last value into
the entity's state on startup, but does not re-write to the device.
We handle this in `async_added_to_hass`: if a value is restored, push it
to the HVAC immediately so the watchdog window starts fresh.

The 90s constraint is documented in the README and surfaced in the
entity description text. Recommended automation cadence is ≤60s for
margin.

### Options flow for `scan_interval`

`scan_interval` moves into a HA options flow (no connection
re-validation). Connection details (host / port / slave_id) stay locked
to the initial setup flow — changing the host means a different device,
which is a unique_id change and warrants re-adding the integration.

The coordinator reads `scan_interval` from `entry.options` first, falling
back to `entry.data` for entries created before this feature.

### Extend `RegisterType` to include `COIL`

C10510 is a coil register. The existing batch system handles only
`INPUT` and `HOLDING`. Add `COIL = "coil"` to `RegisterType` and extend
`build_batch_groups` and the coordinator's read loop to call
`read_coils`.

`read_coils` returns `result.bits` (a `list[bool]` padded to a multiple
of 8) instead of `result.registers`. The coordinator normalizes both
into `list[int]` before the per-key conversion, so register entries
have a single uniform `convert(int) -> ...` signature.

### Separate `WRITE_REGISTER_MAP`

Writes have different semantics from reads (no batching, encoder rather
than decoder), so a separate `WRITE_REGISTER_MAP` keeps each map
focused. Read-write registers (`toda_source`, `tida_source`) appear in
both maps under the same key.

```python
@dataclass(frozen=True)
class WriteRegisterEntry:
    address: int
    register_type: RegisterType   # HOLDING or COIL
    encode: Callable[[Any], int]
```

The coordinator gains a single `async_write(key, value)` helper that
looks up the entry, encodes, and dispatches to `write_register` or
`write_coil`. Select and number platforms call this helper rather than
touching the modbus client directly.

After a successful write the coordinator calls
`async_request_refresh()` so read-back state for select entities
updates promptly. The call is debounced by HA, so it doesn't cause
redundant polling.

### Validation at entity boundary, not encoder

HA service handlers validate `number.set_value` against
`native_min_value` / `native_max_value` and `select.select_option`
against the entity's `options` list. Out-of-range automation calls fail
at the service layer before reaching our encoder. The encoders therefore
don't need defensive `KeyError` / range guards.

`step` is a UI hint, not strictly enforced — `encode_signed10` uses
`round(temp_c * 10)` which handles values between steps gracefully.

## Components

### File-level changes

| File | Change |
|------|--------|
| `const.py` | `RegisterType.COIL`; new register entries (C10510, H10514) in `REGISTER_MAP`; `WRITE_REGISTER_MAP` with H10213/H10214/C10510/H10514; `encode_signed10`; source enums and reverse maps |
| `coordinator.py` | Handle `COIL` in batch reader; add `async_write(key, value)` helper |
| `select.py` *(new)* | T-ODA Source, T-IDA Source as `CoordinatorEntity` selects with `EntityCategory.CONFIG` |
| `number.py` *(new)* | BMS T-ODA Setpoint, BMS T-IDA Setpoint as `RestoreNumber` entities; restore-and-push-on-startup |
| `config_flow.py` | `AtreaOptionsFlow` editing `scan_interval`; `async_get_options_flow` on the main flow |
| `__init__.py` | Register `SELECT` and `NUMBER` platforms; install update listener that reloads the entry on options change |

`manifest.json` requires no change.

### Register map

Read map (`REGISTER_MAP`) gains:

| Key | Address | Type | `convert` |
|-----|---------|------|-----------|
| `toda_source` | 10510 | COIL | lookup → `"Internal"` / `"BMS"` |
| `tida_source` | 10514 | HOLDING | lookup → `"CP"` / `"T-ETA"` / `"TRKn"` / `"BMS"` |

Write map (`WRITE_REGISTER_MAP`):

| Key | Address | Type | `encode` |
|-----|---------|------|----------|
| `bms_toda` | 10213 | HOLDING | `encode_signed10` |
| `bms_tida` | 10214 | HOLDING | `encode_signed10` |
| `toda_source` | 10510 | COIL | `lambda v: TODA_SOURCES_INV[v]` |
| `tida_source` | 10514 | HOLDING | `lambda v: TIDA_SOURCES_INV[v]` |

Resulting batches from `build_batch_groups`:

1. INPUT 10211–10215 — five temperatures (unchanged)
2. HOLDING 10704–10705 — power + mode (unchanged)
3. HOLDING 10514 — T-IDA source (new, separate batch due to address gap)
4. COIL 10510 — T-ODA source (new)

The spec's 5s minimum-interval-between-sessions constraint is satisfied
by the existing `scan_interval` minimum of 5s.

### Encoder

```python
def encode_signed10(temp_c: float) -> int:
    """Encode -50.0..130.0 °C as 16-bit register value (×10, two's complement)."""
    val = round(temp_c * 10)
    if val < 0:
        val += 65536
    return val
```

Round-trip with `signed10` is identity within ±0.05°C (the precision of
the encoding).

### Source enums

```python
TODA_SOURCES = {0: "Internal", 1: "BMS"}
TIDA_SOURCES = {0: "CP", 1: "T-ETA", 2: "TRKn", 3: "BMS"}
TODA_SOURCE_OPTIONS = list(TODA_SOURCES.values())
TIDA_SOURCE_OPTIONS = list(TIDA_SOURCES.values())
TODA_SOURCES_INV = {v: k for k, v in TODA_SOURCES.items()}
TIDA_SOURCES_INV = {v: k for k, v in TIDA_SOURCES.items()}
```

### Select platform

Two `CoordinatorEntity[AtreaCoordinator]` selects in
`EntityCategory.CONFIG`:

- `current_option` reads `coordinator.data[key]` (already a friendly
  string from `convert`).
- `async_select_option(option)` calls
  `coordinator.async_write(write_key, option)`.
- `available` requires `coordinator.last_update_success` and
  non-`None` data.

A small `_build_device_info(coordinator)` helper is extracted to avoid
duplicating the `DeviceInfo` construction across `sensor`, `select`,
`number`.

### Number platform

Two `RestoreNumber` entities in `EntityCategory.CONFIG`:

- `native_min_value=-50.0`, `native_max_value=130.0`,
  `native_step=0.1`, `mode=NumberMode.BOX`,
  `device_class=NumberDeviceClass.TEMPERATURE`,
  `native_unit_of_measurement=UnitOfTemperature.CELSIUS`.
- Not `CoordinatorEntity` — H10213/H10214 are write-only, never read.
- `async_set_native_value(value)` writes via
  `coordinator.async_write(write_key, value)`, then updates
  `_attr_native_value` and calls `async_write_ha_state()`.
- `async_added_to_hass`: after `super()`, call
  `async_get_last_number_data()`. If a value is found, set
  `_attr_native_value` and push it via `coordinator.async_write`. A
  `ModbusException` here is logged at WARNING and swallowed — the
  entity still presents the restored value, the user's automation will
  retry.

### Options flow

```python
class AtreaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        current = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_SCAN_INTERVAL, default=current):
                    vol.All(int, vol.Range(min=5, max=300)),
            }),
        )
```

`__init__.py` installs an update listener that reloads the entry on
options change. Coordinator construction reads `scan_interval` from
options first, falling back to `entry.data`.

## Data flow

```
Periodic poll (scan_interval, options-flow editable)
  → coordinator reads 4 batches: 5 input regs, 2 holding regs, 1 holding reg, 1 coil reg
    → sensor entities update from coordinator.data
    → select entities update current_option from coordinator.data

User/automation sets BMS T-ODA / T-IDA number entity
  → number.async_set_native_value
    → coordinator.async_write("bms_toda" | "bms_tida", value)
      → encode_signed10 → write_register(10213 | 10214)
    → entity state updated and written

User changes select entity option
  → select.async_select_option(option)
    → coordinator.async_write("toda_source" | "tida_source", option)
      → encode lambda → write_coil(10510) or write_register(10514)
    → coordinator.async_request_refresh() picks up the new value

HA restart
  → number.async_added_to_hass restores via RestoreNumber
  → if a value was restored, immediately coordinator.async_write to
    feed the HVAC watchdog before user automation resumes

Options flow change
  → update listener fires → hass.config_entries.async_reload(entry)
  → coordinator rebuilt with new scan_interval
```

## Error handling

- **Read failures** — unchanged from current behaviour: per-batch
  failures null out the affected keys; entities become unavailable;
  full failure raises `UpdateFailed` and HA backs off.
- **Write failures** (`async_write`) — `ModbusException` propagates
  from the coordinator to the entity service handler, surfaced to HA as
  a service call failure.
- **Restore-push failures on startup** — logged at WARNING, swallowed.
  The entity still presents the restored value; the user's automation
  retries on its next cycle.
- **HVAC watchdog timeout** — outside the integration's responsibility.
  Documented in README.

## Testing

Style: `asyncio_mode = "auto"`, table-driven where applicable.

| File | Coverage |
|------|----------|
| `tests/test_const.py` | `signed10` / `encode_signed10` round-trip; `build_batch_groups` produces expected groups; source enum reverse maps |
| `tests/test_coordinator.py` | COIL batch read (incl. 8-bit `bits` padding); coil-batch failure isolation; `async_write` for holding and coil; write error path |
| `tests/test_select.py` (new) | `current_option` reads from coordinator data; `available` False when key missing; `async_select_option` calls `async_write` once |
| `tests/test_number.py` (new) | `async_set_native_value` writes and updates state; restore-and-push on startup (with and without prior value); restore-push failure logs but doesn't raise |
| `tests/test_config_flow.py` | Options-flow happy path; range validation (rejects 4 and 301); update listener triggers reload |

`conftest.py` extends `mock_modbus_client` with default-success
`read_coils`, `write_coil`, `write_register` mocks.

## Documentation

README gains a "BMS Setpoints" section explaining:

- The two source select entities and how to switch the HVAC to
  BMS-sourced T-ODA / T-IDA.
- The two BMS setpoint number entities for writing values.
- The 90s HVAC watchdog and recommended automation cadence (≤60s).
- A worked example automation: read another HA temperature sensor,
  set the corresponding BMS number entity periodically.

## Out of scope

- Any other writable HVAC parameter (mode, power, requested
  temperature). Those have their own register groups and
  manual/scheduled-mode interlocks (H10700–H10717) that warrant a
  separate spec.
- Internal periodic push loop. Reconsider only if user feedback
  indicates automations alone are insufficient.
- An options flow for changing host / port / slave_id. Those are
  identity attributes; users re-add the integration to change them.
