# RTLAMR2MQTT

> **AI Disclosure:** This version of rtlamr2mqtt was developed with the assistance of AI (Claude by Anthropic). The architecture, code, tests, and documentation were produced collaboratively between a human developer and an AI assistant. The code has been reviewed, tested, and validated by the maintainer.

![Docker Pulls](https://img.shields.io/docker/pulls/allangood/rtlamr2mqtt)
[![GitHub license](https://img.shields.io/github/license/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/stargazers)
![GitHub contributors](https://img.shields.io/github/contributors/allangood/rtlamr2mqtt)
[![GitHub issues](https://img.shields.io/github/issues/allangood/rtlamr2mqtt)](https://github.com/allangood/rtlamr2mqtt/issues)

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt)

### Supported Platforms

[![AMD64](https://img.shields.io/badge/AMD64-Yes-green)](https://img.shields.io/badge/AMD64-Yes-green)
[![AARCH64](https://img.shields.io/badge/AARCH64-Yes-green)](https://img.shields.io/badge/AARCH64-Yes-green)

---

RTLAMR2MQTT reads utility meters (water, gas, energy) using an inexpensive USB RTL-SDR device and publishes the readings to an MQTT broker. It integrates with Home Assistant through MQTT auto-discovery, automatically creating sensor entities for each configured meter.

It works by running [rtl_tcp](https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr) to interface with the SDR hardware and [rtlamr](https://github.com/bemasher/rtlamr) to decode the meter transmissions. Readings are parsed and forwarded to MQTT in real time.

## What's New in This Version

> [!CAUTION]
> **Major code rewrite** \
> This version is a complete rewrite of the application internals. \
> Your old entities should be cleaned manually from your MQTT broker.

### Changes from the previous version

- **Async subprocess management** -- Replaced blocking `subprocess.Popen` with `asyncio.create_subprocess_exec`. The application no longer hangs when rtl_tcp or rtlamr stall, which was a recurring issue on resource-constrained devices like Raspberry Pi.
- **Separated architecture** -- The monolithic main loop has been split into independent async tasks: `MeterReader` (reads and parses rtlamr output), `MQTTPublisher` (handles all MQTT communication), and `ManagedProcess` (generic subprocess lifecycle manager). They communicate through an `asyncio.Queue`.
- **Native async MQTT** -- Switched from paho-mqtt with threading to [aiomqtt](https://github.com/empicano/aiomqtt) for native asyncio MQTT support. Includes automatic reconnection with backoff.
- **Process retry with backoff** -- When rtl_tcp or rtlamr fail to start, the application retries up to 5 times with increasing delays (2, 5, 10, 20, 30 seconds) before giving up. This handles transient USB issues common on Raspberry Pi.
- **Stable device identification** -- `device_id` now uses an integer index (0, 1, 2...) matching the order devices are found by librtlsdr, instead of the old `bus:address` format which changed across reboots and in VMs.
- **Standard Python logging** -- Replaced the custom numeric log level system with Python's built-in `logging` module. No more `if LOG_LEVEL >= 3:` checks scattered throughout the code.
- **Replaced `unbuffer` with `stdbuf`** -- Removed the dependency on the `expect` package. Line-buffered subprocess output now uses `stdbuf -oL` from coreutils.
- **HA discovery re-publish** -- When Home Assistant restarts, discovery messages are automatically re-published. This was previously broken (gated behind a log level check).
- **Listen mode** -- New `general.listen_mode: true` option. Runs without any meter filter and logs every meter it hears, deduplicated per session. No MQTT connection is made. Useful for discovering your meter ID before configuring the add-on.
- **Periodic HA discovery re-publish** -- Discovery payloads are re-sent on a configurable interval (`mqtt.discovery_interval`, default 300 s) in addition to on HA restart, so entities survive MQTT broker restarts even with `retain=false`.
- **Test coverage** -- Added 90 unit tests using pytest and pytest-asyncio.
- **Dual-purpose Dockerfile** -- Works both as a Home Assistant add-on (with `BUILD_FROM`) and as a standalone Docker container (defaults to `python:3.13-slim`).
- **Bug fixes** -- Fixed: non-deterministic meter ID key lookup, undefined variable in mock mode, deprecated paho-mqtt API usage, USB file descriptor leak in reset, hardcoded TLS 1.2 protocol.

## Requirements

1. **A compatible smart meter** -- Check the [list of supported meters](https://github.com/bemasher/rtlamr/blob/master/meters.csv)
2. **A USB RTL-SDR device** -- For example: [NooElec NESDR Mini USB](https://www.amazon.ca/NooElec-NESDR-Mini-Compatible-Packages/dp/B009U7WZCA)
3. **An MQTT broker** -- Such as [Mosquitto](https://mosquitto.org/)
4. **[Home Assistant](https://www.home-assistant.io/)** (optional but recommended)

## Installation

### Home Assistant Add-On

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt)

[![Open your Home Assistant instance and show the dashboard of a Supervisor add-on.](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?repository_url=https%3A%2F%2Fgithub.com%2Fallangood%2Frtlamr2mqtt&addon=6713e36e_rtlamr2mqtt)

Or manually:

1. Go to **Settings > Add-ons > Add-on Store**
2. Click the three dots in the top-right corner, then **Repositories**
3. Add `https://github.com/allangood/rtlamr2mqtt` and click **Add**
4. The **rtlamr2mqtt** add-on will appear in the store. Click to install and configure.

When running as an add-on, MQTT broker settings are automatically obtained from the Home Assistant Supervisor API. You only need to configure the `meters` section.

### Docker (Standalone)

```bash
docker run --name rtlamr2mqtt \
  -v /path/to/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml:ro \
  --device /dev/bus/usb:/dev/bus/usb \
  --restart unless-stopped \
  allangood/rtlamr2mqtt
```

### Docker Compose (Standalone)

```yaml
services:
  rtlamr2mqtt:
    image: allangood/rtlamr2mqtt
    container_name: rtlamr2mqtt
    restart: unless-stopped
    devices:
      - /dev/bus/usb:/dev/bus/usb
    volumes:
      - /path/to/rtlamr2mqtt.yaml:/etc/rtlamr2mqtt.yaml:ro
```

## Finding Your Meter ID (Listen Mode)

If you don't know your meter ID, use **listen mode** to discover it. In this mode rtlamr2mqtt runs without any meter filter, logs every meter it receives, and makes no MQTT connection.

### Home Assistant Add-On

In the add-on configuration, set:

```yaml
general:
  listen_mode: true
```

Leave the `meters` list empty (or remove it entirely). Start the add-on and open the **Log** tab. You will see a warning followed by one log line per discovered meter:

```
WARNING: LISTEN MODE ACTIVE — no meter filtering, no MQTT publishing. Check logs for "New meter" lines to discover your meter ID, then configure it and disable listen_mode.

INFO: New meter | ID: 12345678 | Type: SCM  | Consumption: 1978226
INFO: New meter | ID: 87654321 | Type: R900 | Consumption: 4555831
```

Each meter is logged **once per session** regardless of how many times it broadcasts. Note the **ID** and **Type** for the meter you want to track, then configure it normally and set `listen_mode: false`.

### Docker / Standalone

Create a minimal config file:

```yaml
general:
  listen_mode: true
  verbosity: info

mqtt:
  host: 127.0.0.1   # still required for standalone, but no connection is made
```

Run the container and watch the logs:

```bash
docker run --rm \
  -v /path/to/listen.yaml:/etc/rtlamr2mqtt.yaml:ro \
  --device /dev/bus/usb:/dev/bus/usb \
  allangood/rtlamr2mqtt
```

Once you have found your meter ID, update your config with the full meter definition and set `listen_mode: false` (or remove the line — `false` is the default).

---

## Configuration

When running standalone (not as an HA add-on), create a `rtlamr2mqtt.yaml` file. Below is a complete example with all available options:

```yaml
general:
  # Seconds to sleep after all meters are read. 0 = continuous reading.
  sleep_for: 60
  # Log verbosity: debug, info, warning, error, critical, none
  verbosity: info
  # RTL-SDR device index (0 = first device). Use if you have multiple SDR dongles.
  # device_id: 0
  # RTL_TCP server address. Default: local server at 127.0.0.1:1234
  # Set to a remote address to use an external rtl_tcp instance.
  # rtltcp_host: "192.168.1.100:1234"
  # Enable to log all received meters without MQTT. Useful for finding your meter ID.
  # listen_mode: false

mqtt:
  # MQTT broker connection (not needed when running as HA add-on)
  host: 127.0.0.1
  port: 1883
  # user: myuser
  # password: mypassword
  # TLS settings
  tls_enabled: false
  # tls_insecure: false
  # tls_ca: "/path/to/ca.crt"
  # tls_cert: "/path/to/client.crt"
  # tls_keyfile: "/path/to/client.key"
  # MQTT topics
  ha_autodiscovery_topic: homeassistant
  ha_status_topic: homeassistant/status
  base_topic: rtlamr
  # How often (seconds) to re-publish HA discovery payloads. Keeps entities alive after broker restarts.
  # discovery_interval: 300

# Optional: pass extra arguments to rtl_tcp or rtlamr
# custom_parameters:
#   rtltcp: "-s 2048000"
#   rtlamr: "-unique=true"

# Meter definitions (required)
meters:
  - id: 12345678
    protocol: scm+          # scm, scm+, idm, netidm, r900, r900bcd
    name: my_water_meter
    format: "######.###"     # Each '#' is a digit
    unit_of_measurement: "m3"
    icon: mdi:water
    device_class: water      # water, gas, energy, power, current, none
    state_class: total_increasing  # measurement, total, total_increasing
    # expire_after: 3600     # Seconds before sensor becomes unavailable
    # force_update: true     # Send updates even if value unchanged
    # manufacturer: "Badger Meter"  # Shown in HA device info
    # model: "ORION SE"             # Shown in HA device info
```

### Configuration Reference

#### general

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sleep_for` | int | `0` | Seconds to sleep after all meters are read. `0` = continuous. |
| `verbosity` | string | `info` | Log level: `debug`, `info`, `warning`, `error`, `critical`, `none` |
| `device_id` | int | `0` | RTL-SDR device index. `0` = first device found. |
| `rtltcp_host` | string | `127.0.0.1:1234` | RTL_TCP server address. Set to remote host to skip local rtl_tcp. |
| `listen_mode` | bool | `false` | Log all received meters without filtering. No MQTT connection. See [Finding Your Meter ID](#finding-your-meter-id-listen-mode). |

#### mqtt

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | string | *(from Supervisor)* | MQTT broker hostname. Auto-detected in HA add-on mode. |
| `port` | int | `1883` | MQTT broker port. |
| `user` | string | *none* | MQTT username. |
| `password` | string | *none* | MQTT password. |
| `tls_enabled` | bool | `false` | Enable TLS for MQTT connection. |
| `tls_insecure` | bool | `false` | Skip TLS certificate verification (for self-signed certs). |
| `tls_ca` | string | *none* | Path to CA certificate file. |
| `tls_cert` | string | *none* | Path to client certificate file. |
| `tls_keyfile` | string | *none* | Path to client key file. |
| `ha_autodiscovery_topic` | string | `homeassistant` | HA MQTT auto-discovery prefix. |
| `ha_status_topic` | string | `homeassistant/status` | Topic to monitor HA restarts. |
| `base_topic` | string | `rtlamr` | Base topic for status and readings. |
| `discovery_interval` | int | `300` | Seconds between periodic HA discovery re-publishes. |

#### meters[]

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | int | yes | Meter ID number. |
| `protocol` | string | yes | Protocol: `scm`, `scm+`, `idm`, `netidm`, `r900`, `r900bcd` |
| `name` | string | yes | Sensor name in Home Assistant. |
| `format` | string | no | Number format. Each `#` is a digit (e.g., `######.###`). |
| `unit_of_measurement` | string | no | Unit shown in HA (e.g., `m3`, `ft3`, `KWh`). |
| `icon` | string | no | MDI icon (e.g., `mdi:water`, `mdi:gauge`). |
| `device_class` | string | no | HA device class: `water`, `gas`, `energy`, `power`, `current`, `none` |
| `state_class` | string | no | HA state class: `measurement`, `total`, `total_increasing` (default). |
| `expire_after` | int | no | Seconds before sensor becomes unavailable if not updated. |
| `force_update` | bool | no | Send update events even if value hasn't changed. |
| `manufacturer` | string | no | Manufacturer name shown in HA device info. |
| `model` | string | no | Model name shown in HA device info. |

### MQTT Topics

For each configured meter, the following topics are published:

| Topic | Description |
|-------|-------------|
| `rtlamr/status` | `online` / `offline` (LWT) |
| `rtlamr/{meter_id}/state` | JSON: `{"reading": "001234.567", "lastseen": "2025-01-15T10:30:00-05:00"}` |
| `rtlamr/{meter_id}/attributes` | JSON with protocol-specific fields |
| `homeassistant/device/{meter_id}/config` | HA auto-discovery payload |

### Multiple RTL-SDR Devices

If you have more than one RTL-SDR dongle, set `device_id` to the index of the one you want to use. The index corresponds to the order devices are detected by librtlsdr (starting from 0).

### Home Assistant Utility Meter

To track usage over time, add a [utility meter](https://www.home-assistant.io/integrations/utility_meter/) in your Home Assistant configuration:

```yaml
utility_meter:
  daily_water:
    source: sensor.my_water_meter_reading
    cycle: daily
  monthly_water:
    source: sensor.my_water_meter_reading
    cycle: monthly
```

## Development

### Running Tests

```bash
cd rtlamr2mqtt-addon
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest tests/ -v
```

### Testing with Docker Compose

A docker-compose setup with Mosquitto is included for integration testing using mock rtl_tcp/rtlamr scripts:

```bash
cd rtlamr2mqtt-addon
docker compose up --build
```

This starts Mosquitto and rtlamr2mqtt with mock data. You can subscribe to see the messages:

```bash
docker exec rtlamr2mqtt-addon-mosquitto-1 mosquitto_sub -t 'rtlamr/#' -t 'homeassistant/#' -v
```

## Credits

- [rtlamr](https://github.com/bemasher/rtlamr) by bemasher
- [rtl-sdr](https://osmocom.org/projects/rtl-sdr/wiki/Rtl-sdr) by Osmocom
- [aiomqtt](https://github.com/empicano/aiomqtt) by Frederik Aalund
- Icon by [Plastic Donut - Flaticon](https://www.flaticon.com/free-icons/sound)

Thank you to all [contributors](https://github.com/allangood/rtlamr2mqtt/graphs/contributors)!

## License

See [LICENSE](LICENSE).
