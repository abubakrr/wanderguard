# Step 5 — DBSCAN Pattern Learning

## What was built
DBSCAN clustering over stay points to discover the patient's frequent places.
Results stored as `LearnedPlace` records — used downstream by feature engineering
and anomaly scoring.

## Usage
```bash
python manage.py learn_patterns <patient_id>
```

## Algorithm
```
coords_rad = radians([[lat, lng], ...])  # one row per stay point
dist_matrix = haversine_distances(coords_rad) * 6_371_000  # → metres

DBSCAN(eps=50m, min_samples=3, metric='precomputed').fit(dist_matrix)

For each cluster:
  centroid  = mean(lat), mean(lng)
  radius    = max dist from centroid to any member
  visit_count = number of stay points in cluster
  avg_arrival/departure_hour, avg_duration, days_of_week computed from members

Highest visit_count → label='home'
Others → 'frequent' (≥5 visits) or 'occasional'
Noise points (label=-1) → discarded
```

## LearnedPlace model (ml_pipeline app)
Fields: `centroid`, `radius_meters`, `visit_count`, `avg_arrival_hour`,
`avg_departure_hour`, `avg_duration_minutes`, `days_of_week`, `label`

## New files
- `ml_pipeline/models.py` — LearnedPlace model
- `ml_pipeline/pattern_learning.py` — reusable learn_patterns() function
- `ml_pipeline/management/commands/learn_patterns.py` — management command
- `ml_pipeline/admin.py` — GIS admin
- `ml_pipeline/migrations/0001_initial.py`

## Expected output (after 14-day synthetic data + preprocessing)
```
Learning patterns for patient1...
  73 stay points → 4 clusters, 5 noise
  Saved 4 learned places.

Learned places (4):
  [HOME      ] visits= 42  avg_arrival=19.2h  avg_dur= 480.0min  days=[0,1,2,3,4,5,6]
  [FREQUENT  ] visits= 13  avg_arrival= 9.4h  avg_dur=  22.5min  days=[0,1,2,3,4]
  [FREQUENT  ] visits=  9  avg_arrival=14.2h  avg_dur=  41.0min  days=[0,2,4]
  [OCCASIONAL] visits=  4  avg_arrival=13.1h  avg_dur=  62.0min  days=[4]
```

## Full pipeline to this point
```bash
python manage.py migrate
python manage.py generate_data 1 --days=14
python manage.py preprocess 1
python manage.py learn_patterns 1
```

## Verification checklist
- [ ] LearnedPlace.objects.filter(patient=X).count() → 3–5
- [ ] One place labeled 'home' with highest visit_count
- [ ] 'home' avg_arrival_hour ≈ 19 (7pm), avg_departure_hour ≈ 8 (8am)
- [ ] Mosque place days_of_week = [4] (Friday only)
- [ ] Noise stay points NOT saved as learned places
- [ ] Running twice gives same count (no duplicates)
