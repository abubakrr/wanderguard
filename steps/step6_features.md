# Step 6 — Feature Engineering

## What was built
`compute_features(patient, point)` → dict of 12 floats, one per GPS point.
`compute_features_batch(patient)` → (numpy array [N×12], list of points) for training.

## Features

| # | Name | Group | Description |
|---|------|-------|-------------|
| 1 | `distance_from_home` | Spatial | Metres from home learned place |
| 2 | `distance_to_nearest_learned` | Spatial | Metres to closest learned place |
| 3 | `is_inside_learned_place` | Spatial | 1.0 if within place radius, else 0.0 |
| 4 | `distance_from_usual_route` | Spatial | Min dist to any trip path midpoint |
| 5 | `displacement_from_last_staypoint` | Spatial | Metres from most recent stay point |
| 6 | `hour_sin` | Temporal | sin(2π × hour / 24) — cyclic encoding |
| 7 | `hour_cos` | Temporal | cos(2π × hour / 24) — cyclic encoding |
| 8 | `time_deviation_from_expected` | Temporal | Hours off from usual arrival at nearest place |
| 9 | `speed` | Behavioral | Point speed in m/s |
| 10 | `heading_change_rate` | Behavioral | Avg heading change (°/min) over last 3 points |
| 11 | `path_displacement_ratio` | Behavioral | From enclosing trip (AIMLESS → >3.0) |
| 12 | `minutes_since_left_home` | Context | Minutes since last home departure |

## Key design decisions
- Hour encoded as sin/cos pair to handle midnight wrap-around (23:00 ≈ 01:00)
- `PatientContext` preloads places, stay points, trips once per batch — avoids N+1 queries
- All outputs guaranteed `float`, never `None` or `NaN`
- `heading_change_rate` uses 3 previous DB points (small query, real-time safe)

## Key file
- `ml_pipeline/features.py`

## Usage
```python
from ml_pipeline.features import compute_features, compute_features_batch, PatientContext

# Single point (real-time)
ctx = PatientContext(patient)          # load once
features = compute_features(patient, point, ctx=ctx)

# Batch (training)
X, points = compute_features_batch(patient)  # returns np.ndarray [N, 12]
```

## Verification checklist
- [ ] `compute_features` returns dict with all 12 FEATURE_NAMES keys
- [ ] Point at home coords → `distance_from_home` ≈ 0, `is_inside_learned_place` = 1.0
- [ ] Point at pharmacy at 9am → `time_deviation_from_expected` < 1.0
- [ ] Point 3km away at 2am → `distance_from_home` > 3000, `hour_sin` ≈ sin(2π×2/24)
- [ ] `compute_features_batch` → shape (N, 12), no NaN values
- [ ] AIMLESS anomaly points → `path_displacement_ratio` > 3.0
