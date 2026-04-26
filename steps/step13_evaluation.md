# Step 13 — Evaluation & Benchmarking

## Usage
```bash
python manage.py evaluate_model <patient_id>
```

Output saved to `evaluation/<patient_id>/`:
- `metrics.json` — all numeric results
- `roc_curve.png`
- `confusion_matrix.png`
- `feature_importance.png`

## Metrics computed

### 1. Overall (Isolation Forest)
Precision, Recall, F1, AUC — against ground-truth `is_anomaly` labels.

### 2. Per anomaly type
Separate P/R/F1 for WANDERING, DEVIATION, UNFAMILIAR, AIMLESS.

### 3. Baseline comparison
| Baseline | Description |
|----------|-------------|
| geofence_200m | Flag if `distance_from_home > 200m` |
| threshold_500m | Flag if `distance_from_home > 500m` |

### 4. Inference time
Average ms per point (100 points × 100 runs).

### 5. Feature importance (permutation ablation)
Shuffle each feature column, measure F1 drop.
Higher drop = more important feature.

## Expected results (14-day synthetic data)
```
Overall → P≈0.82  R≈0.77  F1≈0.79  AUC≈0.93

WANDERING    → F1≈0.85
DEVIATION    → F1≈0.75
UNFAMILIAR   → F1≈0.90
AIMLESS      → F1≈0.72

Baselines:
  geofence_200m  → F1≈0.41
  threshold_500m → F1≈0.46

Inference: ~0.05 ms/point
```

## Key file
- `ml_pipeline/management/commands/evaluate_model.py`

## Verification checklist
- [ ] `python manage.py evaluate_model 1` → no errors
- [ ] `evaluation/1/metrics.json` exists with all keys
- [ ] 3 PNG charts generated
- [ ] IF F1 > geofence_200m F1 (key thesis result)
- [ ] IF F1 > threshold_500m F1
- [ ] AUC > 0.85
- [ ] `distance_from_home` and `hour_sin`/`hour_cos` appear as top features
