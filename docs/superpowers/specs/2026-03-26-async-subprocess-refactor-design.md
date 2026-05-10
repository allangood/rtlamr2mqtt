# Async Subprocess Refactor — Design Spec

## Problem

The current subprocess management uses blocking `subprocess.Popen` with a non-blocking fd hack (`os.set_blocking(fd, False)`) and a `sleep(1)` polling loop. This causes the application to hang intermittently — a recurring issue evidenced by commits `b6114db`, `0184c09`, `6e8f9d4`. The main loop mixes process lifecycle, MQTT publishing, parsing, and health monitoring in a single function, making it hard to reason about and test.

## Goals

1. Eliminate subprocess blocking/hanging by switching to `asyncio` subprocess management.
2. Clean separation of concerns: process lifecycle, meter reading, MQTT publishing as independent async tasks.
3. Reliable process lifecycle: start with ready detection, retry with backoff, clean shutdown.
4. Fix all known bugs from the current codebase.
5. Add tests.
6. Optimize for resource-constrained environments (Raspberry Pi).

## Decisions Made

- **Full rewrite** with new file structure and clean module boundaries.
- **asyncio** for all I/O (subprocesses, MQTT, sleep/wake).
- **aiomqtt** replaces direct paho-mqtt usage for native async MQTT.
- **stdbuf -oL** replaces `unbuffer` (from `expect` package). Lighter, already available.
- **device_id** changes from `bus:address` format (`"001:010"`) to integer index (`0`, `1`, `2`). Stable across reboots and VMs.
- **sleep_for mode** preserved: collect all meters, stop processes, sleep, restart. MQTT stays connected during sleep.
- **Retry with backoff then exit** on repeated process start failures (5 retries, 2/5/10/20/30s backoff).
- **pytest + pytest-asyncio** for testing.

## File Structure

```
app/
├── rtlamr2mqtt.py           — entry point: asyncio.run(main()), signal handling, orchestration
├── process_manager.py       — ManagedProcess class: start/stop/restart/retry for any subprocess
├── meter_reader.py          — async rtlamr output reader: reads lines, parses, puts on queue
├── mqtt_publisher.py        — async MQTT client wrapper using aiomqtt
├── helpers/
│   ├── __init__.py
│   ├── config.py            — config loading (cleaned up)
│   ├── ha_messages.py       — HA discovery payload builder (pure function)
│   ├── read_output.py       — rtlamr JSON parsing (pure functions)
│   ├── usb_utils.py         — USB device detection by index, reset, tickle
│   ├── buildcmd.py          — CLI arg construction for rtl_tcp and rtlamr
│   ├── info.py              — version string
│   └── sdl_ids.txt          — RTL-SDR device ID list
tests/
├── conftest.py              — shared fixtures (sample configs, mock processes)
├── test_config.py           — config loading, defaults, validation
├── test_read_output.py      — rtlamr JSON parsing, format_number, edge cases
├── test_ha_messages.py      — discovery payload structure
├── test_buildcmd.py         — CLI arg construction
├── test_process_manager.py  — ManagedProcess with mock subprocesses
├── test_meter_reader.py     — reading loop, sleep/wake cycle, queue behavior
├── test_mqtt_publisher.py   — publish flow, reconnection, discovery re-publish
└── test_usb_utils.py        — device index lookup, reset
```

## ManagedProcess Class

Generic async subprocess wrapper. Not rtlamr-specific.

```python
class ManagedProcess:
    def __init__(
        self,
        name: str,              # "rtl_tcp" or "rtlamr"
        command: list[str],     # full command with args
        ready_pattern: str,     # stdout string indicating readiness
        ready_timeout: float,   # seconds to wait for ready pattern
        max_retries: int = 5,
        backoff: list[float] = [2, 5, 10, 20, 30],
    )

    async def start(self) -> bool
    async def stop(self)
    async def restart(self) -> bool
    async def start_with_retry(self) -> bool
    async def read_line(self) -> str | None
    async def wait_for_exit(self)
    @property
    def is_alive(self) -> bool
```

- `start()` uses `asyncio.create_subprocess_exec` and `asyncio.wait_for()` on ready detection. Cannot hang.
- `stop()` sends SIGTERM, waits 2s, escalates to SIGKILL.
- `start_with_retry()` retries with backoff [2, 5, 10, 20, 30]s. Returns False if all exhausted.
- `read_line()` wraps `proc.stdout.readline()` — fully async, no `os.set_blocking` hack.
- Commands wrapped with `stdbuf -oL` for line-buffered output.

## Async Task Architecture

Three concerns as independent async tasks communicating via `asyncio.Queue`:

```
┌─────────────┐     stdout      ┌───────────────┐    Queue     ┌──────────────────┐
│  rtl_tcp     │◄──managed by───│               │              │                  │
│  (process)   │                │  meter_reader  │──readings──►│  mqtt_publisher   │
│              │                │    (task)      │              │     (task)        │
└─────────────┘                └───────────────┘              └──────────────────┘
                                      │                              │
┌─────────────┐     stdout            │                              │
│  rtlamr      │◄──reads from─────────┘                              │
│  (process)   │                                                     │
└─────────────┘                                              ┌──────────────────┐
                                                             │   MQTT broker    │
                                                             └──────────────────┘
```

### meter_reader task

- Owns the rtlamr ManagedProcess.
- Reads lines via `await rtlamr.read_line()`.
- Parses JSON, matches meter IDs (using `read_output.py` helpers).
- Puts valid readings on the queue as dicts.
- Detects rtlamr death, triggers restart via `start_with_retry()`.
- When `sleep_for > 0` and all meters seen: stops rtlamr, signals rtl_tcp stop, sleeps (cancellable), restarts both.

### mqtt_publisher task

- Owns the aiomqtt connection.
- On connect: publishes HA discovery for all meters, publishes "online" status.
- Consumes readings from queue via `await queue.get()`.
- Publishes state + attributes per reading.
- Subscribes to HA status topic; re-publishes discovery on HA restart.
- Reconnects with backoff on disconnect.

### Orchestration (main)

```python
async def main():
    config = load_config()
    shutdown_event = asyncio.Event()
    reading_queue = asyncio.Queue(maxsize=100)

    # USB setup (sync, before async loop)
    setup_usb(config)

    # Create managed processes
    rtltcp = ManagedProcess("rtl_tcp", ..., ready_pattern="listening...")
    rtlamr = ManagedProcess("rtlamr", ..., ready_pattern="GainCount:")

    # Signal handlers
    loop = asyncio.get_event_loop()
    for sig in (SIGTERM, SIGINT):
        loop.add_signal_handler(sig, shutdown_event.set)

    # Start rtl_tcp (if local)
    if not is_remote:
        await rtltcp.start_with_retry()

    # Run tasks
    async with asyncio.TaskGroup() as tg:
        tg.create_task(meter_reader(rtlamr, rtltcp, config, reading_queue, shutdown_event))
        tg.create_task(mqtt_publisher(config, reading_queue, shutdown_event))

    # Cleanup
    await rtlamr.stop()
    await rtltcp.stop()
```

- `shutdown_event` for cooperative cancellation. No signal-to-exception pattern.
- `TaskGroup` ensures if one task crashes, the other is cancelled.
- Reading queue bounded at 100. If MQTT is down and queue fills, oldest readings dropped with warning.

## Sleep/Wake Cycle

When `sleep_for > 0`:

1. **Reading phase:** Start rtl_tcp + rtlamr, read until all meter IDs collected.
2. **Sleep phase:** Stop rtlamr, stop rtl_tcp, `asyncio.sleep(sleep_for)` — cancellable via `shutdown_event`.
3. **Wake:** Back to reading phase with fresh processes.

MQTT stays connected during sleep (LWT active, HA status listener active). Sleep cancellation uses:
```python
await asyncio.wait(
    [asyncio.create_task(asyncio.sleep(sleep_for)),
     asyncio.create_task(shutdown_event.wait())],
    return_when=asyncio.FIRST_COMPLETED
)
```

## MQTT Publisher Details

- Uses `aiomqtt.Client` context manager for connection lifecycle.
- LWT configured via `aiomqtt.Will` in constructor.
- TLS via `ssl.create_default_context()` — no hardcoded protocol version.
- Reconnection pattern:
  ```python
  while not shutdown_event.is_set():
      try:
          async with aiomqtt.Client(...) as client:
              await self._run_connected(client)
      except aiomqtt.MqttError:
          await asyncio.sleep(5)
  ```
- HA status listener: subscribes to `homeassistant/status`, re-publishes discovery on "online" message. No longer gated behind log level.

## Error Handling

| Layer | Behavior |
|---|---|
| ManagedProcess | Logs failures, retries with backoff, returns False if exhausted. Never raises. |
| meter_reader | If rtlamr can't start after retries, sets shutdown_event. |
| mqtt_publisher | Reconnects with backoff. Readings queue up (bounded). |
| main() | TaskGroup catches crashes, ensures cleanup. |
| Config loading | Fail fast on bad config. |

## Logging

Replace numeric `LOG_LEVEL` global with standard Python logging:

```python
VERBOSITY_MAP = {
    'none': logging.CRITICAL + 1,
    'error': logging.ERROR,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'debug': logging.DEBUG,
}
logger = logging.getLogger('rtlamr2mqtt')
logger.setLevel(VERBOSITY_MAP[config['general']['verbosity']])
```

No more `if LOG_LEVEL >= 3:` checks. Use `logger.info()`, `logger.debug()`, etc.

## Config Changes

### device_id format (breaking)

```yaml
# Before
general:
  device_id: "001:010"

# After
general:
  device_id: 0
```

Schema: `match(^[0-9]{3}:[0-9]{3})` → `int`. Default `0`.

### Dependencies

```
aiomqtt>=2.0.0
paho-mqtt>=2.1.0
pyyaml==6.0.2
requests==2.32.4
pyusb==1.3.1
```

Dev: `pytest`, `pytest-asyncio`.

### Dockerfile

- Remove `expect` package.
- `stdbuf` already in base image via `coreutils`.

### No changes to

- MQTT topic structure.
- HA discovery topic structure.
- Payload formats.
- Config format for mqtt, meters, custom_parameters sections.

## Bugs Fixed

1. Indentation/logic error at rtlamr2mqtt.py:345-347 (rtltcp None check) — eliminated by ManagedProcess design.
2. Dead expression in ha_messages.py:15.
3. Undefined `sdl_devices` in buildcmd.py mock mode.
4. Non-deterministic set ordering in read_output.py:53 — use ordered list lookup.
5. Deprecated paho-mqtt v1 API — replaced by aiomqtt.
6. Hardcoded TLS 1.2 — use ssl.create_default_context().
7. HA discovery re-publish gated behind LOG_LEVEL >= 3.
8. read_counter as list instead of set.
9. USB fd leak in reset_usb_device (no context manager).
