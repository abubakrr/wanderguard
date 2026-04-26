# Step 3 — Synthetic Data Generator

## What was built
Management command that generates a realistic 14-day GPS trace for a patient
in Tashkent, with normal routines and injected anomalies covering all 4 types.

## Usage
```bash
python manage.py generate_data <patient_id> --days=14
```

## Normal daily routines
| Time | Activity | Frequency |
|------|----------|-----------|
| 00:00–08:00 | Home (stationary, 5-min intervals) | Daily |
| 09:00–10:00 | Walk to pharmacy (~400m) | Mon–Fri |
| 13:00–14:00 | Mosque visit (~900m) | Friday only |
| 14:00–15:00 | Park visit (~600m) | Mon, Wed, Fri |
| 15:00–16:00 | Market (~700m) | Weekend (50% chance) |
| 19:00–23:59 | Home (stationary) | Daily |

## Anomaly types
| Type | Description | Typical time |
|------|-------------|--------------|
| WANDERING | Repetitive loops 100–200m from home | 01:00–03:00 |
| DEVIATION | Heads toward pharmacy but walks opposite direction | 09:00 |
| UNFAMILIAR | Appears 3.5–4km away at unusual hour | 15:30 |
| AIMLESS | Circular movement, 4–7 random short legs | 16:00 |

## Guarantees
- All 4 anomaly types appear at least twice
- ~8% of points flagged `is_anomaly=True`
- Point frequency: every ~45s during movement, every 5min at rest
- GPS noise: ±5–10m jitter on every point (realistic scatter)
- Battery drain simulated; recharges overnight

## Key file
- `tracking/management/commands/generate_data.py`

## Verification checklist
- [ ] `python manage.py generate_data <id> --days=14` → no errors, prints summary
- [ ] `LocationPoint.objects.filter(patient=X).count()` → 7,000–10,000
- [ ] `LocationPoint.objects.filter(patient=X, is_anomaly=True).count()` → 400–800
- [ ] All 4 anomaly types present in DB
- [ ] Re-running command clears old data and regenerates cleanly
