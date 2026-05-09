# CHANGELOG

### 2026.5.9

- Fixed listen mode to actually listen for **all** protocols. rtlamr defaults to `scm` only when `-msgtype` is omitted, so listen mode was silently missing scm+, idm, netidm, r900, and r900bcd meters. Now passes `-msgtype=all` when no meters are configured

### 2026.5.3

- Added a 2-second delay between receiving `homeassistant/status = online` and re-publishing discovery payloads. HA fires `online` slightly before its discovery handler is fully ready, causing payloads to be silently dropped and entities to stay `unavailable` after a restart
- Periodic discovery re-publish now also publishes the `online` status afterwards, matching the connect and HA-restart paths

### 2026.5.1

- Added stuck-process diagnostics to `ManagedProcess`: rolling 20-line stdout buffer, `exit_code` and `recent_output` properties, and a dump of recent output on startup timeout, early exit during ready-wait, and runtime exit — failure logs now include what the process actually printed instead of a bare timeout message (failure modes proposed by [@crash0verride11](https://github.com/crash0verride11/rtlamr2mqtt/commit/f29ecc108971cf589b50c7454a933b98b5841a52))
- Capped the post-SIGKILL `wait()` at 5 seconds to prevent an indefinite hang when a process is stuck in kernel D-state on USB I/O (Synology-class issue) (proposed by [@crash0verride11](https://github.com/crash0verride11/rtlamr2mqtt/commit/f29ecc108971cf589b50c7454a933b98b5841a52))
- Made `tickle_rtl_tcp` async — replaces blocking `socket` + `time.sleep` calls with `asyncio.open_connection`, so the MQTT publisher and shutdown handler no longer stall during a tickle. Writer is closed in a `finally` so partial-write failures don't leak file descriptors (proposed by [@crash0verride11](https://github.com/crash0verride11/rtlamr2mqtt/commit/f29ecc108971cf589b50c7454a933b98b5841a52))
- When rtlamr exits, restart rtl_tcp first if it also died — closes a gap where rtlamr's restart attempts would all hit `connection refused` after a shared USB error took both processes down together (proposed by [@crash0verride11](https://github.com/crash0verride11/rtlamr2mqtt/commit/f29ecc108971cf589b50c7454a933b98b5841a52))
- Fixed rtlamr readiness check broken by upstream v0.9.5 slog migration — `ready_pattern` changed from `GainCount:` to `GainCount` to match both old (`GainCount: 29`) and new (`GainCount=29`) log formats, eliminating the 30s timeout-and-kill on every start (#404 by Adam Light)
- Pinned rtlamr to v0.9.5 in the Dockerfile (was `@latest`) to prevent future breakage from upstream changes (#404 by Adam Light)
- Updated mock `rtlamr` script and process-manager tests to match the slog output format (#404 by Adam Light)
- Added a water-leak-detection automation example to the README (utility_meter + derivative sensor for overnight and sustained-flow patterns) (#403 by @allangood)

### 2026.4.22

- Added **listen mode** (`general.listen_mode: true`) to discover meter IDs without connecting to MQTT; logs each new meter once per session (#399 by @allangood)
- Fixed invalid `meters?:` schema syntax — HA Supervisor only supports `?` on scalar types. Default options now use `meters: []` and an empty meters list in non-listen mode returns a clear error (#402 by @allangood)

### 2026.4.21

- Periodic HA discovery re-publish to recover from simultaneous broker/HA restarts (configurable via `mqtt.discovery_interval`, default 300s) (#397 by @allangood)
- Fixed `sw_version` in HA device discovery payload to reflect actual add-on version (#397 by @allangood)
- Fixed `device_class: none` in add-on schema — field is now optional; omit it instead of using `none` (#397 by @allangood)
- Fixed `unit_of_measurement` capitalisation for energy meters (`KWh` → `kWh`) (#397 by @allangood)
- Fixed publisher reconnect loop to handle `MqttError` wrapped in an `ExceptionGroup` by the inner `TaskGroup` — previously, an MQTT broker restart (e.g. Mosquitto upgrade) would crash the add-on instead of triggering a reconnect (#396 by @trionnis)

### 2026.3.26

- Major rewrite of the codebase to improve maintainability and performance assisted by AI agent (by @allangood)
- Using AsyncIO to deal with subprocess calls in a non-blocking way (by @allangood)
- Using Async MQTT and Paho v2 (by @allangood)
