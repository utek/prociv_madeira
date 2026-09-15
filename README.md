# ProCiv Madeira

Home Assistant integration for Madeira weather warnings issued by [IPMA](https://www.ipma.pt) (Instituto Português do Mar e da Atmosfera) and relayed by [ProCiv Madeira](https://www.procivmadeira.pt). The user interface is available in English and Portuguese.

Data source: IPMA open data, [`warnings_www.json`](https://api.ipma.pt/open-data/forecast/warnings/warnings_www.json) (warnings up to 3 days ahead).

## Installation

Requires Home Assistant 2026.9.2 or newer.

### HACS

1. In HACS, open the menu (⋮) → **Custom repositories** and add `https://github.com/utek/prociv_madeira` with the type **Integration**.
2. Install **ProCiv Madeira** and restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → ProCiv Madeira**.

### Manual

1. Copy the `custom_components/prociv_madeira` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → ProCiv Madeira**.

While you add the integration it checks that the IPMA feed can be reached. Only one instance can be configured.

## Entities

The entity IDs below are for Home Assistant set to English. Home Assistant builds entity IDs from the entity names in its configured language, so with Portuguese you get, for example, `sensor.prociv_madeira_weather_alerts_costa_norte`. Entity IDs of an existing installation never change.

### Per-region alert sensors

One sensor per IPMA warning area. The state is the most severe warning in effect right now: `green` / `yellow` / `orange` / `red` (displayed as Normal / Moderate / High / Extreme). It changes when a warning starts or ends, without waiting for the next poll.

If IPMA's data for a region can't be read, for example a warning with a level the integration doesn't know, only that region's sensor becomes unavailable and the log says why. It comes back when IPMA publishes readable data again.

| Entity                                                     | Region                                  |
| ---------------------------------------------------------- | --------------------------------------- |
| `sensor.prociv_madeira_weather_alerts_north_coast`         | North Coast (CN, IPMA area MCN)         |
| `sensor.prociv_madeira_weather_alerts_south_coast`         | South Coast (CS, IPMA area MCS)         |
| `sensor.prociv_madeira_weather_alerts_porto_santo`         | Porto Santo (PS, IPMA area MPS)         |
| `sensor.prociv_madeira_weather_alerts_mountainous_regions` | Mountainous Regions (RM, IPMA area MRM) |

Each sensor exposes the following attributes:

| Attribute         | Description                                                    |
| ----------------- | -------------------------------------------------------------- |
| `region_code`     | Region code (`CN`, `CS`, `PS`, `RM`)                           |
| `region`          | Full region name                                               |
| `alert_type`      | Level of the most severe warning in effect (same as the state) |
| `color`           | Display colour for that level                                  |
| `problem_type`    | Hazard of that warning (e.g. Heat, Wind, Rough Seas)           |
| `description`     | IPMA's description of that warning, in Portuguese              |
| `start_date`      | Warning start (ISO 8601, UTC)                                  |
| `end_date`        | Warning end (ISO 8601, UTC)                                    |
| `alerts`          | All warnings in effect now                                     |
| `upcoming_alerts` | Warnings that have not started yet                             |

`alerts` and `upcoming_alerts` are not stored in the recorder history. For a warning that is already running, IPMA reports its latest bulletin time as the start, so `start_date` can move forward when a bulletin is reissued.

### Aggregate sensors

| Entity                                                         | Description                                            |
| -------------------------------------------------------------- | ------------------------------------------------------ |
| `sensor.prociv_madeira_weather_alerts_worst_alert`             | Most severe warning level in effect across all regions |
| `binary_sensor.prociv_madeira_weather_alerts_any_active_alert` | `on` when any region has a warning in effect           |

While a region sensor is unavailable, these only report what is certain: the worst alert stays available when another region is already red, and the binary sensor stays available when another region has a warning in effect. Otherwise they are unavailable too.

### Diagnostic

| Entity                                              | Description                                                                                                          |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `sensor.prociv_madeira_weather_alerts_last_fetch`   | Time of the last successful fetch; stays available while IPMA can't be reached                                       |
| `button.prociv_madeira_weather_alerts_refresh_data` | Fetches the warnings now and shows an error when that fails; presses within a few seconds of each other are combined |

## Lovelace card

The integration ships a dashboard card and loads it automatically, for UI-managed and YAML dashboards alike, so there is no resource to add:

```yaml
type: custom:prociv-madeira-weather-card
```

With no options the card finds the integration's region sensors by itself, leaving out sensors you have hidden. It opens expanded; click the header to collapse it. Level labels follow your Home Assistant language.

Regions whose sensor is unavailable are always shown, labelled as unavailable, and the header then says **No data** instead of **All Clear**.

| Option              | Default                    | Description                                                     |
| ------------------- | -------------------------- | --------------------------------------------------------------- |
| `title`             | `Madeira Weather Alerts`   | Card title                                                      |
| `entities`          | all region sensors         | Region sensors to show, as entity IDs or `{entity, name}` items |
| `entity_prefix`     | none                       | Only show region sensors whose entity ID starts with this       |
| `columns`           | `2`                        | Number of grid columns (1–4)                                    |
| `show_all`          | `false`                    | Also show regions without warnings                              |
| `severity_order`    | `true`                     | Sort regions by severity                                        |
| `show_header`       | `true`                     | Show the header with the number of warnings per level           |
| `show_last_updated` | `true`                     | Show when the data was last fetched                             |
| `show_icon`         | `true`                     | Show the level icon next to each region                         |
| `show_problem_type` | `true`                     | Show the hazard of each warning                                 |
| `show_dates`        | `true`                     | Show when each warning is in effect                             |
| `no_alerts_message` | `No weather alerts active` | Text shown when no region has warnings                          |

You can also show the sensors with the built-in `entities` card:

```yaml
type: entities
title: Madeira - Weather Alerts
icon: mdi:shield-alert
entities:
  - sensor.prociv_madeira_weather_alerts_north_coast
  - sensor.prociv_madeira_weather_alerts_south_coast
  - sensor.prociv_madeira_weather_alerts_porto_santo
  - sensor.prociv_madeira_weather_alerts_mountainous_regions
```

### Upgrading from 0.1.x

Earlier versions added the card as a dashboard resource; the first start after upgrading removes that resource. If you copied `prociv-madeira-weather-card.js` into your `www` folder and added it as a resource yourself, remove it: while an old copy is loaded it takes precedence, and the browser console shows a warning.

## Configuration

The polling interval can be adjusted in the integration options (**Settings → Devices & Services → ProCiv Madeira → Configure**).

| Option        | Default    | Range            |
| ------------- | ---------- | ---------------- |
| Scan interval | 30 minutes | 5 – 1440 minutes |

## Troubleshooting

- **Could not reach the IPMA warnings feed**: Home Assistant can't connect to `api.ipma.pt`, or IPMA answered with an HTTP error; the message ends with the reason. Check the internet connection and DNS. The integration keeps retrying.
- **The IPMA warnings feed returned unexpected data**: IPMA answered with something other than the warnings list, for example during maintenance, or no region's data could be read. The integration tries again on the next poll.
- While the feed can't be fetched the alert entities are unavailable. **Last fetch** keeps showing the last successful fetch, unless Home Assistant restarted during the outage: then it is unavailable too until the first successful fetch.
- **A single region is unavailable**: IPMA's data for that region couldn't be read. The log has a warning saying why, and the region comes back once IPMA's data is readable again.

## Credits

Warning data is provided by IPMA. The integration icon is based on Material Design Icons by Pictogrammers, licensed under the Apache License 2.0; see the [NOTICE](custom_components/prociv_madeira/brand/NOTICE) and [licence](custom_components/prociv_madeira/brand/LICENSE-2.0.txt) next to the icons.
