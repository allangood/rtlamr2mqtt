# CHANGELOG

### 2026.4.22

- Added **listen mode** (`general.listen_mode: true`) to discover meter IDs without connecting to MQTT; logs each new meter once per session
- Fixed invalid `meters?:` schema syntax — HA Supervisor only supports `?` on scalar types. Default options now use `meters: []` and an empty meters list in non-listen mode returns a clear error

### 2026.4.21

- Periodic HA discovery re-publish to recover from simultaneous broker/HA restarts (configurable via `mqtt.discovery_interval`, default 300s)
- Fixed `sw_version` in HA device discovery payload to reflect actual add-on version
- Fixed `device_class: none` in add-on schema — field is now optional; omit it instead of using `none`
- Fixed `unit_of_measurement` capitalisation for energy meters (`KWh` → `kWh`)

### 2026.3.26

- Major rewrite of the codebase to improve maintainability and performance assisted by AI agent
- Using AsyncIO to deal with subprocess calls in a non-blocking way
- Using Async MQTT and Paho v2
