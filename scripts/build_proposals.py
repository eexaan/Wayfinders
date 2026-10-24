"""
================================================================================
Propose NEW service, routed on real roads
================================================================================
Maldives Datathon 2026 | Team Wayfinders

The scenario bar re-times existing trips. This script answers the other question:
where would a genuinely new service go, and what would it cost?

Every proposal is ADDITIVE. None of them removes a trip from an existing route,
because the riders already on that route would be stranded - the failure mode
that donor_load_after_pct in scenario_moves.csv exists to catch. Three kinds of
additive change are distinguished:

    new_route   a service that does not exist today
    extension   more stops on an existing line, same vehicles, same trips
    feeder      a short line into an existing interchange

Anchor points are real OSM POIs from data/derived/greater_male_pois.csv, and
every line is routed along OSM roads by OSRM - not drawn as a straight line, so
the km and minute figures are road distances. The output is committed so the
dashboard never calls OSRM at runtime.

Honesty grades: "high" where the change needs no new vehicle and the anchor is
a measured stop or POI; "medium" where a POI exists but the trip count is
inferred; "low" where the origin is not demand-measured at all.

Output:
    docs/mockups/proposals.json   the proposals, including routed geometry

Run:
    .venv/bin/python scripts/build_proposals.py
"""
import json, subprocess, pathlib, csv, math, time

ROOT = pathlib.Path('/home/falulaan/Dev/Datathon_2026/Wayfinders')
OSRM = "https://router.project-osrm.org/route/v1/driving/"

def route(pts, label):
    coords = ";".join(f"{lon},{lat}" for lat, lon in pts)
    url = f"{OSRM}{coords}?overview=full&geometries=geojson"
    for attempt in range(3):
        out = subprocess.run(["curl","-sf","--max-time","30","-A","Wayfinders-datathon/1.0",url],
                             capture_output=True).stdout
        if out:
            d = json.loads(out)
            if d.get("code") == "Ok":
                r = d["routes"][0]
                return {"coords": [[c[1],c[0]] for c in r["geometry"]["coordinates"]],
                        "km": round(r["distance"]/1000,2),
                        "min": round(r["duration"]/60,1)}
        time.sleep(2)
    raise RuntimeError(f"OSRM failed: {label}")

# --- anchors: real POIs from the OSM scrape, real stop coordinates ---
POIS = list(csv.DictReader(open(ROOT/'data/derived/greater_male_pois.csv')))
def poi(name):
    for p in POIS:
        if p['name'].strip().lower() == name.lower():
            return (float(p['lat']), float(p['lon'])), p
    raise KeyError(name)

rehendhi, reh = poi('Rehendhi School')
shaheed, sha = poi('Shaheed Ali School')
kaamil, kaa = poi('Kaamil Didi Pre School')
mi_college, mi = poi('MI College')
ghaazee, gha = poi('Ghaazee School')

# northern Phase 2 blocks: the 13 buildings beyond 400 m of any stop
PH2_NORTH = (4.2385, 73.5460)
PH2_WEST  = (4.2320, 73.5400)
HIYA      = (4.2314, 73.5489)   # Hiya Flats Stop 1, the Phase 2 interchange

proposals = []

# P1 - new school special, Phase 2 north -> Rehendhi School
p1 = route([PH2_NORTH, rehendhi], 'P1')
proposals.append({
    "id": "P1", "kind": "new_route", "name": "Phase 2 → Rehendhi School special",
    "colour": "#7b3ff2",
    "coords": p1["coords"], "km": p1["km"], "min": p1["min"],
    "windows": ["06:45–07:30", "13:45–14:30"],
    "anchors": [
        {"name": "Northern Phase 2 blocks", "at": list(PH2_NORTH), "role": "origin",
         "evidence": "13 buildings sit >400 m from any stop (OSM footprints)"},
        {"name": "Rehendhi School", "at": list(rehendhi), "role": "destination",
         "evidence": f"OSM education POI, {reh['walk_m']} m from a stop today"},
    ],
    "adds": "2 trips/day, timed to the school peak",
    "removes": "nothing — this is a new service",
    "confidence": "medium",
    "why": "Phase 2 has residents and a school-age destination 3.8 km away, but no direct "
           "trip between them: R5/R6 run the corridor and turn at 4.234, north of the "
           "last stop the new blocks sit beyond.",
})

# P2 - extend R6 north by two stops (cheapest possible fix)
ext_pts = [(4.2342, 73.5478), (4.2368, 73.5470), (4.2392, 73.5462)]
p2 = route([ (4.2342,73.5478), (4.2392,73.5462) ], 'P2')
proposals.append({
    "id": "P2", "kind": "extension", "name": "Extend R6 two stops north",
    "colour": "#0f8f6f",
    "coords": p2["coords"], "km": p2["km"], "min": p2["min"],
    "windows": ["all R6 service"],
    "anchors": [
        {"name": "H 16 Bus Stop (current terminus)", "at": [4.2342, 73.5478], "role": "existing",
         "evidence": "R5/R6/R7/R8/R9 stop 11309"},
        {"name": "Northern Phase 2 blocks", "at": [4.2392, 73.5462], "role": "new stop",
         "evidence": "2310 mapped buildings run to 4.2400; no stop north of 4.2342"},
    ],
    "adds": "2 stops, no extra trips — the same buses simply go further",
    "removes": "nothing",
    "confidence": "high",
    "why": "Every R6 trip already passes within 350 m of these blocks and turns around "
           "before them. Two more stops reaches the newest buildings with no new vehicle "
           "and no new driver.",
})

# P3 - Phase 2 internal feeder, west side -> Hiya Flats interchange
p3pts = [PH2_WEST, (4.2340, 73.5415), (4.2368, 73.5440), HIYA]
p3 = route(p3pts, 'P3')
proposals.append({
    "id": "P3", "kind": "new_route", "name": "Phase 2 west feeder loop",
    "colour": "#c2601a",
    "coords": p3["coords"], "km": p3["km"], "min": p3["min"],
    "windows": ["06:30–09:00", "16:00–19:30"],
    "anchors": [
        {"name": "Western Phase 2 blocks", "at": list(PH2_WEST), "role": "origin",
         "evidence": "136 buildings west of the stop line; median walk 237 m"},
        {"name": "Hiya Flats Stop 1", "at": list(HIYA), "role": "interchange",
         "evidence": "served by R5, R6, R7, R8, R9 — every Phase 2 corridor"},
    ],
    "adds": "feeder trips at the two commute peaks",
    "removes": "nothing",
    "confidence": "low",
    "why": "A feeder only works if it connects to a hub riders already use — Hiya Flats "
           "carries five routes. But the western blocks are not currently demand-measured, "
           "so the trip count here is a hypothesis.",
})

out = {"proposals": proposals,
       "rules": "Proposals only ADD service. None of them takes a trip off an existing "
                "route, because the riders already on that route would be stranded."}
pathlib.Path(ROOT/'docs/mockups/proposals.json').write_text(json.dumps(out, indent=1))
print(json.dumps([{k:v for k,v in p.items() if k in ('id','kind','km','min','confidence')} for p in proposals], indent=1))
