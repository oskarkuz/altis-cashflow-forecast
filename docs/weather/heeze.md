# Weather Data — Heeze

## Location

| Field | Value |
|-------|-------|
| City | Heeze |
| Province | Noord-Brabant (+ Limburg operations) |
| Latitude | 51.3812 |
| Longitude | 5.573 |
| Timezone | Europe/Amsterdam |
| Dataset | Portfolio company — Snelstart GB exports (GL 8000/8001/8002) |

## Time Periods

| Period | Start | End | Days | File |
|--------|-------|-----|------|------|
| Training | 2023-01-01 | 2025-05-31 | 882 | `heeze_training_2023-01-01_2025-05-31.json` |
| Test | 2025-06-01 | 2026-05-31 | 365 | `heeze_test_2025-06-01_2026-05-31.json` |

## Variables

| Variable | Unit |
|----------|------|
| `temperature_2m_max` | °C |
| `temperature_2m_min` | °C |
| `apparent_temperature_max` | °C |
| `apparent_temperature_min` | °C |
| `precipitation_sum` | mm |
| `rain_sum` | mm |
| `snowfall_sum` | cm |
| `wind_speed_10m_max` | km/h |
| `wind_gusts_10m_max` | km/h |
| `weather_code` | WMO code |

## API

- Endpoint: `https://archive-api.open-meteo.com/v1/archive`
- Params: `latitude=51.3812&longitude=5.573&daily=...&timezone=Europe/Amsterdam`

*Generated 2026-06-06 14:14*
