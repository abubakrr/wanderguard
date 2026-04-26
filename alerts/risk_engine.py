"""
Dynamic risk score engine.
compute_risk_score(patient, point) → RiskScore

Formula:
  combined = 0.40 * anomaly_score
           + 0.20 * zone_risk
           + 0.20 * time_factor
           + 0.20 * distance_factor

Levels: safe (<0.3), caution (0.3-0.6), warning (0.6-0.8), critical (>0.8)
"""

import math

from django.contrib.gis.geos import Point

from accounts.models import PatientProfile
from ml_pipeline.training import score_point
from ml_pipeline.zone_risk import get_zone_risk

from .models import Alert, RiskScore

WEIGHTS = {'anomaly': 0.40, 'zone': 0.20, 'time': 0.20, 'distance': 0.20}

LEVEL_THRESHOLDS = [
    (0.8, 'critical'),
    (0.6, 'warning'),
    (0.3, 'caution'),
    (0.0, 'safe'),
]

ALERT_THRESHOLD = 'warning'   # create Alert for warning and critical


def compute_risk_score(patient, point, model_dict=None):
    """
    Score a LocationPoint and persist a RiskScore.
    Creates an Alert if risk_level >= ALERT_THRESHOLD.
    Returns the saved RiskScore instance.
    """
    anomaly_score = score_point(patient, point, model_dict=model_dict)
    zone_risk = get_zone_risk(point.point.y, point.point.x)
    time_factor = _time_factor(point.timestamp)
    distance_factor = _distance_factor(patient, point)

    combined = (
        WEIGHTS['anomaly'] * anomaly_score +
        WEIGHTS['zone'] * zone_risk +
        WEIGHTS['time'] * time_factor +
        WEIGHTS['distance'] * distance_factor
    )
    combined = round(float(min(max(combined, 0.0), 1.0)), 4)
    level = _level(combined)

    risk = RiskScore.objects.create(
        patient=patient,
        location=point,
        anomaly_score=round(anomaly_score, 4),
        zone_risk=round(zone_risk, 4),
        time_factor=round(time_factor, 4),
        distance_factor=round(distance_factor, 4),
        combined_score=combined,
        risk_level=level,
        timestamp=point.timestamp,
    )

    if _should_alert(level):
        _create_alert(patient, point, risk)

    return risk


# ── Factor helpers ─────────────────────────────────────────────────────────────

def _time_factor(ts):
    """Night hours (22:00–06:00) are high-risk; midday is low-risk."""
    hour = ts.hour + ts.minute / 60
    # cosine peak at 2am, trough at 2pm
    angle = 2 * math.pi * (hour - 2) / 24
    return round((1 - math.cos(angle)) / 2, 4)


def _distance_factor(patient, point):
    """Normalise distance from home to [0, 1] — 2km+ → 1.0."""
    from ml_pipeline.models import LearnedPlace
    home = LearnedPlace.objects.filter(patient=patient, label='home').first()
    if home is None:
        return 0.3
    dist = _haversine(point.point.y, point.point.x, home.centroid.y, home.centroid.x)
    return round(min(dist / 2000, 1.0), 4)   # saturates at 2km


def _haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lng2 - lng1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _level(score):
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return 'safe'


def _should_alert(level):
    order = ['safe', 'caution', 'warning', 'critical']
    return order.index(level) >= order.index(ALERT_THRESHOLD)


def _create_alert(patient, point, risk):
    profile = PatientProfile.objects.filter(user=patient).select_related('caregiver').first()
    if not profile or not profile.caregiver:
        return

    alert_type = _infer_alert_type(risk)
    message = (
        f"{patient.get_full_name() or patient.username} may need attention. "
        f"Risk level: {risk.risk_level.upper()}. "
        f"Anomaly score: {risk.anomaly_score:.2f}. "
        f"Distance from home: {int(risk.distance_factor * 2000)}m."
    )

    Alert.objects.create(
        patient=patient,
        caregiver=profile.caregiver,
        risk_score=risk,
        alert_type=alert_type,
        message=message,
        location=point.point,
    )


def _infer_alert_type(risk):
    if risk.anomaly_score > 0.85 and risk.distance_factor > 0.7:
        return 'unfamiliar'
    if risk.anomaly_score > 0.85 and risk.time_factor > 0.7:
        return 'wandering'
    if risk.anomaly_score > 0.7:
        return 'deviation'
    return 'general'
