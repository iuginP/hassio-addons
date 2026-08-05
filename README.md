# iuginP Home Assistant apps

This repository is prepared to be used as a custom Home Assistant add-on repository.

## Add the repository to Home Assistant

1. In Home Assistant, open Settings -> Add-ons -> Add-on Store.
2. Click the three-dots menu in the top-right and choose "Repositories".
3. Add this repository URL:
   - https://github.com/iuginP/hassio-addons
4. Save the repository.
5. Restart Home Assistant or refresh the add-on store so the new repository is discovered.

## Install the WeeWX app

1. Open the Add-on Store after the repository has been added.
2. Find the "WeeWX" add-on and open it.
3. Click Install.
4. Start the add-on after installation completes.
5. Open the add-on web interface or inspect the logs to confirm WeeWX started correctly.

## Install the Onzo Smart Energy Meter app

Install the app from the same repository, ensure Home Assistant's MQTT integration and Mosquitto Broker app are configured, then attach one or more Onzo meters by USB. Every connected clamp is discovered as a separate Home Assistant device.

## Install the WiPcam Bridge app

Install WiPcam Bridge from the same repository, then configure the Home Assistant host's LAN IPv4 address and strong management credentials before starting it. The app discovers WiPcam/OMGuard cameras and publishes enabled feeds as RTSP streams on port 8554.

## Development

Run the repository and app validation suite locally with:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Pull requests targeting `main` run the same checks automatically.

Every add-on uses a versioned multi-architecture image from GitHub Container
Registry. Pull requests build changed add-ons without publishing them. Pushes
to `main` publish `amd64` and `aarch64` images plus the generic multi-arch
manifest consumed by Home Assistant. The workflow can also be run manually to
rebuild every add-on.

After a package is published for the first time, its visibility must be set to
**Public** in the repository owner's GitHub package settings so Home Assistant
can pull it without registry credentials.

## Notes

- WeeWX settings are available in the Home Assistant Configuration tab.
- WeeWX automatically creates a weather-station device and sensor entities through MQTT Discovery.
- Station data is stored in the app's persistent `/data` volume.
