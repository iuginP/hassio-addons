# Onzo Smart Energy Meter app

This app discovers all attached Onzo USB energy meters with the configured USB vendor and product IDs. Each clamp is identified by its own serial number and appears as a separate device in Home Assistant through MQTT Discovery.

## Prerequisites

- Install the official Mosquitto Broker app and configure Home Assistant's MQTT integration.
- Attach one or more Onzo displays to the Home Assistant host by USB.

No MQTT credentials are required in this app. Supervisor supplies short-lived broker credentials automatically.

## Configuration

The default USB IDs are `04d8:003f`. The app continuously scans for matching HID devices, so meters can reconnect without restarting the app.

The optional `meters` list assigns friendly names to known clamp serials:

```yaml
meters:
  - serial: "0x12345678"
    name: House
  - serial: "87654321"
    name: Workshop
```

If a serial is not listed, the device is still discovered with a generated name such as `Onzo 12345678`. Clamp serials and HID paths are written to the app log when discovered.

## Entities

Each meter exposes real, reactive, and apparent power; cumulative energy; clamp battery voltage and temperature; and mains voltage. Discovery and state messages are retained, while availability changes when a meter connects or disconnects.
