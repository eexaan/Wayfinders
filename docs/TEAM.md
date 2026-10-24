# Team: ownership and cross-check

Four people. This page says who owns what, what each person owes the report,
and how to check any number for yourself in under a minute.

---

## 1. Ownership

| Member | Role | Owns | Does **not** touch |
|---|---|---|---|
| **Raaish** | Data owner + validation | `data/`, `dashboard/build/build_data.py`, `dashboard/data/`, validation results | UI code, the report text |
| **Dev B** | Modelling | `build_data.py` demand/scenario functions, `docs/adr/` proposals for model changes | UI code, `data/` sources |
| **Dev C** | UI | `dashboard/index.html`, `app.js`, `styles.css` | anything in `dashboard/data/` |
| **Member 4** | Report | `docs/report/`, the deck, the dataset register prose | source data, model code |

**Rule:** one owner per file. If you need a change in someone else's area,
request it; do not edit it. That is how four people on one day avoid writing
over each other.

---

## 2. What each person owes the report

Member 4 cannot reconstruct the reasoning from the repo in the time available.
These are the hand-offs, and they are a hard dependency, not a courtesy.

| From | Deliverable | By |
|---|---|---|
| **Raaish** | The headline-numbers sheet (§3 below), the limitations list, `DATA_SOURCES.md` verified against the repo | 18:00 |
| **Raaish** | Confirmation that `dashboard/data/` is frozen | 12:30 |
| **Dev B** | Validation table: holdout MAPE + the three-way airport reconciliation | 18:00 |
| **Dev B** | Segment load factor, or an explicit "not available" | 16:00 |
| **Dev C** | 3–4 screenshots of the finished dashboard (map, route panel, a scenario, the method drawer) | 20:00 |
| **All** | One paragraph each on what you did and what you would do next | 19:00 |

**Rule:** member 4 writes from these numbers, not from a re-derivation. If they
recompute something and disagree, that is a bug to chase — not a competing
figure in the deck.

---

## 3. Canonical numbers — the sheet to quote from

If you are about to type a number into a slide, it must appear here. Everything
else is derived.

| # | Statement | Value | Verify with |
|---|---|---|---|
| 1 | R1 load factor on **seats** | **104.4%** | §4 command A |
| 2 | R1 load factor on seats + standing | 89.5% | §4 command A |
| 3 | R4 load factor on seats | 48.5% | §4 command A |
| 4 | R3 airport bus headway | **60 min** (hourly, all captured hours) | §4 command B |
| 5 | Expected wait on R3 | 30 min | 60 ÷ 2 |
| 6 | R1 end-to-end scheduled run | **70 min** | §4 command C |
| 7 | Share of that run on the two causeway crossings | **40 min = 57%** | §4 command C |
| 8 | Same corridor by taxi (median) | 12.7 min | `taxi_od_by_hour.csv` |
| 9 | Bus fare vs taxi fare, Malé↔HM Ph1 | 10 vs 85 MVR (8.5×) | `routes_master.csv`, `scenario_modal_shift.csv` |
| 10 | Taxi riders who would switch on price alone | 62–76% | `scenario_modal_shift.csv` |
| 11 | Taxi riders who would switch on generalised cost | 0.05–9.3% | `scenario_modal_shift.csv` |
| 12 | Ride minutes the bus must shed, Malé↔HM Ph1 | **54.4** | `scenario_modal_shift.csv` |
| 13 | Friday demand vs weekday | **61–64%** (all 4 routes) | §4 command D |
| 14 | International arrivals landing 07:00–09:59 | **35.5%** | `airport_demand_profile.csv` |
| 15 | MACL coverage of international arrivals | ≤ 36.5% | `airport_demand_profile.csv` |
| 16 | Malé airport arrivals per day, 2025 | 3,987 domestic + 7,395 international | `airport_demand_profile.csv` |
| 17 | Captured service window | ~11:00–24:00, one Saturday | `routes_master.csv` |
| 18 | Routes with any ridership data | **5 of 15** (R1, R2, R3, R4, R7) | `route_load.csv` |
| 19 | Baseline unmet demand, captured window | 8.62% | §4 command E |
| 20 | S5 effect | −236 boardings over capacity, 6.23% unmet | §4 command E |

### Numbers that are **withdrawn** — do not use

| Do not say | Why |
|---|---|
| "Friday service falls only 9–22%" | Rest on the withdrawn Ramadan PDFs. ADR-0009 |
| "R2 runs 91% of weekday service on a Friday" | Same. Withdrawn |
| "R1 at 102% of capacity" | Wrong pairing: weekday demand against a Saturday trip count |
| "1,715 boardings over capacity" | Pre-capacity-correction figure |
| "371 trips/day" | Pre-capacity-correction figure |
| "613 bus stops" | Now 184 route-stop records, 97 unique stops |
| "MACL shows domestic flights" | It contains none. ADR-0006 |

---

## 4. Verify any number in under a minute

```bash
cd ~/Documents/dev/wayfinders

# A - load factors (the headline)
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/route_load.csv')
print(d[['route_code','seated_capacity','max_passengers',
         'load_factor_seats_upper_pct',
         'load_factor_capacity_upper_pct']].to_string(index=False))"

# B - service frequency
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/route_service_by_hour.csv')
print(d[d.route_code.isin(['R3','R4'])].pivot(
      index='hour',columns='route_code',values='departures').to_string())"

# C - the causeway
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/bridge_segment_analysis.csv')
r=d[d.route_code=='R1']
print('end-to-end', r.median_end_to_end_minutes.max())
print(r[r.median_segment_minutes>=10][['from_stop','to_stop',
      'median_segment_minutes']].to_string(index=False))"

# D - Friday demand
python -c "
import pandas as pd
d=pd.read_csv('dashboard/data/demand_by_daytype.csv')
print(d.pivot(index='route_code',columns='day_type',
      values='boardings_per_day').to_string())"

# E - scenarios
python -c "
import pandas as pd
print(pd.read_csv('dashboard/data/scenario_kpis.csv').to_string(index=False))"
```

### Rebuild everything from source

```bash
python dashboard/build/build_data.py
python dashboard/build/build_figures.py
git diff --stat dashboard/data docs/figures   # should be empty if nothing changed
```

That last line is the real cross-check: **a clean rebuild must produce no diff.**
If it does, something is being edited by hand and will drift.

---

## 5. Reviewing a change

Before approving anyone's change, check:

1. **Does it cite an ADR?** A change to the model or the data contract needs one,
   new or existing (see `docs/adr/README.md`).
2. **Does it regenerate cleanly?** `build_data.py` then a clean `git diff`.
3. **Does it break a canonical number?** Run §4 and compare with §3.
4. **Does it touch the frontend contract?** If it renames a column in
   `dashboard/data/`, `docs/DASHBOARD_SPEC.md` must change in the same commit,
   and Dev C must be told before it lands.
5. **Does it reintroduce a withdrawn claim?** See the table in §3.

---

## 6. The three things that will go wrong

Ranked by how much damage they do.

1. **Someone quotes a withdrawn number.** The Friday finding and the 102%
   load factor are the two that keep coming back, because they were in early
   drafts and they sound better than the corrected ones. §3 has the list.
2. **The UI shows uncaptured hours as zero.** It looks like a finished chart
   and asserts that Malé has no morning buses. `DASHBOARD_SPEC.md` §2.16 trap 1.
3. **`dashboard/data/` gets hand-edited.** Then the numbers and the slides
   diverge and nobody notices until the judges ask. The clean-rebuild-no-diff
   check in §4 catches it.

---

## 7. Where everything lives

| Question | File |
|---|---|
| What are we building and why? | `SPEC.md` |
| How do I build the dashboard? | `docs/DASHBOARD_SPEC.md` |
| Why is it like this? | `docs/adr/` |
| Where did the data come from? | `DATA_SOURCES.md` |
| What did we try and reject? | `RESEARCH.md` §8 |
| What is still missing? | `SPEC.md` §11–12, `RESEARCH.md` §9 |
| Who owns what? | this file |
