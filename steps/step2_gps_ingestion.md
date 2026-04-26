# Step 2 — GPS Data Ingestion

## What was built
- `LocationPoint` model with PostGIS `PointField` (geography=True, SRID 4326)
- Single and batch GPS ingestion endpoints (patient app → backend)
- Auto-rejection of low-accuracy points (>50m)
- Latest location endpoint for caregiver app
- Paginated location history with optional date range filtering

## Architecture note (v1)
In this version, GPS data is POSTed by the patient's smartphone app.
Future versions will replace the app with a custom wearable device — the endpoints stay the same.

## Endpoints
| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/tracking/location/` | JWT (patient) | Submit single GPS point |
| POST | `/api/tracking/location/batch/` | JWT (patient) | Submit array of points (offline sync) |
| GET  | `/api/tracking/location/latest/<patient_id>/` | JWT (caregiver) | Most recent point for patient |
| GET  | `/api/tracking/location/history/<patient_id>/` | JWT (caregiver) | Paginated history, optional `?from=&to=` |

## Key files
- `tracking/models.py` — LocationPoint model
- `tracking/serializers.py` — lat/lng ↔ PointField conversion, accuracy validation
- `tracking/views.py` — 4 views with caregiver access control
- `tracking/urls.py` — URL routes
- `tracking/admin.py` — GIS-enabled admin
- `tracking/migrations/0001_initial.py` — DB migration

## Dependencies installed
- GDAL 3.12.4 (via Homebrew: `brew install gdal`)
- `GDAL_LIBRARY_PATH` and `GEOS_LIBRARY_PATH` set in `wanderguard/settings.py`

## DB setup (run once)
```bash
createdb wanderguard
python manage.py migrate
```

## Sample POST payload (single point)
```json
{
  "lat": 41.2995,
  "lng": 69.2401,
  "speed": 1.2,
  "accuracy": 8,
  "battery_level": 85,
  "heading": 270,
  "activity_type": "walking",
  "timestamp": "2026-04-26T08:30:00Z"
}
```

## Batch POST payload
```json
{
  "points": [
    { "lat": 41.2995, "lng": 69.2401, "speed": 0, "accuracy": 10, "battery_level": 90, "heading": 0, "activity_type": "still", "timestamp": "2026-04-26T08:00:00Z" },
    { "lat": 41.2998, "lng": 69.2405, "speed": 1.1, "accuracy": 12, "battery_level": 89, "heading": 45, "activity_type": "walking", "timestamp": "2026-04-26T08:01:00Z" }
  ]
}
```

## Verification checklist
- [ ] POST single point → 201, point stored
- [ ] POST point with accuracy=80 → 400 rejected
- [ ] POST batch of 50 points → `{"saved": 50}`
- [ ] GET latest → returns most recent point with lat/lng
- [ ] GET history with `?from=&to=` → filtered, paginated results
- [ ] `SELECT ST_AsText(point) FROM tracking_locationpoint LIMIT 1;` → returns WKT geometry
