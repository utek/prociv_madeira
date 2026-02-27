# ProCiv Madeira

Home Assistant integration for [ProCiv Madeira](https://www.procivmadeira.pt) weather alerts.

## Installation

1. Copy the `custom_components/prociv_madeira` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → ProCiv Madeira**.

## Entities

### Per-region alert sensors

One sensor per region, state is `GREEN` / `YELLOW` / `ORANGE` / `RED`.

| Entity                                                     | Region                   |
| ---------------------------------------------------------- | ------------------------ |
| `sensor.prociv_madeira_weather_alerts_north_coast`         | North Coast (CN)         |
| `sensor.prociv_madeira_weather_alerts_south_coast`         | South Coast (CS)         |
| `sensor.prociv_madeira_weather_alerts_porto_santo`         | Porto Santo (PS)         |
| `sensor.prociv_madeira_weather_alerts_mountainous_regions` | Mountainous Regions (RM) |

Each sensor exposes the following attributes:

| Attribute      | Description                            |
| -------------- | -------------------------------------- |
| `region`       | Full region name                       |
| `problem_type` | Type of hazard (e.g. Rough Seas, Wind) |
| `description`  | Free-form alert description            |
| `start_date`   | Alert validity start (ISO 8601)        |
| `end_date`     | Alert validity end (ISO 8601)          |

### Aggregate sensors

| Entity                                                         | Description                                     |
| -------------------------------------------------------------- | ----------------------------------------------- |
| `sensor.prociv_madeira_weather_alerts_worst_alert`             | Highest-severity alert level across all regions |
| `binary_sensor.prociv_madeira_weather_alerts_any_active_alert` | `on` when any region has a non-green alert      |

### Diagnostic

| Entity                                            | Description                                 |
| ------------------------------------------------- | ------------------------------------------- |
| `sensor.prociv_madeira_weather_alerts_last_fetch` | Timestamp of the last successful data fetch |

## Lovelace card

Use the built-in `entities` card to display the alert sensors:

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

## Configuration

The polling interval can be adjusted in the integration options (**Settings → Devices & Services → ProCiv Madeira → Configure**).

| Option        | Default    | Range            |
| ------------- | ---------- | ---------------- |
| Scan interval | 30 minutes | 5 – 1440 minutes |
