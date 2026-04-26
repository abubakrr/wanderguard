"""
DBSCAN-based place learning from stay points.
Callable directly (for Celery) or via: python manage.py learn_patterns <patient_id>
"""

import math

import numpy as np
from django.contrib.gis.geos import Point
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import haversine_distances

from tracking.models import StayPoint

from .models import LearnedPlace

DBSCAN_EPS_M = 50        # metres — two stay points are "same place" if within 50m
DBSCAN_MIN_SAMPLES = 3   # need ≥3 visits to form a learned place


def learn_patterns(patient, logger=None):
    """
    Run DBSCAN on the patient's stay points to discover frequent places.
    Deletes previous LearnedPlace records before saving new ones.
    Returns list of saved LearnedPlace objects.
    """
    def log(msg):
        if logger:
            logger(msg)

    stay_points = list(StayPoint.objects.filter(patient=patient).order_by('arrival_time'))

    if len(stay_points) < DBSCAN_MIN_SAMPLES:
        log(f'  Only {len(stay_points)} stay points — not enough for DBSCAN (need {DBSCAN_MIN_SAMPLES}).')
        return []

    # Build haversine distance matrix (in metres)
    coords = np.array([(sp.centroid.y, sp.centroid.x) for sp in stay_points])
    coords_rad = np.radians(coords)
    dist_matrix = haversine_distances(coords_rad) * 6_371_000  # → metres

    db = DBSCAN(eps=DBSCAN_EPS_M, min_samples=DBSCAN_MIN_SAMPLES, metric='precomputed')
    labels = db.fit_predict(dist_matrix)

    unique_labels = set(labels) - {-1}   # -1 = noise
    log(f'  {len(stay_points)} stay points → {len(unique_labels)} clusters, '
        f'{(labels == -1).sum()} noise')

    places = []
    for cluster_id in unique_labels:
        cluster_sps = [sp for sp, lbl in zip(stay_points, labels) if lbl == cluster_id]
        places.append(_build_place(patient, cluster_sps))

    # Label the place with the highest visit count as 'home'
    if places:
        places.sort(key=lambda p: p.visit_count, reverse=True)
        places[0].label = 'home'
        for p in places[1:]:
            p.label = 'frequent' if p.visit_count >= 5 else 'occasional'

    # Persist
    LearnedPlace.objects.filter(patient=patient).delete()
    LearnedPlace.objects.bulk_create(places)
    saved = list(LearnedPlace.objects.filter(patient=patient).order_by('-visit_count'))
    log(f'  Saved {len(saved)} learned places.')
    return saved


def _build_place(patient, cluster_sps):
    lats = [sp.centroid.y for sp in cluster_sps]
    lngs = [sp.centroid.x for sp in cluster_sps]
    centroid_lat = sum(lats) / len(lats)
    centroid_lng = sum(lngs) / len(lngs)

    radius = max(
        _haversine(centroid_lat, centroid_lng, sp.centroid.y, sp.centroid.x)
        for sp in cluster_sps
    )

    arrival_hours = [sp.arrival_time.hour + sp.arrival_time.minute / 60 for sp in cluster_sps]
    departure_hours = [sp.departure_time.hour + sp.departure_time.minute / 60 for sp in cluster_sps]
    durations = [sp.duration_minutes for sp in cluster_sps]
    days_of_week = sorted(set(sp.arrival_time.weekday() for sp in cluster_sps))

    return LearnedPlace(
        patient=patient,
        centroid=Point(centroid_lng, centroid_lat, srid=4326),
        radius_meters=round(max(radius, 10), 2),
        visit_count=len(cluster_sps),
        avg_arrival_hour=round(sum(arrival_hours) / len(arrival_hours), 2),
        avg_departure_hour=round(sum(departure_hours) / len(departure_hours), 2),
        avg_duration_minutes=round(sum(durations) / len(durations), 2),
        days_of_week=days_of_week,
        label='frequent',
    )


def _haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
