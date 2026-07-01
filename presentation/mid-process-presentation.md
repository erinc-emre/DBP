# Mid-Process Presentation

Working outline for the mid-project presentation. Topics added incrementally.

---

## 1. OpenSky API Format

**Auth — OAuth2 client credentials**
- POST `client_id` + `client_secret` → 30-min `access_token`
- Send as `Authorization: Bearer <token>` on every call

**Endpoint used — flight trajectory**
- `GET /tracks/all?icao24=<hex>&time=<unix>` → one flight's path
- Keyed on **`icao24`** (transponder hex), not flight number

**Track response**
```jsonc
{ "icao24": "3c6487", "callsign": "DLH67K",
  "startTime": ..., "endTime": ...,
  "path": [ [time, lat, lon, baro_altitude, true_track, on_ground], ... ] }
```
Waypoint array (positional, to save bandwidth):

| idx | field | unit |
|----|-------|------|
| 0 | time | Unix seconds (UTC) |
| 1 | latitude | ° WGS-84 |
| 2 | longitude | ° WGS-84 |
| 3 | baro_altitude | meters (null/0 on ground) |
| 4 | true_track | ° from north (heading) |
| 5 | on_ground | bool |

**Key limits:** REST `/tracks` ≤ 30 days & experimental · no speed field (derived later) · credits per call (fair use).

---

<!-- Add next topics below -->
