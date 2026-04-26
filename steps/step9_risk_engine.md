# Step 9 — Dynamic Risk Score Engine

## What was built
`compute_risk_score(patient, point)` → persisted `RiskScore` + optional `Alert`.

## Formula
```
combined = 0.40 × anomaly_score     (Isolation Forest output)
         + 0.20 × zone_risk          (OSM POI classification)
         + 0.20 × time_factor        (cosine peak at 2am)
         + 0.20 × distance_factor    (saturates at 2km from home)
```

## Risk levels
| Score | Level | Action |
|-------|-------|--------|
| < 0.3 | safe | No alert |
| 0.3–0.6 | caution | No alert |
| 0.6–0.8 | warning | Alert created |
| > 0.8 | critical | Alert created |

## Alert type inference
| Condition | Type |
|-----------|------|
| anomaly > 0.85 + distance > 70% of 2km | unfamiliar |
| anomaly > 0.85 + night hours | wandering |
| anomaly > 0.7 | deviation |
| otherwise | general |

## New models (alerts app)
- `RiskScore` — one per GPS point, stores all 4 components + combined
- `Alert` — created for warning/critical, linked to caregiver

## Key files
- `alerts/models.py` — RiskScore, Alert
- `alerts/risk_engine.py` — compute_risk_score(), factor helpers
- `alerts/admin.py`
- `alerts/migrations/0001_initial.py`

## Verification checklist
- [ ] Point at home, noon → risk_level='safe'
- [ ] Point 2km away at 2am → risk_level='critical', Alert created
- [ ] Alert linked to correct caregiver via PatientProfile
- [ ] Running compute_risk_score twice on same point creates two RiskScore rows (expected — called per real-time point)
