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

## Development

Run the repository and app validation suite locally with:

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Pull requests targeting `main` run the same checks automatically.

## Notes

- The first add-on implemented here is WeeWX.
- WeeWX settings are available in the Home Assistant Configuration tab.
- Station data is stored in the app's persistent `/data` volume.
