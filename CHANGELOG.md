# CHANGELOG

### 2025.6.6

One of the main causes of problems has been addresses in this release: Non-blocking readings!

- fix: #319 Publish discover messages when Home Assiatant restarts
- fix: #318 Restart `rtl_tcp` and/or `rtl_amr` if their process die
- enhancement: Make `state_class = total_increasing` if not specified
- enhancement: Make readings non-blocking!

### 2025.6.5

- fix: Error when multiple arguments were used in custom_parameters
- fix: Version information (ouch!)
- fix: Error regarding missing_readings when sleep_for > 0 is used
- fix: Stop accepting wrong device_id numbers
- enhancement: Changed last_seen sensor to timestamp
- breaking change: The device_id parameter will fail if is not formatted in the 000:000 usb device id way

Special thanks to:
@nrdufour
@airdrummingfool

### 2025.6.4

- fix: Fix bug #288 rtlamr hanging forever during startup
- Thanks to @nrdufour

### 2025-06-03

- Fix: No MQTT messages from RTLAMR #288
- Fix: Dockerfile.mock now works out-of-the-box

### 2025-06-02

- Fixed `rtl_tcp` hanging forever
- Fixed logic to use remote `rtl_tcp`
- Added logic to get MQTT user and password from Mosquitto Add-On

### 2025-06-01 - First release

- This version is broken

### 2025-05-28 - Major changes!!!

**MAJOR REWRITE**
After a long break without working on this project
I am back with a major rewrite.
The old code was too hard to maintain
This is a completly new code.
You old entities should be cleaned manually from your MQTT broker

**Changes**

- I've tried to keep the configuration compatible with this new version
  but some of the parameters had to change and I had to add some others.
  Please check the tlamr2mqtt.yaml` file to see all the changes

### 2022-05-17

- Bug fixes for remote rtl_tcp and usb_reset logic #123
- Code changes to load config file and merge defaults
- Added vscode files to test the Addon development (finally!)

### 2022-04-12

- **REMOVED PARAMETER** usb_reset
- **ADDED PARAMETER** device_id
- **Changed Dockerfile**: Much smaller docker container
- Deprecated Anomaly detection (looks like no one is using it and it's not very reliable)

### 2022-04-12

- New `tls_enabled` parameter to avoid confusions
- Some fixes for the Add-On regarding the TLS configuration

### 2022-04-04

- New TLS parameters to MQTT connection
- New parameter: USB_RESET to address problem mentioned on #98

### 2022-02-11

- New configuration parameter: `state_class` (thanks to @JeffreyFalgout)
- Automatic MQTT configuration when using the Addon (thanks to @JeffreyFalgout)
- Fixed 255 characters limit for state value #86

### 2022-01-11

- Happy new year! :)
- Added "tickle_rtl_tcp" parameter to enable/disable the feature (explained below)
- Added date/time to the log output
- Added device_class configuration option #66 (thanks to @phidauex)
- Some clean up in the README file!
- Machine Learning to detect leaks still experimental and needs a lot of love to work properly

### 2021-12-01

- Lots of changes!
- Changed Docker container to use Debian Bullseye instead of Alpine
- Added TinyDB to store past readings
- Added Linear Regression to flag anomaly usage
- Problems with the official python docker base image :(

### 2021-10-27

- Many fixes regarding error handling
- More comments inside the code
- Some code cleanup
- Fix a bug for MQTT anonymous message publishing discovered by @jeffeb3
- Using latest code for both rtl-sdr and rtamr in the Dockerfile

### 2021-10-12

- The HA-ADDON is working now! A shout-out to @AnthonyPluth for his hard work!!! \o/
- New feature to allow this container to run with a remote rtl_tcp. Thanks to @jonbloom
- A bug was introduced by #28 and has been fixed.

### 2021-09-23:

- New images are based on Alpine 3.14 **_ IMPORTANT _**
  - If this container stops to work after you upgrade, please read this: [https://docs.linuxserver.io/faq](https://docs.linuxserver.io/faq)
- We are working in a new image: HA-ADDON! Thanks to @AnthonyPluth ! Stay tuned for news about it!

### 2021-09-13:

- A new configuration parameter has been added: _verbosity_
- Environment variable _DEBUG_ has been renamed to _LISTEN_ONLY_ to prevent confusion
- Better error handling and output (still work in progress)

### 2021-09-09

- Added last Will and testment messages
- Added availability status topic
- Added RTL_MSGTYPE to debug mode

### 2021-09-03

- Added DEBUG Mode
