# Deploying WanderGuard Backend on Hetzner

## First-time server setup

```bash
# 1. SSH into your Hetzner server
ssh root@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER   # optional: run docker without sudo

# 3. Clone the repo
git clone git@github.com:abubakrr/wanderguard.git
cd wanderguard

# 4. Create your .env from the template
cp .env.example .env
nano .env   # fill in SECRET_KEY, DB_PASSWORD, ALLOWED_HOSTS, DOMAIN, CERTBOT_EMAIL

# 5. Upload your Firebase service account key
scp firebase-credentials.json root@your-server-ip:/root/wanderguard/

# 6. Start everything
docker compose up -d --build

# 7. Issue TLS certificate (first time only — requires DNS pointing to this server)
docker compose --profile certbot up certbot

# 8. Reload Nginx to pick up the cert
docker compose restart nginx
```

## Day-to-day deployment (after git push from dev machine)

```bash
cd /root/wanderguard
git pull origin main
bash scripts/deploy.sh
```

## Useful commands

```bash
# Live logs
docker compose logs -f web
docker compose logs -f celery

# Django shell
docker compose exec web python manage.py shell

# Create superuser
docker compose exec web python manage.py createsuperuser

# Database backup
docker compose exec db pg_dump -U wanderguard wanderguard > backup_$(date +%F).sql

# Restore backup
docker compose exec -T db psql -U wanderguard wanderguard < backup_2026-04-27.sql

# Renew TLS cert (set up a monthly cron on the server)
docker compose --profile certbot run --rm certbot renew
docker compose restart nginx
```

## Services exposed

| Service  | Port | Description                    |
|----------|------|--------------------------------|
| Nginx    | 80   | HTTP → HTTPS redirect          |
| Nginx    | 443  | HTTPS proxy to Gunicorn        |
| Gunicorn | 8000 | Django app (internal only)     |
| Redis    | —    | Celery broker (internal only)  |
| Postgres | —    | PostGIS database (internal)    |

## Architecture

```
Internet
   │
  443
   │
Nginx ──── /static/  ──► volume (staticfiles)
   │
   │ proxy_pass
   ▼
Gunicorn (web:8000)
   │
   ├── Django ORM ──► PostgreSQL / PostGIS
   └── Celery tasks ─► Redis ─► Celery worker
```
