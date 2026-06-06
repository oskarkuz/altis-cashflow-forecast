# Weather Data — Brunssum

## Location

| Field     | Value              |
|-----------|--------------------|
| City      | Brunssum           |
| Province  | Limburg            |
| Latitude  | 50.9489            |
| Longitude | 5.9725             |

## Dataset Association

- **Portfolio company 2** — Dakdekkersbedrijf Peter Ummels
- **Platform**: Exact Online
- **Company ID**: 82604

## Time Periods

### Training period

| Field      | Value        |
|------------|--------------|
| Start date | 2023-01-01   |
| End date   | 2025-05-31   |
| Days       | 882          |
| First date | 2023-01-01   |
| Last date  | 2025-05-31   |

### Test period

| Field      | Value        |
|------------|--------------|
| Start date | 2025-06-01   |
| End date   | 2026-05-31   |
| Days       | 365          |
| First date | 2025-06-01   |
| Last date  | 2026-05-31   |

## Variables

All variables are **daily** aggregates. Timezone: `Europe/Amsterdam`.

| Variable                    | Unit   | Description                          |
|-----------------------------|--------|--------------------------------------|
| `temperature_2m_max`        | °C     | Maximum air temperature at 2 m       |
| `temperature_2m_min`        | °C     | Minimum air temperature at 2 m       |
| `apparent_temperature_max`  | °C     | Maximum apparent (feels-like) temp   |
| `apparent_temperature_min`  | °C     | Minimum apparent (feels-like) temp   |
| `precipitation_sum`         | mm     | Total daily precipitation            |
| `rain_sum`                  | mm     | Total daily rain                     |
| `snowfall_sum`              | cm     | Total daily snowfall                 |
| `wind_speed_10m_max`        | km/h   | Maximum wind speed at 10 m           |
| `wind_gusts_10m_max`        | km/h   | Maximum wind gusts at 10 m           |
| `weather_code`              | WMO    | WMO weather interpretation code      |

## Files

| File | Period | Days |
|------|--------|------|
| `brunssum_training_2023-01-01_2025-05-31.json` | Training (2023-01-01 – 2025-05-31) | 882 |
| `brunssum_test_2025-06-01_2026-05-31.json`     | Test (2025-06-01 – 2026-05-31)     | 365 |

## API Source

- **Endpoint**: `https://archive-api.open-meteo.com/v1/archive`
- **Docs**: <https://open-meteo.com/en/docs/historical-weather-api>
- **Fetched**: 2026-06-06
