# ProCiv Madeira

Home Assistant integration for ProCiv Madeira alerts.

## What?

This repository contains the ProCiv Madeira custom integration for Home Assistant.

File | Purpose | Documentation
-- | -- | --
`.devcontainer.json` | Used for development/testing with Visual Studio Code. | [Documentation](https://code.visualstudio.com/docs/remote/containers)
`custom_components/prociv_madeira/*` | Integration files, this is where everything happens. | [Documentation](https://developers.home-assistant.io/docs/creating_component_index)
`LICENSE` | The license file for the project. | [Documentation](https://help.github.com/en/github/creating-cloning-and-archiving-repositories/licensing-a-repository)
`README.md` | The file you are reading now, should contain info about the integration, installation and configuration instructions. | [Documentation](https://help.github.com/en/github/writing-on-github/basic-writing-and-formatting-syntax)
`requirements.txt` | Python packages used for development/lint/testing this integration. | [Documentation](https://pip.pypa.io/en/stable/user_guide/#requirements-files)

## Installation

1. Copy the `custom_components/prociv_madeira` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → ProCiv Madeira**.

## Features

- Displays ProCiv Madeira weather/safety alerts as sensor entities.
- Each alert is represented as a separate sensor with its alert type as the state.
- Extra attributes include region, problem type, description, start date, and end date.
