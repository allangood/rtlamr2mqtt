# Home Assistant Add-on: RTLAMR2MQTT

## Updates:

**2025.6.6**

One of the main causes of problems has been addresses in this release: Non-blocking readings!

- fix: #319 Publish discover messages when Home Assiatant restarts
- fix: #318 Restart `rtl_tcp` and/or `rtl_amr` if their process die
- enhancement: Make `state_class = total_increasing` if not specified
- enhancement: Make readings non-blocking!

**2025.6.5**

- fix: Error when multiple arguments were used in custom_parameters
- fix: Version information (ouch!)
- fix: Error regarding missing_readings when sleep_for > 0 is used
- fix: Stop accepting wrong device_id numbers
- enhancement: Changed last_seen sensor to timestamp
- breaking change: The device_id parameter will fail if is not formatted in the 000:000 usb device id way

Special thanks to:
@nrdufour
@airdrummingfool

**2025.6.4**

- fix: Fix bug #288 rtlamr hanging forever during startup
- Thanks to @nrdufour

**2025.6.3**

- fix: No MQTT messages from RTLAMR #288
- fix: Added logic to ignore usb scan when rtl_tcp is defined as remote
- chore: Dockerfile.mock now works out-of-the-box

**2025.6.2**

- Fixed `rtl_tcp` hanging forever
- Fixed logic to use remote `rtl_tcp`
- Added logic to get MQTT user and password from Mosquitto Add-On

**2025.6.1**

- Complete rewrite of the code
- The update has completely broken the add-on (sorry)

## How to use

The add-on has a couple of options available. To get the add-on running:

1. Start the add-on.
2. Have some patience and wait a couple of minutes.
3. Check the add-on log output to see the result.

## Configuration

> [[!WARNING]]
> The "old" version and the new setting for `device_id` are incompatible! Please read the configuraion below.

Add-on configuration:

```yaml
general:
  # Sleep for this amount of seconds before each reading
  # If this value is 0, it means we will never stop reading
  sleep_for: 0
  # Verbose output. It can be: debug, info, warning, error, none
  verbosity: debug
  # if you have multiple RTL devices, set the device id to use with this instance.
  # Get the ID running the lsusb command. If not specified, the first device will be used.
  # Example:
  # device_id: '001:010'
  # RTL_TCP host and port to connect. Default, use the internal server
  # If you want to use a remote rtl_tcp server, set the host and port here
  # rtltcp_host: "172.17.0.4:1234"

mqtt:
  # Broker host. This is optional.
  # If not specified, it will query supervisor
  ###host: localhost
  # Broker port. This is optional.
  # If not specified, it will query supervisor
  ###port: 1883
  # Username. This is optional.
  # If not specified, it will query supervisor
  ###user: test
  # Password. This is optional.
  # If not specified, it will query supervisor
  ###password: testpassword
  # Use TLS with MQTT?
  tls_enabled: false
  # TLS insecure. Must be true for self-signed certificates. Defaults to False
  tls_insecure: true
  # Path to CA certificate to use. Mandatory if tls_enabled = true
  tls_ca: "/etc/ssl/certs/ca-certificates.crt"
  # Path to certificate file to use. Optional
  tls_cert: "/etc/ssl/my_self_signed_cert.crt"
  # Certificate key file to use. Optional
  tls_keyfile: "/etc/ssl/my_self_signed_cert_key.key"
  # Which topic for the auto discover to use?
  ha_autodiscovery_topic: homeassistant
  # Home Assistant status topic
  ha_status_topic: homeassistant/status
  # Base topic to send status and state information
  # i.e.: status = <base_topic>/status
  base_topic: "rtlamr"

# Optional section
# If you need to pass parameters to rtl_tcp or rtlamr
# custom_parameters:
#   rtltcp: "-s 2048000 -f 912600155"
#   rtlamr: ""

# Mandatory section: Meters definition
# You can define multiple meters
# Check here for more info:
# https://www.home-assistant.io/integrations/sensor.mqtt
meters:
  # Meter ID
  - id: 33333333
    # Protocol: scm, scm+, idm, netidm, r900 and r900bcd
    protocol: scm+
    # A nice name to show on HA
    name: my_water_meter
    # How to format the number of your meter. Each '#' is a digit
    format: "######.###"
    # Unit of measurement to show on HA
    unit_of_measurement: "m³"
    # Icon to show on HA
    icon: mdi:gauge
    # device_class on HA
    device_class: water
    # HA state_class. It can be measurement|total|total_increasing
    # state_class: total_increasing
    # If set, it defines the number of seconds after the sensor’s state expires,
    # if it’s not updated. After expiry, the sensor’s state becomes unavailable.
    # expire_after: 0
    # Sends update events even if the value hasn’t changed.
    # Useful if you want to have meaningful value graphs in history.
    # force_update: true
  - id: 22222222
    # Protocol: scm, scm+, idm, netidm, r900 and r900bcd
    protocol: r900
    # A nice name to show on HA
    name: my_energy_meter
    # How to format the number of your meter. Each '#' is a digit
    format: "######.###"
    # Unit of measurement to show on HA
    unit_of_measurement: "KWh"
    # Icon to show on HA
    icon: mdi:gauge
    # device_class on HA
    device_class: energy
```

## Support

Got questions?

- Repository: https://github.com/allangood/rtlamr2mqtt
- Report issues here: https://github.com/allangood/rtlamr2mqtt/issues
- Questions: https://github.com/allangood/rtlamr2mqtt/discussions
