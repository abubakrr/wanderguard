# Step 1 — Project Scaffolding & Auth

## What was built
- Django 6 project `wanderguard` with 4 apps: `accounts`, `tracking`, `ml_pipeline`, `alerts`
- Custom `User` model (extends AbstractUser) with `role` (patient/caregiver), `phone`, `link_code`
- `PatientProfile` model linking patient → caregiver
- JWT auth via `djangorestframework-simplejwt`
- CORS headers middleware

## Endpoints
| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/auth/register/` | None | Register patient or caregiver, returns JWT |
| POST | `/api/auth/login/` | None | Login, returns access + refresh tokens |
| POST | `/api/auth/refresh/` | None | Refresh access token |
| GET  | `/api/auth/me/` | JWT | Returns current user info |
| POST | `/api/patients/link/` | JWT (caregiver) | Caregiver links to patient via link_code |
| GET  | `/api/patients/my-patients/` | JWT (caregiver) | List all linked patients |

## Key files
- `accounts/models.py` — User + PatientProfile models
- `accounts/serializers.py` — Register, User, PatientProfile, LinkPatient serializers
- `accounts/views.py` — Register, Me, LinkPatient, MyPatients views
- `accounts/urls.py` — URL routes
- `accounts/admin.py` — Admin panel config
- `wanderguard/settings.py` — Full settings with JWT, CORS, DRF config

## DB setup (run once)
```bash
createdb wanderguard
python manage.py migrate
python manage.py createsuperuser
```

## Verification checklist
- [ ] `python manage.py migrate` runs clean
- [ ] POST /api/auth/register/ with role=patient → returns JWT + link_code
- [ ] POST /api/auth/register/ with role=caregiver → returns JWT
- [ ] POST /api/auth/login/ → returns access + refresh tokens
- [ ] GET /api/auth/me/ with Bearer token → returns user with role
- [ ] POST /api/patients/link/ with patient's link_code → caregiver linked
- [ ] GET /api/patients/my-patients/ → lists linked patients
- [ ] Admin panel at /admin/ shows Users with role column
