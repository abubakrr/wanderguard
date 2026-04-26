"""
Preprocessing pipeline: noise filter → stay-point detection → trip segmentation.
Callable directly (for Celery) or via: python manage.py preprocess <patient_id>
"""

import math

from django.contrib.gis.geos import Point

from .models import LocationPoint, StayPoint, Trip


# ── Geometry ───────────────────────────────────────────────────────────────────

def haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Step 1: Noise filter ───────────────────────────────────────────────────────

MAX_ACCURACY_M = 50
MAX_SPEED_MS = 15_000 / 3600   # 15 km/h → m/s

def filter_points(patient):
    """Return clean, time-ordered LocationPoints for this patient."""
    return list(
        LocationPoint.objects
        .filter(patient=patient, accuracy__lte=MAX_ACCURACY_M, speed__lte=MAX_SPEED_MS)
        .order_by('timestamp')
    )


# ── Step 2: Stay-point detection ───────────────────────────────────────────────

STAY_RADIUS_M = 30
STAY_MIN_MINUTES = 5

def detect_stay_points(patient, points):
    """
    Slide a window over time-ordered points.
    If a cluster stays within STAY_RADIUS_M for > STAY_MIN_MINUTES → StayPoint.
    Returns list of StayPoint (unsaved).
    """
    if not points:
        return []

    stay_points = []
    anchor = points[0]
    cluster = [points[0]]

    for pt in points[1:]:
        dist = haversine(
            anchor.point.y, anchor.point.x,
            pt.point.y, pt.point.x,
        )
        if dist <= STAY_RADIUS_M:
            cluster.append(pt)
        else:
            span = (cluster[-1].timestamp - cluster[0].timestamp).total_seconds() / 60
            if span >= STAY_MIN_MINUTES:
                stay_points.append(_make_stay_point(patient, cluster))
            anchor = pt
            cluster = [pt]

    # flush last cluster
    if len(cluster) > 1:
        span = (cluster[-1].timestamp - cluster[0].timestamp).total_seconds() / 60
        if span >= STAY_MIN_MINUTES:
            stay_points.append(_make_stay_point(patient, cluster))

    return stay_points


def _make_stay_point(patient, cluster):
    lats = [p.point.y for p in cluster]
    lngs = [p.point.x for p in cluster]
    centroid_lat = sum(lats) / len(lats)
    centroid_lng = sum(lngs) / len(lngs)

    # radius = max distance from centroid to any cluster point
    radius = max(
        haversine(centroid_lat, centroid_lng, p.point.y, p.point.x)
        for p in cluster
    )
    span_min = (cluster[-1].timestamp - cluster[0].timestamp).total_seconds() / 60

    return StayPoint(
        patient=patient,
        centroid=Point(centroid_lng, centroid_lat, srid=4326),
        radius_meters=round(radius, 2),
        arrival_time=cluster[0].timestamp,
        departure_time=cluster[-1].timestamp,
        duration_minutes=round(span_min, 2),
        point_count=len(cluster),
    )


# ── Step 3: Trip segmentation ──────────────────────────────────────────────────

def segment_trips(patient, points, stay_points):
    """
    Extract movement segments between consecutive stay points.
    Returns list of Trip (unsaved).
    """
    if len(stay_points) < 2:
        return []

    trips = []
    for i in range(len(stay_points) - 1):
        sp_from = stay_points[i]
        sp_to = stay_points[i + 1]

        # Points between departure of sp_from and arrival of sp_to
        seg = [
            p for p in points
            if sp_from.departure_time <= p.timestamp <= sp_to.arrival_time
        ]
        if len(seg) < 2:
            continue

        path_dist = sum(
            haversine(seg[j].point.y, seg[j].point.x,
                      seg[j + 1].point.y, seg[j + 1].point.x)
            for j in range(len(seg) - 1)
        )
        displacement = haversine(
            seg[0].point.y, seg[0].point.x,
            seg[-1].point.y, seg[-1].point.x,
        )
        duration_s = (seg[-1].timestamp - seg[0].timestamp).total_seconds()
        avg_speed = path_dist / duration_s if duration_s > 0 else 0
        ratio = path_dist / displacement if displacement > 1 else 1.0

        trips.append(Trip(
            patient=patient,
            start_point=Point(seg[0].point.x, seg[0].point.y, srid=4326),
            end_point=Point(seg[-1].point.x, seg[-1].point.y, srid=4326),
            start_time=seg[0].timestamp,
            end_time=seg[-1].timestamp,
            distance_meters=round(path_dist, 2),
            avg_speed=round(avg_speed, 4),
            point_count=len(seg),
            path_to_displacement_ratio=round(ratio, 4),
        ))

    return trips


# ── Public entry point ─────────────────────────────────────────────────────────

def run_preprocessing(patient, logger=None):
    """
    Full pipeline: filter → stay points → trips.
    Deletes previous results for this patient before saving new ones.
    Returns dict with counts.
    """
    def log(msg):
        if logger:
            logger(msg)

    log('  [1/3] Filtering noise...')
    points = filter_points(patient)
    log(f'        {len(points)} clean points')

    log('  [2/3] Detecting stay points...')
    stay_points = detect_stay_points(patient, points)
    log(f'        {len(stay_points)} stay points')

    log('  [3/3] Segmenting trips...')
    trips = segment_trips(patient, points, stay_points)
    log(f'        {len(trips)} trips')

    # Persist — clear old results first
    StayPoint.objects.filter(patient=patient).delete()
    Trip.objects.filter(patient=patient).delete()

    StayPoint.objects.bulk_create(stay_points, batch_size=200)

    # Re-fetch saved stay points (need PKs for FK references if needed later)
    saved_stay = list(StayPoint.objects.filter(patient=patient).order_by('arrival_time'))
    Trip.objects.bulk_create(trips, batch_size=200)

    return {
        'clean_points': len(points),
        'stay_points': len(saved_stay),
        'trips': len(trips),
    }
