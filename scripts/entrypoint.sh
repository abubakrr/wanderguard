#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'EOF'
import os, time, psycopg2
for _ in range(30):
    try:
        psycopg2.connect(
            host=os.environ['DB_HOST'],
            port=os.environ.get('DB_PORT', '5432'),
            dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
        )
        break
    except psycopg2.OperationalError:
        time.sleep(2)
else:
    print("Database not ready after 60 seconds — aborting"); raise SystemExit(1)
EOF

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Starting: $@"
exec "$@"
