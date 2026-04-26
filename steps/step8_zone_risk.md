# Step 8 — OSM Zone Risk Classification

## What was built
`get_zone_risk(lat, lng)` → float [0.0–1.0] based on nearby OpenStreetMap POIs.
Results cached in `ZoneRiskCache` by 100m grid cell.

## Risk tiers
| Score | POI types |
|-------|-----------|
| 0.95 | nightclub, bar, cliff, riverbank |
| 0.80 | highway, railway, construction, industrial, water |
| 0.30 | shop, restaurant, bus_station, residential |
| 0.10 | hospital, pharmacy, school, place_of_worship, park |
| 0.40 | default (unknown area) |
| 0.50 | fallback on Overpass API timeout/error |

## Key file
- `ml_pipeline/zone_risk.py` — get_zone_risk(), Overpass query, cache logic
- `ml_pipeline/migrations/0003_zoneriskcache.py`

## Verification checklist
- [ ] `get_zone_risk(41.2995, 69.2401)` returns value in [0, 1]
- [ ] Second call to same coords → cache hit (no HTTP request)
- [ ] Kill network → returns 0.5 gracefully
- [ ] Park/hospital area → score < 0.3
- [ ] Highway area → score > 0.6
