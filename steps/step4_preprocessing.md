# Step 4 — Preprocessing Pipeline

## What was built
Three-stage pipeline: noise filter → stay-point detection → trip segmentation.
Implemented as a reusable function (`run_preprocessing`) and a management command.

## Usage
```bash
python manage.py preprocess <patient_id>
```

## Pipeline stages

### 1. Noise filter
Removes `LocationPoint` rows where:
- `accuracy > 50m` (GPS too imprecise)
- `speed > 15 km/h` (device glitch / vehicle)

### 2. Stay-point detection
Algorithm (from build plan):
```
anchor = first point
cluster = [first point]

for each subsequent point:
    if haversine(point, anchor) < 30m:
        cluster.append(point)
    else:
        if cluster time span > 5 min → save StayPoint
        anchor = point, cluster = [point]
```
StayPoint stores: centroid, radius, arrival/departure time, duration, point count.

### 3. Trip segmentation
For each consecutive pair of stay points, collects movement points between them and computes:
- Total path distance (sum of segment lengths)
- Displacement (straight-line start→end)
- `path_to_displacement_ratio` = path / displacement
  - Normal walk: ~1.1–1.5
  - AIMLESS anomaly: > 3.0

## New models (tracking app)
- `StayPoint` — location cluster where patient stayed ≥5min
- `Trip` — movement segment between two stay points

## New files
- `tracking/preprocessing.py` — reusable pipeline function
- `tracking/management/commands/preprocess.py` — management command
- `tracking/migrations/0002_staypoint_trip.py`

## Expected output (after 14-day generate_data)
```
Preprocessing data for patient1...
  [1/3] Filtering noise...
        8,200 clean points
  [2/3] Detecting stay points...
        73 stay points
  [3/3] Segmenting trips...
        68 trips

Done!
  Clean points : 8,200
  Stay points  : 73
  Trips        : 68
```

## Verification checklist
- [ ] `python manage.py preprocess <id>` → no errors
- [ ] `StayPoint.objects.filter(patient=X).count()` → 60–90
- [ ] Most frequent centroid clusters near HOME coordinates (41.2995, 69.2401)
- [ ] `Trip.objects.filter(patient=X, path_to_displacement_ratio__gt=3).count()` → >0 (AIMLESS trips)
- [ ] Running twice gives same count (no duplicates — deletes before recreating)
