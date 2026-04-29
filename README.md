<p align="center">
  <img src="icon@2x.png" alt="homeassistant-atrea-rd5-modbus" width="200">
</p>

# Atrea RD5 Modbus — Home Assistant Integration

[![CI](https://github.com/thozza/homeassistant-atrea-rd5-modbus/actions/workflows/ci.yml/badge.svg)](https://github.com/thozza/homeassistant-atrea-rd5-modbus/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Monitor your **Atrea RD5 ventilation unit** from Home Assistant using Modbus TCP.

## Features

- 🌡️ **5 temperature sensors**: outdoor air (T-ODA), supply air (T-SUP), extract air (T-ETA), exhaust air (T-EHA), indoor air (T-IDA)
- 🔄 **Ventilation mode**: tracks current mode (Off / Automatic / Ventilation / Circulation / Night cooling / ...)
- 💨 **Ventilation power**: current requested fan power (0–100%)
- Efficient batch Modbus reads — only 2 TCP requests per poll cycle
- Zero-YAML setup via Home Assistant UI config flow

## Requirements

- Home Assistant 2024.1.0 or newer
- Atrea RD5 unit with Modbus TCP enabled and accessible on the network (default port: 502)
- Python package `pymodbus >= 3.10.0` (installed automatically by HA)

## Installation

### Manual

1. Copy the `custom_components/atrea_rd5_modbus/` folder into your Home Assistant config directory:
   ```
   <config>/custom_components/atrea_rd5_modbus/
   ```
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**.
4. Search for **Atrea RD5 Modbus** and follow the setup wizard.

### HACS

1. In HACS, go to **Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/thozza/homeassistant-atrea-rd5-modbus` as type **Integration**.
3. Click **Download** on the Atrea RD5 Modbus card.
4. Restart Home Assistant.
5. Go to **Settings → Devices & Services → Add Integration** and search for **Atrea RD5 Modbus**.

## Configuration

The integration is configured entirely through the UI. During setup you will be asked for:

| Field | Default | Description |
|-------|---------|-------------|
| Host | — | IP address of the Atrea RD5 device |
| Port | `502` | Modbus TCP port |
| Slave ID | `1` | Modbus slave/unit ID |
| Scan interval | `30` | Poll frequency in seconds |

The connection is validated before the entry is saved — if the device is unreachable an error is shown in the form.

## Entities

| Entity | Unit | Description |
|--------|------|-------------|
| T-ODA Outdoor Air | °C | Outdoor air temperature (sensor T-ODA) |
| T-SUP Supply Air | °C | Supply air temperature after heat recovery (sensor T-SUP) |
| T-ETA Extract Air | °C | Room exhaust air entering the unit (sensor T-ETA) |
| T-EHA Exhaust Air | °C | Air leaving the unit to the outside (sensor T-EHA) |
| T-IDA Indoor Air | °C | Indoor/room air temperature (sensor T-IDA) |
| Ventilation Power | % | Current requested ventilation fan power (0–100%) |
| Ventilation Mode | — | Current operation mode (Off, Automatic, Ventilation, Circulation, ...) |
| T-ODA Source | — | Select: choose outdoor temp source (Internal / BMS) |
| T-IDA Source | — | Select: choose indoor temp source (CP / T-ETA / TRKn / BMS) |
| BMS T-ODA Setpoint | °C | BMS-supplied outdoor temp (write-only, −50–130 °C) |
| BMS T-IDA Setpoint | °C | BMS-supplied indoor temp (write-only, −50–130 °C) |

## BMS Setpoints (T-ODA / T-IDA from external sensors)

The Atrea RD5 can use temperatures supplied by Home Assistant in place
of its own outdoor (T-ODA) or indoor (T-IDA) sensors. This integration
exposes the relevant device registers as four entities:

| Entity | Type | Purpose |
|--------|------|---------|
| `select.atrea_rd5_t_oda_source` | select | Choose internal sensor or BMS-supplied T-ODA |
| `select.atrea_rd5_t_ida_source` | select | Choose CP / T-ETA / TRKn / BMS for T-IDA |
| `number.atrea_rd5_bms_t_oda_setpoint` | number | T-ODA value pushed to the HVAC |
| `number.atrea_rd5_bms_t_ida_setpoint` | number | T-IDA value pushed to the HVAC |

### 90-second watchdog

The HVAC declares a temperature-sensor fault if a BMS-sourced value is
not refreshed within **90 seconds**. The integration writes to the
device every time the number entity is set, but it does **not** run an
internal periodic push — that's left to your automation. Keep your
update cadence comfortably below 90 s (we recommend ≤60 s).

After a Home Assistant restart, each BMS setpoint number entity
restores its last known value and immediately writes it back to the
HVAC, so the watchdog window starts fresh before your automation's
next trigger.

### Example automation

```yaml
automation:
  - alias: "Atrea: push outdoor temperature from weather sensor"
    trigger:
      - platform: time_pattern
        seconds: "/30"
    action:
      - service: number.set_value
        target:
          entity_id: number.atrea_rd5_bms_t_oda_setpoint
        data:
          value: "{{ states('sensor.outdoor_temperature') | float }}"
```

Pair this with `select.atrea_rd5_t_oda_source` set to `BMS` so the
HVAC actually consumes the supplied value.

### Polling interval

The polling interval (default 30 s) is editable post-setup via
**Configure** on the integration tile in **Settings → Devices &
Services**. Allowed range: 5–300 s.

## Architecture

The integration uses a single `DataUpdateCoordinator` (`AtreaCoordinator`) that owns a persistent `AsyncModbusTcpClient` TCP connection. On each poll cycle, registers are read in **contiguous batches** — the 5 temperature sensors are fetched in one Modbus request (input registers 10211–10215), and power + mode in another (holding registers 10704–10705). This minimises network round-trips and scales well as more sensors are added.

```
custom_components/atrea_rd5_modbus/
├── __init__.py       # Integration setup, coordinator + client lifecycle
├── coordinator.py    # DataUpdateCoordinator, batched Modbus reads
├── const.py          # Register map, signed10() conversion, batch grouping
├── sensor.py         # 7 sensor entities
└── config_flow.py    # UI config flow with live connection validation
```

To add a new sensor in the future: add one entry to `REGISTER_MAP` in `const.py` and one entry to `SENSOR_DESCRIPTIONS` in `sensor.py`. Batch grouping is recomputed automatically.

## Troubleshooting

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.atrea_rd5_modbus: debug
```

**Common issues:**

- *Cannot connect* — verify the device IP, port (default 502), and that Modbus TCP is enabled on the unit
- *Entities unavailable* — check HA logs for Modbus errors; ensure the slave ID is correct (usually 1)
- *Stale/missing values* — increase the scan interval if the device reports protocol errors on rapid polling

## Disclaimer

This is an unofficial community integration. It is not sponsored by, affiliated with, or endorsed by ATREA s.r.o. in any way. Use it at your own risk.

## License

Apache 2.0 — see [LICENSE](LICENSE).
