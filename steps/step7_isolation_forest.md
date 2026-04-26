# Step 7 — Anomaly Detection Model (Isolation Forest)

## Usage
```bash
python manage.py train_model <patient_id>
```

## What was built
- Isolation Forest trained on normal points only (`is_anomaly=False`)
- Decision function normalized to [0, 1] anomaly score (0 = normal, 1 = anomaly)
- Threshold baseline for comparison (flags `distance_from_home > 500m`)
- Model saved to `models/patient_<id>_isolation_forest.joblib`
- `TrainedModel` DB record tracks path, metrics, active flag
- `score_point(patient, point)` for real-time single-point scoring (Step 11)

## Key files
- `ml_pipeline/training.py` — train_model(), load_model(), score_point()
- `ml_pipeline/management/commands/train_model.py`
- `ml_pipeline/migrations/0002_trainedmodel.py`

## Full pipeline to this point
```bash
python manage.py migrate
python manage.py generate_data 1 --days=14
python manage.py preprocess 1
python manage.py learn_patterns 1
python manage.py train_model 1
```

## Expected output
```
Training model for patient1...
  Computing features for 8,412 points...
  Training on 7,789 normal points (623 anomalies held out)...
  IF   → P=0.821  R=0.764  F1=0.791  AUC=0.934
  Base → P=0.312  R=0.891  F1=0.462

Isolation Forest vs Threshold Baseline:
  Metric       IF    Baseline
  --------------------------------
  Precision   0.821      0.312
  Recall      0.764      0.891
  F1          0.791      0.462
  AUC         0.934        N/A
```

## Verification checklist
- [ ] Model file exists at `models/patient_1_isolation_forest.joblib`
- [ ] TrainedModel record created in DB with is_active=True
- [ ] IF F1 > Threshold baseline F1 (key thesis result)
- [ ] AUC > 0.85
- [ ] Normal points score mostly < 0.5, anomaly points mostly > 0.5
