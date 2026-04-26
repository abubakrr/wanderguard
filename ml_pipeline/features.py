"""
Feature engineering: compute_features(patient, point) → dict of 12 floats.
Also supports batch mode over a queryset for model training.

Feature groups:
  Spatial  (5): distance_from_home, distance_to_nearest_learned,
                is_inside_learned_place, distance_from_usual_route,
                displacement_from_last_staypoint
  Temporal (3): hour_sin, hour_cos, time_deviation_from_expected
  Behavioral(3): speed, heading_change_rate, path_displacement_ratio
  Context  (1): minutes_since_left_home
"""

import math

import numpy as np

from tracking.models import LocationPoint, StayPoint, Trip
from .models import LearnedPlace

FEATURE_NAMES = [
    'distance_from_home',
    'distance_to_nearest_learned',
    'is_inside_learned_place',
    'distance_from_usual_route',
    'displacement_from_last_staypoint',
    'hour_sin',
    'hour_cos',
    'time_deviation_from_expected',
    'speed',
    'heading_change_rate',
    'path_displacement_ratio',
    'minutes_since_left_home',
]


# ── Geometry ───────────────────────────────────────────────────────────────────

def _haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Cache helpers (per-patient, refreshed each batch) ─────────────────────────

class PatientContext:
    """Preloads DB state for a patient to avoid N+1 queries in batch mode."""

    def __init__(self, patient):
        self.patient = patient
        self.places = list(LearnedPlace.objects.filter(patient=patient))
        self.home = next((p for p in self.places if p.label == 'home'), None)
        self.stay_points = list(
            StayPoint.objects.filter(patient=patient).order_by('arrival_time')
        )
        self.trips = list(
            Trip.objects.filter(patient=patient).order_by('start_time')
        )

    @property
    def home_lat(self):
        return self.home.centroid.y if self.home else None

    @property
    def home_lng(self):
        return self.home.centroid.x if self.home else None


# ── Individual feature computations ───────────────────────────────────────────

def _distance_from_home(lat, lng, ctx):
    if ctx.home is None:
        return 0.0
    return _haversine(lat, lng, ctx.home_lat, ctx.home_lng)


def _distance_to_nearest_learned(lat, lng, ctx):
    if not ctx.places:
        return 0.0
    return min(
        _haversine(lat, lng, p.centroid.y, p.centroid.x)
        for p in ctx.places
    )


def _is_inside_learned_place(lat, lng, ctx):
    for place in ctx.places:
        if _haversine(lat, lng, place.centroid.y, place.centroid.x) <= place.radius_meters:
            return 1.0
    return 0.0


def _distance_from_usual_route(lat, lng, ctx):
    """
    Min distance from the point to any trip path midpoint.
    Approximation: use trip start/end midpoints as route proxies.
    Returns 0 if no trips exist.
    """
    if not ctx.trips:
        return 0.0
    min_dist = float('inf')
    for trip in ctx.trips:
        mid_lat = (trip.start_point.y + trip.end_point.y) / 2
        mid_lng = (trip.start_point.x + trip.end_point.x) / 2
        d = _haversine(lat, lng, mid_lat, mid_lng)
        if d < min_dist:
            min_dist = d
    return min_dist


def _displacement_from_last_staypoint(lat, lng, ts, ctx):
    """Distance from the most recent stay point that ended before this timestamp."""
    past = [sp for sp in ctx.stay_points if sp.departure_time <= ts]
    if not past:
        return 0.0
    last_sp = past[-1]
    return _haversine(lat, lng, last_sp.centroid.y, last_sp.centroid.x)


def _hour_features(ts):
    hour = ts.hour + ts.minute / 60
    angle = 2 * math.pi * hour / 24
    return math.sin(angle), math.cos(angle)


def _time_deviation_from_expected(lat, lng, ts, ctx):
    """
    How many hours off is this visit from the usual arrival time at the
    nearest learned place? Returns 0 if inside a learned place on schedule.
    """
    if not ctx.places:
        return 0.0
    nearest = min(ctx.places,
                  key=lambda p: _haversine(lat, lng, p.centroid.y, p.centroid.x))
    dist = _haversine(lat, lng, nearest.centroid.y, nearest.centroid.x)
    if dist > nearest.radius_meters * 3:
        return 12.0   # far from any known place → max deviation
    current_hour = ts.hour + ts.minute / 60
    diff = abs(current_hour - nearest.avg_arrival_hour)
    return min(diff, 24 - diff)   # circular difference


def _heading_change_rate(point, ctx):
    """
    Average heading change rate (degrees/min) over the last 3 points.
    Proxy for how erratic the movement is.
    """
    recent = (
        LocationPoint.objects
        .filter(patient=ctx.patient, timestamp__lt=point.timestamp)
        .order_by('-timestamp')[:3]
    )
    recent = list(recent)
    if len(recent) < 2:
        return 0.0
    total_change = 0.0
    total_time = 0.0
    for i in range(len(recent) - 1):
        dh = abs(recent[i].heading - recent[i + 1].heading)
        dh = min(dh, 360 - dh)
        dt_min = abs((recent[i].timestamp - recent[i + 1].timestamp).total_seconds()) / 60
        total_change += dh
        total_time += dt_min
    return total_change / total_time if total_time > 0 else 0.0


def _path_displacement_ratio(point, ctx):
    """
    path_to_displacement_ratio of the most recent trip that contains this point.
    Falls back to 1.0 if no matching trip.
    """
    matching = [
        t for t in ctx.trips
        if t.start_time <= point.timestamp <= t.end_time
    ]
    if not matching:
        return 1.0
    return matching[-1].path_to_displacement_ratio


def _minutes_since_left_home(ts, ctx):
    """Minutes since the patient last departed the home stay point."""
    if ctx.home is None:
        return 0.0
    home_departures = [
        sp.departure_time for sp in ctx.stay_points
        if sp.departure_time <= ts
        and _haversine(sp.centroid.y, sp.centroid.x,
                       ctx.home_lat, ctx.home_lng) <= ctx.home.radius_meters * 2
    ]
    if not home_departures:
        return 0.0
    last_departure = max(home_departures)
    return (ts - last_departure).total_seconds() / 60


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_features(patient, point, ctx=None):
    """
    Compute all 12 features for a single LocationPoint.
    Pass a PatientContext to avoid re-fetching DB in batch mode.
    Returns dict with FEATURE_NAMES keys, all floats.
    """
    if ctx is None:
        ctx = PatientContext(patient)

    lat = point.point.y
    lng = point.point.x
    ts = point.timestamp

    h_sin, h_cos = _hour_features(ts)

    features = {
        'distance_from_home':               _distance_from_home(lat, lng, ctx),
        'distance_to_nearest_learned':      _distance_to_nearest_learned(lat, lng, ctx),
        'is_inside_learned_place':          _is_inside_learned_place(lat, lng, ctx),
        'distance_from_usual_route':        _distance_from_usual_route(lat, lng, ctx),
        'displacement_from_last_staypoint': _displacement_from_last_staypoint(lat, lng, ts, ctx),
        'hour_sin':                         h_sin,
        'hour_cos':                         h_cos,
        'time_deviation_from_expected':     _time_deviation_from_expected(lat, lng, ts, ctx),
        'speed':                            float(point.speed),
        'heading_change_rate':              _heading_change_rate(point, ctx),
        'path_displacement_ratio':          _path_displacement_ratio(point, ctx),
        'minutes_since_left_home':          _minutes_since_left_home(ts, ctx),
    }

    # Guarantee no NaN / None
    return {k: float(v) if v is not None else 0.0 for k, v in features.items()}


def compute_features_batch(patient, points=None):
    """
    Compute features for all (or given) LocationPoints of a patient.
    Returns (numpy array shape [N, 12], list of LocationPoint).
    Uses a single PatientContext to minimise DB queries.
    """
    ctx = PatientContext(patient)
    if points is None:
        points = list(
            LocationPoint.objects
            .filter(patient=patient)
            .order_by('timestamp')
        )
    rows = []
    for pt in points:
        f = compute_features(patient, pt, ctx=ctx)
        rows.append([f[name] for name in FEATURE_NAMES])

    X = np.array(rows, dtype=np.float64)
    return X, points
