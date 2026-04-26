# Step 10 — Push Notifications (FCM)

## What was built
- `DeviceToken` model to store caregiver FCM tokens
- `send_alert_notification(alert)` — sends push to all active tokens for caregiver
- `register_device_token(user, token, device_type)` — upserts token
- `POST /api/device-token/` endpoint for apps to register tokens
- Notifications wired into risk engine: fired automatically on Alert creation

## Setup (production)
1. Create Firebase project → download service account JSON
2. Set in settings.py:
   ```python
   FIREBASE_CREDENTIALS_PATH = '/path/to/firebase-credentials.json'
   ```
3. Without credentials file → push silently disabled (safe for dev/test)

## Push payload
```json
{
  "title": "WanderGuard — CRITICAL alert",
  "body": "Ahmed: Risk level CRITICAL. Anomaly score: 0.91...",
  "data": {
    "alert_id": "42",
    "patient_id": "1",
    "risk_level": "critical",
    "alert_type": "wandering",
    "lat": "41.2995",
    "lng": "69.2401"
  }
}
```

## Key files
- `alerts/notifications.py` — FCM logic
- `alerts/models.py` — DeviceToken model
- `alerts/views.py` + `alerts/urls.py` — token registration endpoint
- `alerts/migrations/0002_devicetoken.py`

## Verification checklist
- [ ] `POST /api/device-token/` with `{token, device_type}` → 200
- [ ] DeviceToken record created in DB
- [ ] Alert created → push sent to caregiver's tokens (check Firebase console)
- [ ] Invalid/expired token → is_active set to False, no crash
- [ ] Missing credentials file → server starts normally, push silently skipped
