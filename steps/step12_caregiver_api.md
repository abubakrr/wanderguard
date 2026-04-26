# Step 12 — Caregiver API Endpoints

## All endpoints
| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/device-token/` | JWT | Register FCM token |
| POST | `/api/alerts/sos/` | JWT (patient) | Patient triggers SOS |
| GET  | `/api/alerts/` | JWT (caregiver) | List alerts (`?unread=1` for unread only) |
| GET  | `/api/alerts/unread-count/` | JWT (caregiver) | Count of unread alerts |
| POST | `/api/alerts/<id>/resolve/` | JWT (caregiver) | Mark alert read + resolved |
| GET  | `/api/patients/<id>/overview/` | JWT (caregiver) | Name, latest location, risk level |
| GET  | `/api/patients/<id>/risk-history/` | JWT (caregiver) | Paginated RiskScore timeline |
| GET  | `/api/tracking/heatmap/<id>/` | JWT (caregiver) | Lat/lng/weight for heatmap |
| GET  | `/api/ml/learned-places/<id>/` | JWT (caregiver) | Patient's learned places |
| GET  | `/api/tracking/location/latest/<id>/` | JWT (caregiver) | Most recent GPS point |
| GET  | `/api/tracking/location/history/<id>/` | JWT (caregiver) | Paginated GPS history |
| GET  | `/api/patients/my-patients/` | JWT (caregiver) | List all linked patients |

## Key files
- `alerts/views.py` — all caregiver + patient views
- `alerts/urls.py` — routes
- `alerts/serializers.py` — Alert, RiskScore serializers

## Verification checklist
- [ ] All endpoints return 403 for caregivers accessing other caregivers' patients
- [ ] GET /api/patients/<id>/overview/ → name, location, risk_level, last_update
- [ ] GET /api/alerts/ → list with patient_name, alert_type, risk_level, lat/lng
- [ ] POST /api/alerts/<id>/resolve/ → is_resolved=True
- [ ] GET /api/alerts/unread-count/ → correct integer
- [ ] GET /api/tracking/heatmap/<id>/ → list of {lat, lng, weight} (anomalies weight=2)
- [ ] GET /api/ml/learned-places/<id>/ → places with label, radius, visit_count
- [ ] POST /api/alerts/sos/ with lat/lng → Alert created, push sent
