"""
OSM-based zone risk classification.
get_zone_risk(lat, lng) → float [0.0 - 1.0]

Results are cached per 100m grid cell to avoid repeated Overpass API calls.
Falls back to 0.5 on timeout or API error.
"""

import requests

from .models import ZoneRiskCache

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
OVERPASS_TIMEOUT = 8          # seconds
SEARCH_RADIUS_M = 100         # POIs within 100m of the point
GRID_RESOLUTION = 0.001       # ~100m grid cell size in degrees

# Risk tiers — first match wins (ordered highest-risk first)
RISK_TIERS = [
    (0.95, ['nightclub', 'bar', 'cliff', 'riverbank']),
    (0.80, ['highway', 'railway', 'construction', 'industrial', 'water']),
    (0.30, ['shop', 'restaurant', 'bus_station', 'residential']),
    (0.10, ['hospital', 'pharmacy', 'school', 'place_of_worship', 'park']),
]
DEFAULT_RISK = 0.4   # unknown area


def get_zone_risk(lat, lng):
    """
    Return risk score [0, 1] for the given coordinates.
    Uses grid-cell cache; queries Overpass API on cache miss.
    """
    grid_lat = round(lat / GRID_RESOLUTION) * GRID_RESOLUTION
    grid_lng = round(lng / GRID_RESOLUTION) * GRID_RESOLUTION

    cached = ZoneRiskCache.objects.filter(grid_lat=grid_lat, grid_lng=grid_lng).first()
    if cached:
        return cached.risk_score

    risk, poi_data = _query_overpass(lat, lng)
    ZoneRiskCache.objects.update_or_create(
        grid_lat=grid_lat,
        grid_lng=grid_lng,
        defaults={'risk_score': risk, 'poi_data': poi_data},
    )
    return risk


def _query_overpass(lat, lng):
    """Query Overpass API for POIs around (lat, lng). Returns (risk_score, poi_data)."""
    query = f"""
    [out:json][timeout:{OVERPASS_TIMEOUT}];
    (
      node(around:{SEARCH_RADIUS_M},{lat},{lng})[amenity];
      node(around:{SEARCH_RADIUS_M},{lat},{lng})[highway];
      node(around:{SEARCH_RADIUS_M},{lat},{lng})[railway];
      node(around:{SEARCH_RADIUS_M},{lat},{lng})[leisure];
      node(around:{SEARCH_RADIUS_M},{lat},{lng})[landuse];
    );
    out tags;
    """
    try:
        resp = requests.post(OVERPASS_URL, data={'data': query}, timeout=OVERPASS_TIMEOUT + 2)
        resp.raise_for_status()
        elements = resp.json().get('elements', [])
    except Exception:
        return 0.5, {}   # graceful fallback

    poi_types = _extract_poi_types(elements)
    risk = _classify_risk(poi_types)
    return risk, {'types': list(poi_types)}


def _extract_poi_types(elements):
    types = set()
    tag_keys = ['amenity', 'highway', 'railway', 'leisure', 'landuse', 'natural']
    for el in elements:
        tags = el.get('tags', {})
        for key in tag_keys:
            if key in tags:
                types.add(tags[key].lower())
    return types


def _classify_risk(poi_types):
    for score, keywords in RISK_TIERS:
        if any(kw in poi_types for kw in keywords):
            return score
    return DEFAULT_RISK
