# Weather Data — Winschoten

## Location

| Field    | Value                          |
| -------- | ------------------------------ |
| City     | Winschoten                     |
| Province | Groningen                      |
| Latitude | 53.1427                        |
| Longitude| 7.0356                         |
| Dataset  | Altis Dataset 2 (Company E)    |
| Source   | Gilde journal entries          |

## Data source

Open-Meteo Archive API (`https://archive-api.open-meteo.com/v1/archive`)
Timezone: `Europe/Amsterdam`

## Time periods

### Training period

| Property   | Value                                                        |
| ---------- | ------------------------------------------------------------ |
| Range      | 2023-01-01 → 2025-05-31                                     |
| Days       | 882                                                          |
| First date | 2023-01-01                                                   |
| Last date  | 2025-05-31                                                   |
| File       | `winschoten_training_2023-01-01_2025-05-31.json`             |

### Test period

| Property   | Value                                                        |
| ---------- | ------------------------------------------------------------ |
| Range      | 2025-06-01 → 2026-05-31                                     |
| Days       | 365                                                          |
| First date | 2025-06-01                                                   |
| Last date  | 2026-05-31                                                   |
| File       | `winschoten_test_2025-06-01_2026-05-31.json`                 |

## Variables fetched (daily)

| Variable                    | Unit     | Description                        |
| --------------------------- | -------- | ---------------------------------- |
| `temperature_2m_max`        | °C       | Daily maximum temperature at 2 m   |
| `temperature_2m_min`        | °C       | Daily minimum temperature at 2 m   |
| `apparent_temperature_max`  | °C       | Daily max apparent (feels-like)    |
| `apparent_temperature_min`  | °C       | Daily min apparent (feels-like)    |
| `precipitation_sum`         | mm       | Total daily precipitation          |
| `rain_sum`                  | mm       | Total daily rain                   |
| `snowfall_sum`              | cm       | Total daily snowfall               |
| `wind_speed_10m_max`        | km/h     | Maximum wind speed at 10 m         |
| `wind_gusts_10m_max`        | km/h     | Maximum wind gusts at 10 m         |
| `weather_code`              | WMO code | Daily weather condition code       |

## JSON structure

Each file contains the raw Open-Meteo response:

```json
{
  "latitude": 53.14,
  "longitude": 7.04,
  "generationtime_ms": ...,
  "utc_offset_seconds": ...,
  "timezone": "Europe/Amsterdam",
  "daily_units": { ... },
  "daily": {
    "time": ["2023-01-01", ...],
    "temperature_2m_max": [...],
    ...
  }
}
```

## Fetch script

`_fetch_winschoten.py` in this directory reproduces the download using only Python stdlib (`urllib`).
