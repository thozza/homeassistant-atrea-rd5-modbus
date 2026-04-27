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
