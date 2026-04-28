"""
Management command: seed_screenshot_data
Populates dummy LearnedPlace + LocationPoint records for the one patient,
centered on Auckland CBD, to generate heatmap and learned-places screenshots.

Usage (from repo root):
  docker compose exec web python manage.py seed_screenshot_data
  docker compose exec web python manage.py seed_screenshot_data --patient-id 2
  docker compose exec web python manage.py seed_screenshot_data --clear
"""

import random
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from ml_pipeline.models import LearnedPlace
from tracking.models import LocationPoint

User = get_user_model()

# ── Auckland CBD anchor ────────────────────────────────────────────────────────
BASE_LAT = -36.8485
BASE_LNG = 174.7633

# ~1 degree latitude  ≈ 111 km  →  1 m ≈ 0.000009°
M_PER_DEG_LAT = 111_000
M_PER_DEG_LNG = 111_000 * 0.79   # cos(-36.8°) ≈ 0.79

def offset(lat, lng, d_lat_m, d_lng_m):
    """Return (lat, lng) shifted by metres."""
    return (
        lat + d_lat_m / M_PER_DEG_LAT,
        lng + d_lng_m / M_PER_DEG_LNG,
    )


# ── Learned-place definitions ──────────────────────────────────────────────────
PLACES = [
    {
        "label": "home",
        "d_lat_m": 0, "d_lng_m": 0,
        "radius_meters": 50,
        "visit_count": 180,
        "avg_arrival_hour": 18.5,
        "avg_departure_hour": 8.2,
        "avg_duration_minutes": 840,
        "days_of_week": [0, 1, 2, 3, 4, 5, 6],
    },
    {
        "label": "frequent",
        "d_lat_m": 800, "d_lng_m": -400,   # local supermarket
        "radius_meters": 40,
        "visit_count": 62,
        "avg_arrival_hour": 10.5,
        "avg_departure_hour": 11.3,
        "avg_duration_minutes": 45,
        "days_of_week": [0, 2, 4, 6],
    },
    {
        "label": "frequent",
        "d_lat_m": -500, "d_lng_m": 900,   # GP clinic
        "radius_meters": 35,
        "visit_count": 28,
        "avg_arrival_hour": 9.0,
        "avg_departure_hour": 10.0,
        "avg_duration_minutes": 60,
        "days_of_week": [1, 3],
    },
    {
        "label": "frequent",
        "d_lat_m": 1200, "d_lng_m": 600,   # community centre
        "radius_meters": 60,
        "visit_count": 41,
        "avg_arrival_hour": 14.0,
        "avg_departure_hour": 16.0,
        "avg_duration_minutes": 120,
        "days_of_week": [0, 2, 4],
    },
    {
        "label": "occasional",
        "d_lat_m": -1500, "d_lng_m": -1000,  # park
        "radius_meters": 80,
        "visit_count": 12,
        "avg_arrival_hour": 11.0,
        "avg_departure_hour": 12.5,
        "avg_duration_minutes": 90,
        "days_of_week": [5, 6],
    },
    {
        "label": "occasional",
        "d_lat_m": 2200, "d_lng_m": -800,   # pharmacy
        "radius_meters": 30,
        "visit_count": 8,
        "avg_arrival_hour": 13.0,
        "avg_departure_hour": 13.5,
        "avg_duration_minutes": 25,
        "days_of_week": [1, 4],
    },
    {
        "label": "occasional",
        "d_lat_m": 600, "d_lng_m": 2000,    # library
        "radius_meters": 55,
        "visit_count": 6,
        "avg_arrival_hour": 10.0,
        "avg_departure_hour": 12.0,
        "avg_duration_minutes": 110,
        "days_of_week": [3, 6],
    },
]


def jitter(meters=5):
    """Small random noise in metres."""
    return random.uniform(-meters, meters)


def make_location_points(patient, place_defs, count_per_place=80, stray_count=200):
    """
    Generate LocationPoint rows:
    • Clustered points near each learned place (for heatmap hotspots)
    • Connecting walk points between places (paths)
    • A handful of stray points (noise)
    """
    now = datetime.now(timezone.utc)
    points = []

    for pdef in place_defs:
        c_lat, c_lng = offset(BASE_LAT, BASE_LNG, pdef["d_lat_m"], pdef["d_lng_m"])
        r = pdef["radius_meters"]

        for _ in range(count_per_place):
            # Gaussian cluster tighter than the place radius
            sigma_m = r * 0.4
            dlat = random.gauss(0, sigma_m)
            dlng = random.gauss(0, sigma_m)
            lat, lng = offset(c_lat, c_lng, dlat, dlng)

            # Spread timestamps over the past 60 days
            ts = now - timedelta(
                days=random.uniform(0, 60),
                hours=random.uniform(0, 2),
            )
            points.append(LocationPoint(
                patient=patient,
                point=Point(lng, lat, srid=4326),
                speed=random.uniform(0, 0.3),
                accuracy=random.uniform(5, 20),
                battery_level=random.randint(20, 100),
                heading=random.uniform(0, 360),
                activity_type="still",
                timestamp=ts,
            ))

    # Walk paths between consecutive places
    ordered = [(offset(BASE_LAT, BASE_LNG, p["d_lat_m"], p["d_lng_m"])) for p in place_defs]
    for i in range(len(ordered) - 1):
        a_lat, a_lng = ordered[i]
        b_lat, b_lng = ordered[i + 1]
        steps = 20
        for s in range(steps + 1):
            t = s / steps
            lat = a_lat + t * (b_lat - a_lat) + random.gauss(0, 3) / M_PER_DEG_LAT
            lng = a_lng + t * (b_lng - a_lng) + random.gauss(0, 3) / M_PER_DEG_LNG
            ts = now - timedelta(days=random.uniform(0, 60), minutes=random.uniform(0, 30))
            points.append(LocationPoint(
                patient=patient,
                point=Point(lng, lat, srid=4326),
                speed=random.uniform(0.8, 1.8),
                accuracy=random.uniform(5, 15),
                battery_level=random.randint(20, 100),
                heading=random.uniform(0, 360),
                activity_type="walking",
                timestamp=ts,
            ))

    # Stray / noise points within ~3 km
    for _ in range(stray_count):
        dlat = random.uniform(-3000, 3000)
        dlng = random.uniform(-3000, 3000)
        lat, lng = offset(BASE_LAT, BASE_LNG, dlat, dlng)
        ts = now - timedelta(days=random.uniform(0, 60))
        points.append(LocationPoint(
            patient=patient,
            point=Point(lng, lat, srid=4326),
            speed=random.uniform(0, 2.5),
            accuracy=random.uniform(5, 30),
            battery_level=random.randint(15, 100),
            heading=random.uniform(0, 360),
            activity_type=random.choice(["walking", "still", "in_vehicle", "unknown"]),
            timestamp=ts,
        ))

    return points


class Command(BaseCommand):
    help = "Seed dummy LearnedPlace + LocationPoint data for screenshot purposes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--patient-id", type=int, default=None,
            help="Patient user ID. Defaults to the first patient in the DB.",
        )
        parser.add_argument(
            "--clear", action="store_true",
            help="Delete ALL existing LearnedPlace and LocationPoint rows for the patient first.",
        )
        parser.add_argument(
            "--points-per-place", type=int, default=80,
            help="Number of heatmap points to generate per learned place (default 80).",
        )
        parser.add_argument(
            "--stray-points", type=int, default=200,
            help="Number of random stray location points (default 200).",
        )

    def handle(self, *args, **options):
        random.seed(42)

        # ── Resolve patient ──────────────────────────────────────────────────
        if options["patient_id"]:
            try:
                patient = User.objects.get(pk=options["patient_id"], role="patient")
            except User.DoesNotExist:
                raise CommandError(f"No patient with id={options['patient_id']}")
        else:
            patient = User.objects.filter(role="patient").first()
            if not patient:
                raise CommandError("No patient users found in the database.")

        self.stdout.write(f"Target patient: {patient.username} (id={patient.pk})")

        # ── Optionally clear existing data ───────────────────────────────────
        if options["clear"]:
            lp_count = LearnedPlace.objects.filter(patient=patient).count()
            loc_count = LocationPoint.objects.filter(patient=patient).count()
            LearnedPlace.objects.filter(patient=patient).delete()
            LocationPoint.objects.filter(patient=patient).delete()
            self.stdout.write(
                self.style.WARNING(
                    f"Deleted {lp_count} LearnedPlace + {loc_count} LocationPoint rows."
                )
            )

        # ── Seed LearnedPlaces ───────────────────────────────────────────────
        learned_places = []
        for pdef in PLACES:
            lat, lng = offset(BASE_LAT, BASE_LNG, pdef["d_lat_m"], pdef["d_lng_m"])
            lp = LearnedPlace(
                patient=patient,
                centroid=Point(lng, lat, srid=4326),
                radius_meters=pdef["radius_meters"],
                visit_count=pdef["visit_count"],
                avg_arrival_hour=pdef["avg_arrival_hour"],
                avg_departure_hour=pdef["avg_departure_hour"],
                avg_duration_minutes=pdef["avg_duration_minutes"],
                days_of_week=pdef["days_of_week"],
                label=pdef["label"],
            )
            learned_places.append(lp)

        LearnedPlace.objects.bulk_create(learned_places)
        self.stdout.write(self.style.SUCCESS(f"Created {len(learned_places)} LearnedPlace records."))

        # ── Seed LocationPoints ──────────────────────────────────────────────
        loc_points = make_location_points(
            patient,
            PLACES,
            count_per_place=options["points_per_place"],
            stray_count=options["stray_points"],
        )
        LocationPoint.objects.bulk_create(loc_points, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Created {len(loc_points)} LocationPoint records."))

        self.stdout.write(self.style.SUCCESS("\nDone! Open the app to take your screenshots."))
