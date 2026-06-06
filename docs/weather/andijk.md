# Weather Data — Andijk

## Location

| Field    | Value              |
|----------|--------------------|
| City     | Andijk             |
| Province | Noord-Holland      |
| Latitude | 52.7453            |
| Longitude| 5.2200             |
| Dataset  | Altis Dataset 1 (monthly aggregated revenue data) |

## Time Periods

| Period   | Start      | End        | Days |
|----------|------------|------------|------|
| Training | 2023-01-01 | 2025-05-31 | 882  |
| Test     | 2025-06-01 | 2026-05-31 | 365  |

## Variables Fetched

| Variable                   | Unit     |
|----------------------------|----------|
| temperature_2m_max         | °C       |
| temperature_2m_min         | °C       |
| apparent_temperature_max   | °C       |
| apparent_temperature_min   | °C       |
| precipitation_sum          | mm       |
| rain_sum                   | mm       |
| snowfall_sum               | cm       |
| wind_speed_10m_max         | km/h     |
| wind_gusts_10m_max         | km/h     |
| weather_code               | WMO code |

## Files

| File                                         | Period   | Size     |
| -------------------------------------------- | -------- | -------- |
| `andijk_training_2023-01-01_2025-05-31.json` | Training | 125.1 KB |
| `andijk_test_2025-06-01_2026-05-31.json`     | Test     | 52.4 KB  |

## Source

- API: [Open-Meteo Archive API](https://archive-api.open-meteo.com/v1/archive)
- Timezone: `Europe/Amsterdam`
- Fetched: 2026-06-06
