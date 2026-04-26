"""
Management command: python manage.py generate_data <patient_id> [--days=14]

Generates a realistic synthetic GPS trace for an Alzheimer's patient based in
Tashkent. Normal routines are interspersed with ~8% anomalous episodes covering
all four anomaly types: WANDERING, DEVIATION, UNFAMILIAR, AIMLESS.
"""

import math
import random
from datetime import datetime, timedelta, timezone

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError

from tracking.models import LocationPoint

User = get_user_model()

# ── Geography ──────────────────────────────────────────────────────────────────
HOME = (41.2995, 69.2401)          # lat, lng — residential Tashkent

DESTINATIONS = {
    'pharmacy':  (41.3025, 69.2430),   # ~400m NE
    'park':      (41.2960, 69.2350),   # ~600m SW
    'mosque':    (41.3010, 69.2480),   # ~900m E
    'market':    (41.2975, 69.2330),   # ~700m W
}

ANOMALY_TARGETS = {
    'unfamiliar_a': (41.3250, 69.2650),   # 3.5km away
    'unfamiliar_b': (41.2700, 69.2100),   # 4km away
}


# ── Geometry helpers ───────────────────────────────────────────────────────────

def haversine(lat1, lng1, lat2, lng2):
    """Distance in metres between two lat/lng points."""
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def offset(lat, lng, dlat_m, dlng_m):
    """Shift a point by metres in lat and lng directions."""
    return (
        lat + dlat_m / 111_320,
        lng + dlng_m / (111_320 * math.cos(math.radians(lat))),
    )


def jitter(lat, lng, radius_m=8):
    """Add small random GPS noise (simulates real device scatter)."""
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(0, radius_m)
    return offset(lat, lng, dist * math.sin(angle), dist * math.cos(angle))


def interpolate(p1, p2, steps, speed_ms=1.2):
    """Yield (lat, lng, speed) points walking from p1 to p2."""
    for i in range(steps):
        t = i / max(steps - 1, 1)
        lat = p1[0] + t * (p2[0] - p1[0])
        lng = p1[1] + t * (p2[1] - p1[1])
        yield jitter(lat, lng), speed_ms


def heading_between(p1, p2):
    """Compass heading in degrees from p1 to p2."""
    dlng = p2[1] - p1[1]
    dlat = p2[0] - p1[0]
    angle = math.degrees(math.atan2(dlng, dlat))
    return angle % 360


# ── Point factory ──────────────────────────────────────────────────────────────

def make_point(patient, lat, lng, ts, speed=0.0, activity='still',
               battery=None, is_anomaly=False, anomaly_type=''):
    if battery is None:
        battery = random.randint(40, 100)
    lat, lng = jitter(lat, lng, radius_m=5 if activity == 'still' else 10)
    return LocationPoint(
        patient=patient,
        point=Point(lng, lat, srid=4326),
        speed=round(speed, 2),
        accuracy=random.uniform(4, 18),
        battery_level=battery,
        heading=random.uniform(0, 360) if activity == 'still' else 0,
        activity_type=activity,
        timestamp=ts,
        is_anomaly=is_anomaly,
        anomaly_type=anomaly_type,
    )


# ── Segment generators ─────────────────────────────────────────────────────────

def gen_stationary(patient, lat, lng, start, duration_min, battery_start):
    """Patient is still at (lat, lng) for duration_min minutes."""
    points = []
    interval = timedelta(minutes=5)
    t = start
    end = start + timedelta(minutes=duration_min)
    battery = battery_start
    while t < end:
        points.append(make_point(patient, lat, lng, t, speed=0.0,
                                  activity='still', battery=battery))
        battery = max(10, battery - random.randint(0, 1))
        t += interval
    return points, battery


def gen_walk(patient, origin, dest, start, battery_start, speed_ms=1.2,
             is_anomaly=False, anomaly_type=''):
    """Walk from origin to dest; returns (points, arrival_time, battery)."""
    dist = haversine(*origin, *dest)
    walk_secs = dist / speed_ms
    steps = max(2, int(walk_secs / 45))   # point every ~45s
    interval = timedelta(seconds=walk_secs / steps)

    points = []
    t = start
    battery = battery_start
    hdg = heading_between(origin, dest)

    for (lat, lng), spd in interpolate(origin, dest, steps, speed_ms):
        p = make_point(patient, lat, lng, t, speed=spd, activity='walking',
                       battery=battery, is_anomaly=is_anomaly,
                       anomaly_type=anomaly_type)
        p.heading = hdg
        points.append(p)
        battery = max(10, battery - random.randint(0, 1))
        t += interval

    return points, t, battery


# ── Anomaly generators ─────────────────────────────────────────────────────────

def gen_wandering(patient, start, battery):
    """WANDERING: looping 100-200m from home at night (1–3am)."""
    pts = []
    t = start
    for _ in range(random.randint(2, 4)):
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(100, 200)
        loop_lat, loop_lng = offset(*HOME, radius * math.sin(angle),
                                          radius * math.cos(angle))
        new_pts, t, battery = gen_walk(
            patient, HOME, (loop_lat, loop_lng), t, battery,
            is_anomaly=True, anomaly_type='WANDERING')
        pts.extend(new_pts)
        new_pts, t, battery = gen_walk(
            patient, (loop_lat, loop_lng), HOME, t, battery,
            is_anomaly=True, anomaly_type='WANDERING')
        pts.extend(new_pts)
    return pts, t, battery


def gen_deviation(patient, start, battery):
    """DEVIATION: starts toward pharmacy but veers opposite direction."""
    opposite = offset(*HOME, -400, -400)
    pts, t, battery = gen_walk(
        patient, HOME, opposite, start, battery,
        is_anomaly=True, anomaly_type='DEVIATION')
    # return home
    pts2, t, battery = gen_walk(patient, opposite, HOME, t, battery,
                                is_anomaly=True, anomaly_type='DEVIATION')
    pts.extend(pts2)
    return pts, t, battery


def gen_unfamiliar(patient, start, battery):
    """UNFAMILIAR: appears 3-4km away at an odd hour."""
    target = random.choice(list(ANOMALY_TARGETS.values()))
    pts, t, battery = gen_walk(patient, HOME, target, start, battery,
                               speed_ms=2.0,
                               is_anomaly=True, anomaly_type='UNFAMILIAR')
    stay, battery = gen_stationary(patient, *target, t, 20, battery)
    pts.extend(stay)
    t += timedelta(minutes=20)
    pts2, t, battery = gen_walk(patient, target, HOME, t, battery,
                                speed_ms=2.0,
                                is_anomaly=True, anomaly_type='UNFAMILIAR')
    pts.extend(pts2)
    return pts, t, battery


def gen_aimless(patient, start, battery):
    """AIMLESS: circular movement, high distance/displacement ratio."""
    pts = []
    t = start
    pos = HOME
    for _ in range(random.randint(4, 7)):
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(80, 150)
        next_pos = offset(*pos, radius * math.sin(angle), radius * math.cos(angle))
        new_pts, t, battery = gen_walk(
            patient, pos, next_pos, t, battery,
            is_anomaly=True, anomaly_type='AIMLESS')
        pts.extend(new_pts)
        pos = next_pos
    # drift back
    new_pts, t, battery = gen_walk(patient, pos, HOME, t, battery,
                                   is_anomaly=True, anomaly_type='AIMLESS')
    pts.extend(new_pts)
    return pts, t, battery


ANOMALY_GENERATORS = [gen_wandering, gen_deviation, gen_unfamiliar, gen_aimless]


# ── Daily schedule ─────────────────────────────────────────────────────────────

def generate_day(patient, date, battery, weekday, inject_anomaly=None):
    """
    Generate one day's worth of LocationPoints.
    Returns (points, battery_at_end).
    inject_anomaly: None | 'WANDERING' | 'DEVIATION' | 'UNFAMILIAR' | 'AIMLESS'
    """
    pts = []

    def dt(hour, minute=0):
        return datetime(date.year, date.month, date.day,
                        hour, minute, tzinfo=timezone.utc)

    # ── Night: home 00:00 → 08:00 ──────────────────────────────────────────
    if inject_anomaly == 'WANDERING':
        # sleep until 1am, then wander
        night_pts, battery = gen_stationary(patient, *HOME, dt(0), 60, battery)
        pts.extend(night_pts)
        wander_pts, t_after, battery = gen_wandering(patient, dt(1), battery)
        pts.extend(wander_pts)
        # back home until morning
        rest_min = max(0, int((dt(8) - t_after).total_seconds() / 60))
        rest_pts, battery = gen_stationary(patient, *HOME, t_after, rest_min, battery)
        pts.extend(rest_pts)
    else:
        night_pts, battery = gen_stationary(patient, *HOME, dt(0), 480, battery)
        pts.extend(night_pts)

    # ── Morning walk: pharmacy (Mon–Fri) ────────────────────────────────────
    if weekday < 5:  # Mon–Fri
        if inject_anomaly == 'DEVIATION':
            dev_pts, t_after, battery = gen_deviation(patient, dt(9), battery)
            pts.extend(dev_pts)
        else:
            walk_pts, t_after, battery = gen_walk(
                patient, HOME, DESTINATIONS['pharmacy'], dt(9), battery)
            pts.extend(walk_pts)
            stay_pts, battery = gen_stationary(
                patient, *DESTINATIONS['pharmacy'], t_after, 20, battery)
            pts.extend(stay_pts)
            t_after += timedelta(minutes=20)
            ret_pts, t_after, battery = gen_walk(
                patient, DESTINATIONS['pharmacy'], HOME, t_after, battery)
            pts.extend(ret_pts)
    else:
        t_after = dt(10)

    # ── Midday: home ────────────────────────────────────────────────────────
    mid_end = dt(13) if weekday == 4 else dt(14)  # shorter midday on Friday
    home_min = max(0, int((mid_end - t_after).total_seconds() / 60))
    home_pts, battery = gen_stationary(patient, *HOME, t_after, home_min, battery)
    pts.extend(home_pts)

    # ── Friday mosque ───────────────────────────────────────────────────────
    if weekday == 4:
        walk_pts, t_after, battery = gen_walk(
            patient, HOME, DESTINATIONS['mosque'], dt(13), battery)
        pts.extend(walk_pts)
        stay_pts, battery = gen_stationary(
            patient, *DESTINATIONS['mosque'], t_after, 60, battery)
        pts.extend(stay_pts)
        t_after += timedelta(minutes=60)
        ret_pts, t_after, battery = gen_walk(
            patient, DESTINATIONS['mosque'], HOME, t_after, battery)
        pts.extend(ret_pts)

    # ── Afternoon park (Mon, Wed, Fri) ──────────────────────────────────────
    elif weekday in (0, 2, 4):
        walk_pts, t_after, battery = gen_walk(
            patient, HOME, DESTINATIONS['park'], dt(14), battery)
        pts.extend(walk_pts)
        stay_pts, battery = gen_stationary(
            patient, *DESTINATIONS['park'], t_after, 40, battery)
        pts.extend(stay_pts)
        t_after += timedelta(minutes=40)
        ret_pts, t_after, battery = gen_walk(
            patient, DESTINATIONS['park'], HOME, t_after, battery)
        pts.extend(ret_pts)

    # ── Occasional market ───────────────────────────────────────────────────
    elif weekday == 6 and random.random() < 0.5:
        walk_pts, t_after, battery = gen_walk(
            patient, HOME, DESTINATIONS['market'], dt(15), battery)
        pts.extend(walk_pts)
        stay_pts, battery = gen_stationary(
            patient, *DESTINATIONS['market'], t_after, 30, battery)
        pts.extend(stay_pts)
        t_after += timedelta(minutes=30)
        ret_pts, t_after, battery = gen_walk(
            patient, DESTINATIONS['market'], HOME, t_after, battery)
        pts.extend(ret_pts)
    else:
        t_after = dt(15)

    # ── Afternoon/evening anomalies ─────────────────────────────────────────
    if inject_anomaly == 'UNFAMILIAR':
        unfam_pts, t_after, battery = gen_unfamiliar(patient, dt(15, 30), battery)
        pts.extend(unfam_pts)
    elif inject_anomaly == 'AIMLESS':
        aimless_pts, t_after, battery = gen_aimless(patient, dt(16), battery)
        pts.extend(aimless_pts)

    # ── Evening: home ───────────────────────────────────────────────────────
    eve_start = max(t_after, dt(19))
    eve_min = max(0, int((dt(23, 59) - eve_start).total_seconds() / 60))
    eve_pts, battery = gen_stationary(patient, *HOME, eve_start, eve_min, battery)
    pts.extend(eve_pts)

    # Recharge overnight
    battery = min(100, battery + random.randint(20, 40))

    return pts, battery


# ── Command ────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Generate synthetic GPS data for a patient'

    def add_arguments(self, parser):
        parser.add_argument('patient_id', type=int)
        parser.add_argument('--days', type=int, default=14)

    def handle(self, *args, **options):
        patient_id = options['patient_id']
        days = options['days']

        try:
            patient = User.objects.get(pk=patient_id, role='patient')
        except User.DoesNotExist:
            raise CommandError(f'No patient with id={patient_id}')

        self.stdout.write(f'Generating {days}-day trace for {patient.username}...')

        # Delete existing data for clean regeneration
        deleted, _ = LocationPoint.objects.filter(patient=patient).delete()
        if deleted:
            self.stdout.write(f'  Cleared {deleted} existing points.')

        # Plan anomaly injection — ensure all 4 types appear at least twice
        anomaly_types = ['WANDERING', 'DEVIATION', 'UNFAMILIAR', 'AIMLESS'] * 2
        random.shuffle(anomaly_types)

        # Scatter anomalies — roughly 8% of days get one, minimum 8 anomaly days
        anomaly_days = set(random.sample(range(days), min(days, max(8, int(days * 0.08 * 3)))))
        day_anomaly_map = {}
        for i, day_idx in enumerate(sorted(anomaly_days)):
            day_anomaly_map[day_idx] = anomaly_types[i % len(anomaly_types)]

        all_points = []
        battery = 85
        start_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=days)

        for day_idx in range(days):
            date = (start_date + timedelta(days=day_idx)).date()
            weekday = (start_date + timedelta(days=day_idx)).weekday()
            inject = day_anomaly_map.get(day_idx)
            day_pts, battery = generate_day(patient, date, battery, weekday, inject)
            all_points.extend(day_pts)

            if inject:
                self.stdout.write(f'  Day {day_idx + 1:2d} ({date}) — {inject} anomaly injected')

        # Bulk insert
        LocationPoint.objects.bulk_create(all_points, batch_size=500)

        total = LocationPoint.objects.filter(patient=patient).count()
        anomalies = LocationPoint.objects.filter(patient=patient, is_anomaly=True).count()
        types = (
            LocationPoint.objects
            .filter(patient=patient, is_anomaly=True)
            .values_list('anomaly_type', flat=True)
            .distinct()
        )

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {total:,} points generated, {anomalies:,} anomalies '
            f'({anomalies / total * 100:.1f}%)\n'
            f'Anomaly types present: {", ".join(sorted(types))}'
        ))
