# WeeWX app

This add-on runs WeeWX inside Home Assistant OS.

## Notes

- The Configuration tab controls the WeeWX driver, unit system, location, coordinates, and altitude. Restart the app after saving changes.
- Station data and generated reports persist in the app's private `/data/weewx` directory.
- The optional app configuration mapping is available at `/config` for future custom files; the generated `weewx.conf` remains private to avoid accidental corruption.
- USB and serial devices are exposed so supported station drivers can communicate with hardware.
- The app requires Home Assistant's MQTT service. It obtains broker credentials from Supervisor automatically; no MQTT password is stored in the app options.
- MQTT Discovery creates one device named after the configured station location. Outside temperature, humidity, dew point, wind, pressure, rain, solar radiation, and UV observations appear as sensor entities when the station reports them.
- Discovery metadata, state, and availability are republished after reconnecting and whenever Home Assistant's MQTT integration announces that it has restarted.

## Next steps

- Install the add-on from this repository.
- Open the app and configure it for your weather station hardware or keep `weewx.drivers.simulator` for a hardware-free test.
- Ensure the official Mosquitto Broker app and the MQTT integration are installed. Home Assistant will discover the WeeWX device automatically after WeeWX receives its first LOOP packet.
- Open the Web UI after the first report cycle (normally about five minutes).
- Review the WeeWX documentation for station-specific drivers and reports.
