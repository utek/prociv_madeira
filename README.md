# ProCiv Madeira

Home Assistant integration for [ProCiv Madeira](https://www.procivmadeira.pt) weather alerts.

## Installation

1. Copy the `custom_components/prociv_madeira` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & Services → Add Integration → ProCiv Madeira**.

## Entities

### Per-region alert sensors

One sensor per region, state is `GREEN` / `YELLOW` / `ORANGE` / `RED`.

| Entity                         | Region                   |
| ------------------------------ | ------------------------ |
| `sensor.*_north_coast`         | North Coast (CN)         |
| `sensor.*_south_coast`         | South Coast (CS)         |
| `sensor.*_porto_santo`         | Porto Santo (PS)         |
| `sensor.*_mountainous_regions` | Mountainous Regions (RM) |

Each sensor exposes the following attributes:

| Attribute      | Description                            |
| -------------- | -------------------------------------- |
| `region`       | Full region name                       |
| `problem_type` | Type of hazard (e.g. Rough Seas, Wind) |
| `description`  | Free-form alert description            |
| `start_date`   | Alert validity start (ISO 8601)        |
| `end_date`     | Alert validity end (ISO 8601)          |

### Aggregate sensors

| Entity                             | Description                                     |
| ---------------------------------- | ----------------------------------------------- |
| `sensor.*_worst_alert`             | Highest-severity alert level across all regions |
| `binary_sensor.*_any_active_alert` | `on` when any region has a non-green alert      |

### Diagnostic

| Entity                | Description                                 |
| --------------------- | ------------------------------------------- |
| `sensor.*_last_fetch` | Timestamp of the last successful data fetch |

## Lovelace cards

The integration automatically registers two custom Lovelace cards — no manual resource configuration needed.

### `custom:prociv-madeira-card`

Compact card with expandable rows. Non-green alerts can be expanded to show description and validity dates.

### `custom:prociv-madeira-detail-card`

Always-expanded list showing full details for every region.

### Card configuration

Both cards accept the same options:

```yaml
type: custom:prociv-madeira-card # or custom:prociv-madeira-detail-card
entities:
  - sensor.prociv_madeira_north_coast
  - sensor.prociv_madeira_south_coast
  - sensor.prociv_madeira_porto_santo
  - sensor.prociv_madeira_mountainous_regions
binary_sensor: binary_sensor.prociv_madeira_any_active_alert
worst_sensor: sensor.prociv_madeira_worst_alert
title: 'Madeira Alerts' # optional
```

| Option          | Required | Description                                                     |
| --------------- | -------- | --------------------------------------------------------------- |
| `entities`      | Yes      | List of per-region sensor entity IDs                            |
| `binary_sensor` | No       | Any-active-alert binary sensor; drives the header shield icon   |
| `worst_sensor`  | No       | Worst-alert sensor; drives the header colour and severity badge |
| `title`         | No       | Card title override                                             |

## Configuration

The polling interval can be adjusted in the integration options (**Settings → Devices & Services → ProCiv Madeira → Configure**).

| Option        | Default    | Range            |
| ------------- | ---------- | ---------------- |
| Scan interval | 30 minutes | 5 – 1440 minutes |
