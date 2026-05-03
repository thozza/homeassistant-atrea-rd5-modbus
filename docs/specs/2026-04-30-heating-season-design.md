# Heating Season (TS/NTS) Support

**Date:** 2026-04-30

## Overview

Add support for the three Modbus holding registers that expose and control the
Atrea RD5 heating/non-heating season logic:

| Register | Key | R/W | Description |
|---|---|---|---|
| I11401 | `season` | R | Current season: Heating (0) / Non-heating (1) |
| H11401 | `season_switch` | R/W | Season switch mode: TS, NTS, T-TODA, T-TODA+ |
| H11402 | `season_temp_thr` | R/W | Season temperature threshold (0–30 °C) |

I11401 is exposed as a read-only diagnostic sensor. H11401 is a config select.
H11402 is a config number that reads back from the device (coordinator-backed,
not RestoreNumber).

---

## Architecture

No new files. Five existing files change:

| File | Change |
|---|---|
| `const.py` | New dicts, converters, 3 REGISTER_MAP entries, 2 WRITE_REGISTER_MAP entries |
| `sensor.py` | 1 new ENUM sensor description (H11400) |
| `select.py` | 1 new select description (H11401) |
| `number.py` | New `AtreaNumber` coordinator-backed class + 1 description (H11402) |
| `tests/` | 4 test files updated |

`season` lives in a separate input batch (I11401). `season_switch` and
`season_temp_thr` form a 2-register holding batch (H11401–H11402).
`build_batch_groups()` handles both automatically. Holding batch count: 2 → 3,
input batch count: 1 → 2. `coordinator.py` requires no changes.

---

## `const.py`

### New lookup tables

```python
SEASON_STATES: dict[int, str] = {0: "Heating", 1: "Non-heating"}
SEASON_STATE_OPTIONS: list[str] = list(SEASON_STATES.values())

def _convert_season(val: int) -> str | None:
    return SEASON_STATES.get(val)

SEASON_SWITCH: dict[int, str] = {0: "TS", 1: "NTS", 2: "T-TODA", 3: "T-TODA+"}
SEASON_SWITCH_OPTIONS: list[str] = list(SEASON_SWITCH.values())
SEASON_SWITCH_INV: dict[str, int] = {v: k for k, v in SEASON_SWITCH.items()}

def _convert_season_switch(val: int) -> str | None:
    return SEASON_SWITCH.get(val)
```

### REGISTER_MAP additions

```python
"season":          RegisterEntry(11401, RegisterType.INPUT,   _convert_season),
"season_switch":   RegisterEntry(11401, RegisterType.HOLDING, _convert_season_switch),
"season_temp_thr": RegisterEntry(11402, RegisterType.HOLDING, signed10),
```

### WRITE_REGISTER_MAP additions

H11400 is read-only — no write entry.

```python
"season_switch":   WriteRegisterEntry(11401, RegisterType.HOLDING, lambda v: SEASON_SWITCH_INV[v]),
"season_temp_thr": WriteRegisterEntry(11402, RegisterType.HOLDING, encode_signed10),
```

---

## `sensor.py`

New description appended to `SENSOR_DESCRIPTIONS`. Reads from I11401.
Imports `SEASON_STATE_OPTIONS` (not `SEASON_SWITCH_OPTIONS`).

```python
AtreaSensorEntityDescription(
    key="season",
    name="Heating Season",
    device_class=SensorDeviceClass.ENUM,
    options=SEASON_STATE_OPTIONS,
    entity_category=EntityCategory.DIAGNOSTIC,
),
```

---

## `select.py`

New description appended to `SELECT_DESCRIPTIONS`. Reads/writes H11401.
Imports `SEASON_SWITCH_OPTIONS` (not `SEASON_STATE_OPTIONS`).

```python
AtreaSelectEntityDescription(
    key="season_switch",
    name="Season Switch Mode",
    write_key="season_switch",
    options=SEASON_SWITCH_OPTIONS,
    entity_category=EntityCategory.CONFIG,
),
```

---

## `number.py`

### New description dataclass

```python
@dataclass(frozen=True, kw_only=True)
class AtreaCoordinatorNumberEntityDescription(NumberEntityDescription):
    write_key: str
```

### New entity class

Reads `native_value` from `coordinator.data` (like `AtreaSelect`). Writes via
`coordinator.async_write`. No restore logic — the device holds the value.

```python
class AtreaNumber(CoordinatorEntity[AtreaCoordinator], NumberEntity):
    entity_description: AtreaCoordinatorNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.get(self.entity_description.key) is not None
        )

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(self.entity_description.write_key, value)
        self.async_write_ha_state()
```

### New description

```python
COORDINATOR_NUMBER_DESCRIPTIONS: tuple[AtreaCoordinatorNumberEntityDescription, ...] = (
    AtreaCoordinatorNumberEntityDescription(
        key="season_temp_thr",
        name="Season Temperature Threshold",
        write_key="season_temp_thr",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=0.0,
        native_max_value=30.0,
        native_step=0.1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)
```

### Updated `async_setup_entry`

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        *[AtreaBmsNumber(coordinator, desc) for desc in NUMBER_DESCRIPTIONS],
        *[AtreaNumber(coordinator, desc) for desc in COORDINATOR_NUMBER_DESCRIPTIONS],
    ])
```

---

## Tests

### `test_coordinator.py`
- Mock input batch at I11401 (season) and holding batch at H11401–H11402
  (season_switch, season_temp_thr) with sample raw values.
- Assert `season`, `season_switch`, `season_temp_thr` in `coordinator.data` with
  correctly decoded values.
- Assert input batch failure sets `season` to `None`; holding batch failure sets
  `season_switch` and `season_temp_thr` to `None`.

### `test_sensor.py`
- `season` = `"Heating"` when register = 0.
- `season` = `"Non-heating"` when register = 1.
- Entity unavailable when coordinator data is `None`.

### `test_select.py`
- `current_option` reflects coordinator data for `season_switch`.
- `async_select_option` calls `coordinator.async_write` with correct key and each
  of the 4 string options.

### `test_number.py`
- `AtreaNumber.native_value` reads from coordinator data.
- `async_set_native_value` calls `coordinator.async_write` with `"season_temp_thr"`.
- Entity unavailable when data key is `None`.
- No restore/startup behaviour (unlike `AtreaBmsNumber`).
