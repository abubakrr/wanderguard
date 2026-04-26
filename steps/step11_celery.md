# Step 11 — Real-Time Processing (Celery)

## What was built
- Celery app wired into Django (`wanderguard/celery.py`)
- `process_location` task: features → IF score → zone risk → risk score → alert → push
- Django `post_save` signal on `LocationPoint` fires the task automatically
- Results stored via `django-celery-results` (no separate results DB needed)

## Flow
```
POST /api/tracking/location/
  → LocationPoint saved
    → post_save signal
      → process_location.delay(point_id)   ← async
        → compute_features()
        → score_point()       (Isolation Forest)
        → get_zone_risk()     (OSM / cache)
        → compute_risk_score()
        → if WARNING/CRITICAL → Alert + FCM push
```

## Running Celery (requires Redis)
```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
source venv/bin/activate
celery -A wanderguard worker --loglevel=info

# Terminal 3 — Django
python manage.py runserver
```

## Key files
- `wanderguard/celery.py` — Celery app
- `wanderguard/__init__.py` — exposes celery_app
- `tracking/tasks.py` — process_location task
- `tracking/signals.py` — post_save signal
- `tracking/apps.py` — registers signals on app ready

## Settings added
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'django-db'
```

## Verification checklist
- [ ] Redis running: `redis-cli ping` → PONG
- [ ] Celery worker starts without errors
- [ ] POST GPS point → Celery log shows `process_location` task completed
- [ ] RiskScore created for the point within 2 seconds
- [ ] WARNING/CRITICAL point → Alert created + push sent
- [ ] Normal home point → RiskScore only, no Alert
- [ ] 100 sequential points → no crashes, no duplicate RiskScores
