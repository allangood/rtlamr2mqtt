# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**rtlamr2mqtt** bridges RTL-SDR radio receivers to MQTT, enabling Home Assistant to read utility meters (electric, gas, water). It runs either as a **Home Assistant add-on** or a **standalone Docker container**. The v2026 rewrite replaced blocking subprocess calls with a fully async architecture.

All application code lives under `rtlamr2mqtt-addon/` — this is both the Docker build context and the HA add-on root.

## Commands

All commands run from `rtlamr2mqtt-addon/`:

```bash
# Set up dev environment
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

# Run all tests
.venv/bin/pytest

# Run a single test file
.venv/bin/pytest tests/test_process_manager.py -v

# Run a single test by name
.venv/bin/pytest tests/test_config.py -v -k "test_load_standalone"

# Lint
.venv/bin/pylint --rcfile=.pylint app/

# Build Docker image (standalone mode)
docker build -t rtlamr2mqtt .

# Integration test with mock RTL-SDR hardware
docker compose up --build
# In another terminal, subscribe to verify output:
docker exec rtlamr2mqtt-addon-mosquitto-1 mosquitto_sub -t 'rtlamr/#' -t 'homeassistant/#' -v
```

**pytest config:** `asyncio_mode = auto` — all async test functions run automatically without explicit markers.

## Architecture

### Dual-Mode Execution

The single codebase detects its runtime at startup via the `SUPERVISOR_TOKEN` environment variable:

- **HA add-on mode**: Config is read from `/data/options.json` (or `.yaml`). The MQTT broker is auto-discovered by calling `http://supervisor/services/mqtt` with the supervisor token. No MQTT credentials needed in config.
- **Standalone Docker mode**: Full config is read from `/etc/rtlamr2mqtt.yaml` (or a path passed as `sys.argv[1]`). All MQTT settings must be present in the config file.

Detection happens in [helpers/config.py](rtlamr2mqtt-addon/app/helpers/config.py) — `os.getenv("SUPERVISOR_TOKEN")` determines which path runs.

### Async Task Pipeline

```
asyncio.TaskGroup
├── MeterReader (reads rtlamr stdout → asyncio.Queue)
└── MQTTPublisher (drains queue → publishes to MQTT)
```

The two main classes communicate through a shared `asyncio.Queue(maxsize=100)` and a shared `asyncio.Event` (shutdown signal). They are both started as tasks in a `TaskGroup` in [rtlamr2mqtt.py](rtlamr2mqtt-addon/app/rtlamr2mqtt.py).

Signal handlers (`SIGTERM`, `SIGINT`) call `shutdown_event.set()`, which both tasks watch on every iteration.

### Process Lifecycle (ManagedProcess)

[process_manager.py](rtlamr2mqtt-addon/app/process_manager.py) wraps two external processes:

- **rtl_tcp** — talks to the RTL-SDR USB hardware
- **rtlamr** — decodes meter broadcasts from rtl_tcp's stream

Key behaviors:
- Prepends `stdbuf -oL` to force line-buffered stdout (avoids hangs waiting for output)
- `start_with_retry()` retries up to 5 times with `[2, 5, 10, 20, 30]` second backoff; calls an optional `on_retry` callback between attempts (used for USB reset)
- `stop()` sends SIGTERM to the **process group** (`start_new_session=True`), then SIGKILL after 2s
- If `rtltcp_host` points to a remote host (not `127.0.0.1`/`localhost`), rtl_tcp is not started locally and USB management is skipped

### Sleep/Wake Cycle

When `sleep_for > 0`, after all configured meters are seen, [meter_reader.py](rtlamr2mqtt-addon/app/meter_reader.py):
1. Stops rtlamr and rtl_tcp
2. Sleeps for `sleep_for` seconds (interruptible by shutdown)
3. Restarts rtl_tcp, then calls `tickle_rtl_tcp()` (sends frequency-change commands via raw TCP to wake up stuck receivers)
4. Restarts rtlamr
5. Begins reading again

### MQTT Publisher

[mqtt_publisher.py](rtlamr2mqtt-addon/app/mqtt_publisher.py) uses `aiomqtt` (async wrapper over paho-mqtt v2):
- Sets an LWT (Last Will and Testament) to publish `offline` on unexpected disconnect
- On connection: publishes all HA discovery payloads, subscribes to `homeassistant/status`
- When HA publishes `online` to that topic (HA restart), re-publishes all discovery payloads
- Inner `TaskGroup` runs `_listen_ha_status` and `_consume_readings` concurrently
- On `MqttError` or `ExceptionGroup` containing `MqttError`: reconnects with 5s backoff

### Configuration Shape

After loading, `config` is a dict with these top-level keys: `general`, `mqtt`, `meters`, `custom_parameters`. The `meters` value is a dict keyed by **string** meter ID. See [helpers/config.py](rtlamr2mqtt-addon/app/helpers/config.py) for all fields and defaults.

### rtlamr Output Parsing

[helpers/read_output.py](rtlamr2mqtt-addon/app/helpers/read_output.py) parses JSON lines from rtlamr. Different meter protocols use different field names:
- Meter ID: tries `EndpointID`, then `ERTSerialNumber`, then `ID`
- Consumption: tries `Consumption`, then `LastConsumptionCount`, then `LastConsumption`

### MQTT Topics

```
{base_topic}/status                          → "online" / "offline" (LWT)
{base_topic}/{meter_id}/state                → {"reading": "001234.567", "lastseen": "..."}
{base_topic}/{meter_id}/attributes           → protocol-specific raw fields
homeassistant/device/{meter_id}/config       → HA MQTT discovery payload
```

## Code Style

Pylint enforces these (see [.pylint](rtlamr2mqtt-addon/.pylint)):
- Max line length: 100 characters
- Logging uses `%`-style format strings (not f-strings) — `logger.warning('msg %s', var)` not `logger.warning(f'msg {var}')`
- No docstrings required (`missing-function-docstring` disabled)
- PascalCase for classes, snake_case everywhere else

## Testing Notes

- `conftest.py` provides `sample_config`, `sample_rtlamr_scm_line`, `sample_rtlamr_idm_line`, `sample_rtlamr_r900_line` fixtures
- The `mock/` directory contains shell scripts that simulate `rtlamr` and `rtl_tcp` for integration tests
- Integration tests use `docker-compose.yaml` with a real Mosquitto broker and the mock binaries

## Versioning

Uses date-based versioning (`YYYY.M.D`). Version is defined in [helpers/info.py](rtlamr2mqtt-addon/app/helpers/info.py) and mirrored in [config.yaml](rtlamr2mqtt-addon/config.yaml).
