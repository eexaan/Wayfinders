/* Wayfinders Dashboard — built strictly against docs/DASHBOARD_SPEC.md */

// Embedded fallback dataset so opening index.html directly (file://) works out-of-the-box,
// while also attempting fetch('./data/*.csv') when served via python -m http.server 8000.
const FALLBACK_DATA = {
  routeLines: {
    "type": "FeatureCollection",
    "features": [
      {"type":"Feature","properties":{"route_code":"R1","route_name":"West Park to HM Phase 1","colour":"#e9222a","n_stops":18},"geometry":{"type":"LineString","coordinates":[[73.504676,4.169366],[73.510249,4.169349],[73.514746,4.17001],[73.539788,4.207528],[73.541765,4.207421],[73.542596,4.209958],[73.543088,4.211553],[73.543635,4.213077],[73.54459,4.216186],[73.545734,4.219882],[73.542702,4.219455],[73.542108,4.21678],[73.540352,4.21442],[73.539804,4.210681],[73.539788,4.207528],[73.514446,4.169881],[73.509328,4.169257],[73.504676,4.169366]]}},
      {"type":"Feature","properties":{"route_code":"R2","route_name":"Carnival to HM Phase 1","colour":"#1c54a3","n_stops":11},"geometry":{"type":"LineString","coordinates":[[73.517896,4.176984],[73.517814,4.172973],[73.541829,4.210903],[73.543635,4.213077],[73.542565,4.21635],[73.541345,4.220615],[73.540352,4.21442],[73.539804,4.210681],[73.539788,4.207528],[73.516718,4.172344],[73.518064,4.17513]]}},
      {"type":"Feature","properties":{"route_code":"R3","route_name":"West Park to VIA","colour":"#0e9247","n_stops":9},"geometry":{"type":"LineString","coordinates":[[73.504676,4.169366],[73.510249,4.169349],[73.514746,4.17001],[73.527056,4.190044],[73.526898,4.191667],[73.526887,4.190516],[73.514446,4.169881],[73.509328,4.169257],[73.504676,4.169366]]}},
      {"type":"Feature","properties":{"route_code":"R4","route_name":"HM Phase 1 to VIA","colour":"#c8d02d","n_stops":9},"geometry":{"type":"LineString","coordinates":[[73.540352,4.21442],[73.539788,4.207528],[73.527056,4.190044],[73.526898,4.191667],[73.526887,4.190516],[73.539788,4.207528],[73.543088,4.211553],[73.542565,4.21635],[73.540352,4.21442]]}},
      {"type":"Feature","properties":{"route_code":"R5","route_name":"HM Internal","colour":"#f15a29","n_stops":15},"geometry":{"type":"LineString","coordinates":[[73.548899,4.23139],[73.547805,4.234245],[73.546356,4.231865],[73.544085,4.227847],[73.544066,4.22371],[73.541345,4.220615],[73.537853,4.216739],[73.538511,4.213758],[73.538368,4.211813],[73.536385,4.20656],[73.539788,4.207528],[73.542596,4.209958],[73.54459,4.216186],[73.545734,4.219882],[73.547014,4.224619]]}},
      {"type":"Feature","properties":{"route_code":"R6","route_name":"HM Phase 2 to HM Phase 1","colour":"#90288c","n_stops":16},"geometry":{"type":"LineString","coordinates":[[73.548899,4.23139],[73.547805,4.234245],[73.546356,4.231865],[73.544085,4.227847],[73.544066,4.22371],[73.542702,4.219455],[73.542216,4.217746],[73.540352,4.21442],[73.54048,4.211256],[73.541829,4.210903],[73.543088,4.211553],[73.543635,4.213077],[73.54459,4.216186],[73.545131,4.217841],[73.545734,4.219882],[73.547014,4.224619]]}},
      {"type":"Feature","properties":{"route_code":"R7","route_name":"HM Phase 2 to West Park","colour":"#26b473","n_stops":12},"geometry":{"type":"LineString","coordinates":[[73.546356,4.231865],[73.544085,4.227847],[73.544066,4.22371],[73.514446,4.169881],[73.509328,4.169257],[73.504676,4.169366],[73.510249,4.169349],[73.514746,4.17001],[73.543878,4.223651],[73.547014,4.224619],[73.548899,4.23139],[73.547805,4.234245]]}},
      {"type":"Feature","properties":{"route_code":"R8","route_name":"HM Phase 2 to Carnival","colour":"#b1206d","n_stops":11},"geometry":{"type":"LineString","coordinates":[[73.546356,4.231865],[73.544085,4.227847],[73.544066,4.22371],[73.516718,4.172344],[73.517817,4.174101],[73.517896,4.176984],[73.517814,4.172973],[73.543878,4.223651],[73.547014,4.224619],[73.548899,4.23139],[73.547805,4.234245]]}},
      {"type":"Feature","properties":{"route_code":"R9","route_name":"HM Phase 2 to VIA","colour":"#00adee","n_stops":10},"geometry":{"type":"LineString","coordinates":[[73.548899,4.23139],[73.547805,4.234245],[73.546356,4.231865],[73.544085,4.227847],[73.544066,4.22371],[73.527056,4.190044],[73.526898,4.191667],[73.526887,4.190516],[73.543878,4.223651],[73.547014,4.224619]]}},
      {"type":"Feature","properties":{"route_code":"R10","route_name":"Orchid","colour":"#841a4f","n_stops":13},"geometry":{"type":"LineString","coordinates":[[73.505883,4.175851],[73.507219,4.177532],[73.508454,4.178385],[73.51104,4.17892],[73.513422,4.178784],[73.515595,4.178174],[73.517896,4.176984],[73.518064,4.17513],[73.516835,4.174327],[73.514333,4.174664],[73.511412,4.174948],[73.509847,4.175205],[73.507406,4.175418]]}},
      {"type":"Feature","properties":{"route_code":"R11","route_name":"Ameenee","colour":"#00a69c","n_stops":19},"geometry":{"type":"LineString","coordinates":[[73.517863,4.17331],[73.516314,4.170695],[73.514235,4.170928],[73.512209,4.171185],[73.510187,4.17137],[73.508277,4.171568],[73.505627,4.171871],[73.504227,4.17199],[73.50206,4.172281],[73.500813,4.172781],[73.502422,4.175986],[73.503956,4.175881],[73.506684,4.175564],[73.508185,4.175373],[73.509529,4.17513],[73.511556,4.175024],[73.513774,4.17478],[73.515062,4.174643],[73.517145,4.174467]]}},
      {"type":"Feature","properties":{"route_code":"R12","route_name":"Sosun","colour":"#cb7328","n_stops":9},"geometry":{"type":"LineString","coordinates":[[73.517862,4.176728],[73.514082,4.178512],[73.51104,4.17892],[73.513278,4.17832],[73.514222,4.178033],[73.515282,4.177506],[73.514973,4.175993],[73.515062,4.174643],[73.517145,4.174467]]}},
      {"type":"Feature","properties":{"route_code":"R13","route_name":"Villimale Internal","colour":"#6465ad","n_stops":13},"geometry":{"type":"LineString","coordinates":[[73.486942,4.175107],[73.48597,4.174545],[73.485865,4.173209],[73.485594,4.17234],[73.485121,4.171731],[73.484309,4.172177],[73.484268,4.173065],[73.483706,4.173555],[73.483217,4.174031],[73.48366,4.174845],[73.484172,4.175424],[73.484502,4.176026],[73.48547,4.176059]]}},
      {"type":"Feature","properties":{"route_code":"R14","route_name":"VILLIMALE INTERNAL 2","colour":"#1fe8e3","n_stops":12},"geometry":{"type":"LineString","coordinates":[[73.486942,4.175107],[73.48547,4.176059],[73.484502,4.176026],[73.484172,4.175424],[73.484285,4.174233],[73.484268,4.173065],[73.484309,4.172177],[73.485121,4.171731],[73.485594,4.17234],[73.486062,4.172797],[73.486783,4.174216],[73.486891,4.175078]]}},
      {"type":"Feature","properties":{"route_code":"R15","route_name":"West Park to Orange Hiya","colour":"#890c15","n_stops":7},"geometry":{"type":"LineString","coordinates":[[73.504676,4.169366],[73.510249,4.169349],[73.514746,4.17001],[73.536385,4.20656],[73.514446,4.169881],[73.509328,4.169257],[73.504676,4.169366]]}}
    ]
  },
  routesMaster: [
    {route_code:"R1",route_name:"West Park to HM Phase 1",route_name_dv:"އެޗްއެމް ފޭސް 1",colour:"#e9222a",fare_mvr:10,bus_type:"Double decker",seats:84,capacity_source:"psmnews.mv/en/106008 (team-provided)",trips_per_day:61,trips_captured:40,capture_first_departure:"11:20:00",capture_last_departure:"23:30:00"},
    {route_code:"R2",route_name:"Carnival to HM Phase 1",route_name_dv:"ކާރނިވަލް - ހުޅުމާލެ ފޭސް 1",colour:"#1c54a3",fare_mvr:10,bus_type:"Double decker",seats:84,capacity_source:"psmnews.mv/en/106008 (team-provided)",trips_per_day:61,trips_captured:40,capture_first_departure:"11:20:00",capture_last_departure:"23:30:00"},
    {route_code:"R3",route_name:"West Park to VIA",route_name_dv:"ވެސްޓް ޕާރކް - އެއާޕޯޓް",colour:"#0e9247",fare_mvr:10,bus_type:"Airport bus",seats:52,capacity_source:"ASSUMED - confirm with MTCC",trips_per_day:20,trips_captured:13,capture_first_departure:"11:40:00",capture_last_departure:"23:40:00"},
    {route_code:"R4",route_name:"HM Phase 1 to VIA",route_name_dv:"ހުޅުމާލެ ފޭސް 1 - އެއާޕޯޓް",colour:"#c8d02d",fare_mvr:10,bus_type:"Airport bus",seats:52,capacity_source:"psmnews.mv/en/106008 (team-provided, 50-54)",trips_per_day:38,trips_captured:25,capture_first_departure:"11:30:00",capture_last_departure:"23:30:00"},
    {route_code:"R5",route_name:"HM Internal",route_name_dv:"އެޗްއެމް އިންޓަރނަލް",colour:"#f15a29",fare_mvr:5,bus_type:"Regular bus",seats:54,capacity_source:"ASSUMED - confirm with MTCC",trips_per_day:17,trips_captured:12,capture_first_departure:"11:15:00",capture_last_departure:"22:15:00"},
    {route_code:"R6",route_name:"HM Phase 2 to HM Phase 1",route_name_dv:"ހުޅުމާލެ ފޭސް 2 - ހިުޅުމާލެ ފޭސް 1",colour:"#90288c",fare_mvr:5,bus_type:"Double decker",seats:84,capacity_source:"psmnews.mv/en/106008 (team-provided)",trips_per_day:75,trips_captured:51,capture_first_departure:"11:15:00",capture_last_departure:"23:45:00"},
    {route_code:"R7",route_name:"HM Phase 2 to West Park",route_name_dv:"ހުޅުމާލެ ފޭސް 2 - ވެސްޓް ޕާރކް",colour:"#26b473",fare_mvr:15,bus_type:"Double decker",seats:84,capacity_source:"psmnews.mv/en/106008 (team-provided)",trips_per_day:66,trips_captured:44,capture_first_departure:"11:15:00",capture_last_departure:"23:30:00"},
    {route_code:"R8",route_name:"HM Phase 2 to Carnival",route_name_dv:"ހުޅުމާލެ ފޭސް 2 - ކާރނިވަލް",colour:"#b1206d",fare_mvr:15,bus_type:"Double decker",seats:84,capacity_source:"psmnews.mv/en/106008 (team-provided)",trips_per_day:61,trips_captured:40,capture_first_departure:"11:20:00",capture_last_departure:"23:30:00"},
    {route_code:"R9",route_name:"HM Phase 2 to VIA",route_name_dv:"ހުޅުމާލެ ފޭސް 2 - އެއާޕޯޓް",colour:"#00adee",fare_mvr:15,bus_type:"Airport bus",seats:52,capacity_source:"psmnews.mv/en/106008 (team-provided, 50-54)",trips_per_day:38,trips_captured:25,capture_first_departure:"11:30:00",capture_last_departure:"23:30:00"},
    {route_code:"R10",route_name:"Orchid",route_name_dv:"އޯރކިޑް",colour:"#841a4f",fare_mvr:7,bus_type:"Minibus",seats:21,capacity_source:"official minibus flag + psmnews (20-22)",trips_per_day:null,trips_captured:0,capture_first_departure:"",capture_last_departure:""},
    {route_code:"R11",route_name:"Ameenee",route_name_dv:"އަމީނީ",colour:"#00a69c",fare_mvr:7,bus_type:"Minibus",seats:21,capacity_source:"official minibus flag + psmnews (20-22)",trips_per_day:null,trips_captured:0,capture_first_departure:"",capture_last_departure:""},
    {route_code:"R12",route_name:"Sosun",route_name_dv:"ސޯސަން",colour:"#cb7328",fare_mvr:7,bus_type:"Minibus",seats:21,capacity_source:"official minibus flag + psmnews (20-22)",trips_per_day:null,trips_captured:0,capture_first_departure:"",capture_last_departure:""},
    {route_code:"R13",route_name:"Villimale Internal",route_name_dv:"ވިލިމާލެ އިންޓަރނަލް",colour:"#6465ad",fare_mvr:5,bus_type:"E-minibus",seats:11,capacity_source:"ASSUMED eco e-minibus - confirm",trips_per_day:92,trips_captured:63,capture_first_departure:"11:10:00",capture_last_departure:"23:50:00"},
    {route_code:"R14",route_name:"VILLIMALE INTERNAL 2",route_name_dv:"ވިލިމާލެ އިންޓާރނަލް 2",colour:"#1fe8e3",fare_mvr:5,bus_type:"E-minibus",seats:11,capacity_source:"ASSUMED eco e-minibus - confirm",trips_per_day:105,trips_captured:77,capture_first_departure:"11:10:00",capture_last_departure:"23:50:00"},
    {route_code:"R15",route_name:"West Park to Orange Hiya",route_name_dv:"ވެސްޓްޕާކް  އޮރެންޖް ހިޔާ",colour:"#890c15",fare_mvr:10,bus_type:"Minibus",seats:21,capacity_source:"official minibus flag + psmnews (20-22)",trips_per_day:null,trips_captured:0,capture_first_departure:"",capture_last_departure:""}
  ],
  routeLoad: {
    R1: { boardings_per_day: 4585, pax_per_trip: 75.2, load_factor_peak_pct: 89.5, load_factor_avg_pct: 44.7, demand_source: "MTCC observed", service_capture: "40 of 61.0 trips captured" },
    R2: { boardings_per_day: 3447, pax_per_trip: 56.5, load_factor_peak_pct: 67.3, load_factor_avg_pct: 33.6, demand_source: "MTCC observed", service_capture: "40 of 61.0 trips captured" },
    R3: { boardings_per_day: 752,  pax_per_trip: 37.6, load_factor_peak_pct: 72.3, load_factor_avg_pct: 36.1, demand_source: "MTCC observed", service_capture: "13 of 20.0 trips captured" },
    R4: { boardings_per_day: 1014, pax_per_trip: 26.7, load_factor_peak_pct: 51.3, load_factor_avg_pct: 25.6, demand_source: "MTCC observed", service_capture: "25 of 38.0 trips captured" },
    R5: { boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "12 of 17.0 trips captured" },
    R6: { boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "51 of 75.0 trips captured" },
    R7: { boardings_per_day: 3552, pax_per_trip: 53.8, load_factor_peak_pct: 64.1, load_factor_avg_pct: 32.0, demand_source: "MTCC observed", service_capture: "44 of 66.0 trips captured" },
    R8: { boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "40 of 61.0 trips captured" },
    R9: { boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "25 of 38.0 trips captured" },
    R10:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "no timings returned" },
    R11:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "no timings returned" },
    R12:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "no timings returned" },
    R13:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "63 of 92.0 trips captured" },
    R14:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "77 of 105.0 trips captured" },
    R15:{ boardings_per_day: null, pax_per_trip: null, load_factor_peak_pct: null, load_factor_avg_pct: null, demand_source: "NO DEMAND DATA", service_capture: "no timings returned" }
  },
  // Hourly demand (24h) and captured trips (hours 11..23)
  hourly: {
    R1: {
      demand: [126.5,61.6,32.8,19.8,15.8,33.5,88.5,183.4,169.7,166.8,161.7,165.2,192.7,225.9,270.8,321.9,378.6,315.1,325.5,303.2,303.5,257.0,255.4,210.1],
      trips:  [null,null,null,null,null,null,null,null,null,null,null,2,3,3,3,3,4,4,4,4,3,3,2,2],
      firstOrder: 22
    },
    R2: {
      demand: [95.1,46.3,24.7,14.9,11.8,25.2,66.6,137.9,127.6,125.4,121.5,124.2,144.9,169.8,203.6,242.0,284.7,236.9,244.7,228.0,228.2,193.3,192.0,158.0],
      trips:  [null,null,null,null,null,null,null,null,null,null,null,2,3,3,3,3,4,4,4,4,3,3,2,2],
      firstOrder: 22
    },
    R3: {
      demand: [5.9,2.1,2.9,8.2,13.8,44.5,54.6,50.2,52.0,53.7,51.1,39.9,42.0,53.4,56.1,43.1,29.3,27.3,27.5,23.7,24.4,26.7,12.5,6.8],
      trips:  [null,null,null,null,null,null,null,null,null,null,null,1,1,1,1,1,1,1,1,1,1,1,1,1],
      firstOrder: 8
    },
    R4: {
      demand: [11.2,3.6,3.8,17.9,24.2,67.9,63.1,91.5,76.1,62.3,57.4,36.3,45.1,69.7,71.4,66.6,53.8,34.4,33.1,25.8,29.6,36.9,19.3,12.8],
      trips:  [null,null,null,null,null,null,null,null,null,null,null,1,2,2,2,2,2,2,2,2,2,2,2,2],
      firstOrder: 14
    },
    R5: {
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,1,1,1,1,1,1,1,1,1,1,1,1,null],
      firstOrder: 6
    },
    R6: {
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,3,4,4,4,4,4,4,4,4,4,4,4,4],
      firstOrder: 25
    },
    R7: {
      demand: [85.8,39.0,21.4,13.4,9.8,23.2,58.0,159.1,166.6,146.6,146.7,150.9,150.9,179.5,205.3,244.2,280.2,241.5,240.5,232.2,234.6,193.8,181.9,146.9],
      trips:  [null,null,null,null,null,null,null,null,null,null,null,3,4,4,4,4,4,4,4,3,3,3,2,2],
      firstOrder: 23
    },
    R8: {
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,2,3,3,3,3,4,4,4,4,3,3,2,2],
      firstOrder: 22
    },
    R9: {
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,1,2,2,2,2,2,2,2,2,2,2,2,2],
      firstOrder: 14
    },
    R10:{ demand: Array(24).fill(null), trips: Array(24).fill(null), firstOrder: null },
    R11:{ demand: Array(24).fill(null), trips: Array(24).fill(null), firstOrder: null },
    R12:{ demand: Array(24).fill(null), trips: Array(24).fill(null), firstOrder: null },
    R13:{
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,3,null,null,6,6,6,6,6,6,6,6,6,6],
      firstOrder: 30
    },
    R14:{
      demand: Array(24).fill(null),
      trips:  [null,null,null,null,null,null,null,null,null,null,null,5,6,6,6,6,6,6,6,6,6,6,6,6],
      firstOrder: 29
    },
    R15:{ demand: Array(24).fill(null), trips: Array(24).fill(null), firstOrder: null }
  },
  dayType: {
    R1: { weekday: 5212, sat_holiday: 4585, friday: 3192 },
    R2: { weekday: 3818, sat_holiday: 3447, friday: 2427 },
    R3: { weekday: 786,  sat_holiday: 752,  friday: 669  },
    R4: { weekday: 1146, sat_holiday: 1014, friday: 722  },
    R7: { weekday: 3709, sat_holiday: 3552, friday: 3181 }
  },
  // Causeway & VIA approach segments >= 10 min from bridge_segment_analysis.csv
  causewaySegments: [
    { route_code: "R1", from: "STELCO", to: "Hulhumale' Cemetery", mins: 20, coords: [[4.17001, 73.514746], [4.207528, 73.539788]] },
    { route_code: "R1", from: "Hulhumale' Cemetery OPP", to: "Male' Swimming Track", mins: 20, coords: [[4.207528, 73.539788], [4.169881, 73.514446]] },
    { route_code: "R2", from: "Raalhugandu (Schedule Bus)", to: "Flat No. 120", mins: 20, coords: [[4.172973, 73.517814], [4.210903, 73.541829]] },
    { route_code: "R2", from: "MNDF Flat", to: "Hulhumale' Cemetery", mins: 20, coords: [[4.210681, 73.539804], [4.207528, 73.539788]] },
    { route_code: "R7", from: "MACL Flat Stop", to: "Male' Swimming Track", mins: 20, coords: [[4.22371, 73.544066], [4.169881, 73.514446]] },
    { route_code: "R8", from: "Raalhugandu (Schedule Bus)", to: "MWSC FLAT BUS STOP", mins: 15, coords: [[4.172973, 73.517814], [4.223651, 73.543878]] },
    { route_code: "R3", from: "VIA Domestic Terminal", to: "MACL Office", mins: 15, coords: [[4.17001, 73.514746], [4.190044, 73.527056]] },
    { route_code: "R4", from: "MACL Office", to: "VIA Domestic Terminal OPP", mins: 15, coords: [[4.207528, 73.539788], [4.190044, 73.527056]] }
  ],
  scenarios: {
    S0_baseline: {
      label: "S0 Baseline",
      mean_wait_min_captured: 10.9,
      boardings_over_capacity: 360,
      unmet_share_pct: 3.68,
      total_trips_captured: 162,
      demand_pax_captured: 9805,
      over_capacity_change: 0,
      wait_change_min: 0.0,
      trips_change: 0,
      taxi_capturable_day: 190.6,
      corridors: { R1: 317, R2: 24, R3: 5, R4: 0, R7: 13 }
    },
    S2_airport_retimed: {
      label: "S2 Airport re-timed",
      mean_wait_min_captured: 10.4,
      boardings_over_capacity: 355,
      unmet_share_pct: 3.63,
      total_trips_captured: 168,
      demand_pax_captured: 9786,
      over_capacity_change: -5,
      wait_change_min: -0.5,
      trips_change: 6,
      taxi_capturable_day: 190.6,
      corridors: { R1: 317, R2: 24, R3: 0, R4: 0, R7: 13 }
    },
    S3_rebalanced_to_corridor: {
      label: "S3 Rebalanced to corridor",
      mean_wait_min_captured: 10.6,
      boardings_over_capacity: 349,
      unmet_share_pct: 3.61,
      total_trips_captured: 164,
      demand_pax_captured: 9696,
      over_capacity_change: -11,
      wait_change_min: -0.3,
      trips_change: 2,
      taxi_capturable_day: 190.6,
      corridors: { R1: 274, R2: 24, R3: 0, R4: 37, R7: 13 }
    },
    S4_express_peak: {
      label: "S4 Express peak",
      mean_wait_min_captured: 10.5,
      boardings_over_capacity: 248,
      unmet_share_pct: 2.53,
      total_trips_captured: 170,
      demand_pax_captured: 9805,
      over_capacity_change: -112,
      wait_change_min: -0.4,
      trips_change: 8,
      taxi_capturable_day: 210.2,
      corridors: { R1: 204, R2: 24, R3: 5, R4: 0, R7: 13 }
    },
    S5_recommended_package: {
      label: "S5 Recommended package",
      mean_wait_min_captured: 10.0,
      boardings_over_capacity: 242,
      unmet_share_pct: 2.48,
      total_trips_captured: 176,
      demand_pax_captured: 9786,
      over_capacity_change: -118,
      wait_change_min: -0.9,
      trips_change: 14,
      taxi_capturable_day: 210.2,
      corridors: { R1: 204, R2: 24, R3: 0, R4: 0, R7: 13 }
    }
  }
};

// State
const state = {
  selectedRoute: "R1",
  selectedDayType: "sat_holiday",
  selectedScenario: "S0_baseline",
  colourMode: "load", // 'load' | 'rtl'
  showCauseway: true,
  showStops: true,
  map: null,
  routeLayerGroup: null,
  causewayLayerGroup: null,
  stopsLayerGroup: null,
  routeLayersByCode: {}
};

// Colour helper per DASHBOARD_SPEC §4 C1
function getLoadStrokeColor(routeCode) {
  const load = FALLBACK_DATA.routeLoad[routeCode];
  if (!load || load.load_factor_peak_pct === null) {
    return "#6e7772";
  }
  const peak = load.load_factor_peak_pct;
  if (peak >= 100) return "#e9222a";
  if (peak >= 60) return "#ff7f0e";
  return "#8a9992";
}

function getRouteMaster(code) {
  return FALLBACK_DATA.routesMaster.find((r) => r.route_code === code);
}

// Initialize Leaflet Map
function initMap() {
  const bounds = L.latLngBounds([4.155, 73.470], [4.248, 73.565]);
  const map = L.map("map", {
    center: [4.198, 73.523],
    zoom: 13,
    minZoom: 12,
    maxZoom: 17,
    maxBounds: bounds,
    maxBoundsViscosity: 0.9,
    attributionControl: false
  });

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18
  }).addTo(map);

  state.map = map;
  state.routeLayerGroup = L.layerGroup().addTo(map);
  state.causewayLayerGroup = L.layerGroup().addTo(map);
  state.stopsLayerGroup = L.layerGroup().addTo(map);

  drawMapLayers();
}

function drawMapLayers() {
  state.routeLayerGroup.clearLayers();
  state.causewayLayerGroup.clearLayers();
  state.stopsLayerGroup.clearLayers();
  state.routeLayersByCode = {};

  // 1. Draw 15 route polylines
  FALLBACK_DATA.routeLines.features.forEach((feat) => {
    const code = feat.properties.route_code;
    const master = getRouteMaster(code);
    const load = FALLBACK_DATA.routeLoad[code];
    const isNoData = !load || load.load_factor_peak_pct === null;
    const isSelected = code === state.selectedRoute;

    const color =
      state.colourMode === "rtl"
        ? master.colour
        : getLoadStrokeColor(code);

    const latlngs = feat.geometry.coordinates.map((c) => [c[1], c[0]]);

    const poly = L.polyline(latlngs, {
      color,
      weight: isSelected ? 5 : 2.5,
      opacity: isSelected ? 1.0 : isNoData && state.colourMode === "load" ? 0.55 : 0.82,
      dashArray: isNoData && state.colourMode === "load" ? "5,6" : null
    });

    const bandText = isNoData
      ? "NO DEMAND DATA"
      : `${load.load_factor_avg_pct}% avg – ${load.load_factor_peak_pct}% peak`;

    poly.bindTooltip(
      `<strong>${code} · ${master.route_name}</strong><br/>` +
        `<span class="dv">${master.route_name_dv}</span><br/>` +
        `${master.bus_type} · ${master.seats} seats · ${master.fare_mvr} MVR<br/>` +
        `Load band: <strong>${bandText}</strong>`,
      { className: "dark-tip", sticky: true }
    );

    poly.on("click", () => {
      selectRoute(code);
    });

    poly.addTo(state.routeLayerGroup);
    state.routeLayersByCode[code] = poly;
  });

  // Bring selected route to front
  if (state.routeLayersByCode[state.selectedRoute]) {
    state.routeLayersByCode[state.selectedRoute].bringToFront();
  }

  // 2. Highlight causeway segments >= 10 min
  if (state.showCauseway) {
    FALLBACK_DATA.causewaySegments.forEach((seg) => {
      const line = L.polyline(seg.coords, {
        color: "#e9222a",
        weight: 6,
        opacity: 0.9
      });
      line.bindTooltip(
        `<strong>Causeway / Bottleneck (${seg.mins} min)</strong><br/>` +
          `${seg.route_code}: ${seg.from} → ${seg.to}<br/>` +
          `57% of R1's 70-min journey is spent in two crossings`,
        { className: "dark-tip", sticky: true }
      );
      line.addTo(state.causewayLayerGroup);
    });
  }

  // 3. Draw unique stop markers with official English + Dhivehi names
  if (state.showStops) {
    const stopNames = {
      "4.16937,73.50468": { en: "Maafannu Bus Terminal", dv: "މާފަންނު ބަސްޓާރމިނަލް" },
      "4.16935,73.51025": { en: "Tow Yard", dv: "ޓޯޔާރޑް" },
      "4.17001,73.51475": { en: "STELCO", dv: "ސްޓެލްކޯ" },
      "4.20753,73.53979": { en: "Hulhumale' Cemetery", dv: "ހުޅުމާލެ ސަހަރާ" },
      "4.20742,73.54177": { en: "Skate Park", dv: "ސްކޭޓް ޕާރކް" },
      "4.20996,73.54260": { en: "Flat No. 137", dv: "" },
      "4.21155,73.54309": { en: "Fehires Park", dv: "ފެހިރެސް ޕާރކް" },
      "4.21308,73.54364": { en: "Flat No. 147", dv: "ފްލެޓް 147" },
      "4.21619,73.54459": { en: "Ruhgandu 1", dv: "ރުއްގަނޑު 1" },
      "4.21988,73.54573": { en: "Dhiraagu", dv: "ދިރާގު" },
      "4.21946,73.54270": { en: "Hulhumale' Synthetic Track", dv: "ހުޅުމާލެ ސިންތެޓިކް ޓްރެކް" },
      "4.21678,73.54211": { en: "Hulhumale' Police Station", dv: "ހުޅުމާލެ ޕޮލިސް ސްޓޭޝަން" },
      "4.21442,73.54035": { en: "Amin Avenue", dv: "އަމީން އެވެނިއު" },
      "4.21068,73.53980": { en: "MNDF Flat", dv: "އެމްއެންޑީއެފް ފްލެޓް" },
      "4.16988,73.51445": { en: "Male' Swimming Track", dv: "މާލެ ސްވިމިންގް ޓްރެކް" },
      "4.16926,73.50933": { en: "Dharumavantha School", dv: "ދަރުމަވަންތަ ސްކޫލް" },
      "4.17698,73.51790": { en: "Carnival", dv: "ކާރނިވަލް" },
      "4.17297,73.51781": { en: "Raalhugandu (Schedule Bus)", dv: "" },
      "4.21090,73.54183": { en: "Flat No. 120", dv: "ފްލެޓް 120" },
      "4.21635,73.54257": { en: "Centro Mall", dv: "ސެންޓްރޯމޯލް" },
      "4.22062,73.54135": { en: "CHSE", dv: "ސީއެޗްއެސްއީ" },
      "4.17234,73.51672": { en: "Senahiya", dv: "ސެނަހިޔާ" },
      "4.17513,73.51806": { en: "Artificial Beach", dv: "އާރޓިފިޝަލް ބީޗް" },
      "4.19004,73.52706": { en: "VIA Domestic Terminal", dv: "ވީއައިއޭ ޑޮމެސްޓިކް" },
      "4.19167,73.52690": { en: "MACL Office", dv: "އެމް.އޭ.ސީ.އެލް. އޮފީސް" },
      "4.19052,73.52689": { en: "VIA Domestic Terminal OPP", dv: "" },
      "4.23139,73.54890": { en: "Hiya Flats Stop 1", dv: "ހިޔާފްލެޓް ސްޓޮޕް 1" },
      "4.23425,73.54781": { en: "H 16 Bus Stop", dv: "އެޗް 16 ބަސް ސްޓޮޕް" },
      "4.23187,73.54636": { en: "Hiya Flats Stop 2", dv: "ހިޔާފްލެޓް ސްޓޮޕް 2" },
      "4.22785,73.54409": { en: "VINARES Bus Stop", dv: "" },
      "4.22371,73.54407": { en: "MACL Flat Stop", dv: "" },
      "4.22365,73.54388": { en: "MWSC Flat Bus Stop", dv: "އެމްޑަބްލިއުއެސްސީ ފްލެޓް ސްޓޮޕް" },
      "4.22462,73.54701": { en: "Masjid Ameel Jaleel", dv: "މަސްޖިިިދް އަމީލް ޖަލީލް" },
      "4.20656,73.53639": { en: "Orange Hiya Bus Stop", dv: "" },
      "4.17511,73.48694": { en: "Villimale Ferry Terminal", dv: "ވިލިމާލެ ފެރީ ޓާރމިނަލް" }
    };

    const seen = new Map();
    FALLBACK_DATA.routeLines.features.forEach((feat) => {
      const code = feat.properties.route_code;
      feat.geometry.coordinates.forEach(([lon, lat]) => {
        const key = `${lat.toFixed(5)},${lon.toFixed(5)}`;
        if (!seen.has(key)) {
          seen.set(key, { lat, lon, key, routes: new Set([code]) });
        } else {
          seen.get(key).routes.add(code);
        }
      });
    });

    seen.forEach((stop) => {
      const routesArr = Array.from(stop.routes);
      const onSelected = routesArr.includes(state.selectedRoute);
      const meta = stopNames[stop.key];
      const titleLine = meta
        ? `<strong>${meta.en}</strong>${meta.dv ? `<br/><span class="dv">${meta.dv}</span>` : ""}`
        : `<strong>Bus Stop</strong> (${stop.lat.toFixed(4)}, ${stop.lon.toFixed(4)})`;

      const marker = L.circleMarker([stop.lat, stop.lon], {
        radius: onSelected ? 4 : 2.6,
        fillColor: onSelected ? "#eae6df" : "#9da6a0",
        color: "#141817",
        weight: 1,
        fillOpacity: onSelected ? 1 : 0.75
      });
      marker.bindTooltip(
        `${titleLine}<br/>Routes: <strong>${routesArr.join(", ")}</strong>`,
        { className: "dark-tip" }
      );
      marker.on("click", () => {
        if (!routesArr.includes(state.selectedRoute)) {
          selectRoute(routesArr[0]);
        }
      });
      marker.addTo(state.stopsLayerGroup);
    });
  }
}

// Build Route Pills Strip
function renderRouteStrip() {
  const container = document.getElementById("route-strip");
  container.innerHTML = "";

  FALLBACK_DATA.routesMaster.forEach((r) => {
    const load = FALLBACK_DATA.routeLoad[r.route_code];
    const hasDemand = load && load.load_factor_peak_pct !== null;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "route-pill" +
      (hasDemand ? "" : " no-demand") +
      (r.route_code === state.selectedRoute ? " active" : "");

    const dotColor =
      state.colourMode === "rtl"
        ? r.colour
        : getLoadStrokeColor(r.route_code);

    btn.innerHTML = `<span class="dot" style="background:${dotColor}"></span>${r.route_code}`;
    btn.title = `${r.route_code}: ${r.route_name} (${hasDemand ? load.load_factor_peak_pct + "% peak" : "NO DEMAND DATA"})`;
    btn.addEventListener("click", () => selectRoute(r.route_code));
    container.appendChild(btn);
  });
}

function selectRoute(routeCode) {
  state.selectedRoute = routeCode;
  renderRouteStrip();
  drawMapLayers();
  renderRoutePanel();
}

// Render C2 Route Panel (<100ms instant update)
function renderRoutePanel() {
  const code = state.selectedRoute;
  const master = getRouteMaster(code);
  const load = FALLBACK_DATA.routeLoad[code];
  const hourly = FALLBACK_DATA.hourly[code];

  // Header
  const codeTag = document.getElementById("rp-code");
  codeTag.textContent = code;
  codeTag.style.background = master.colour;

  document.getElementById("rp-name").textContent = master.route_name;
  document.getElementById("rp-name-dv").textContent = master.route_name_dv || "";
  document.getElementById("rp-bustype").textContent = master.bus_type;
  document.getElementById("rp-seats").textContent = `${master.seats} seats`;
  document.getElementById("rp-seats-cell").title = `Capacity source: ${master.capacity_source}`;
  document.getElementById("rp-fare").textContent = `${master.fare_mvr} MVR`;

  const tripsText =
    master.trips_per_day !== null
      ? `${master.trips_per_day} (${master.trips_captured} cap.)`
      : "No timings";
  document.getElementById("rp-trips").textContent = tripsText;
  document.getElementById("rp-trips-cell").title = load.service_capture;

  // 2. Load Factor Band (Range Bar: avg -> peak, never a single number)
  const bandSource = document.getElementById("rp-demand-source");
  bandSource.textContent = load.demand_source;
  const bandContainer = document.getElementById("rp-band-container");

  if (load.load_factor_peak_pct === null) {
    bandContainer.innerHTML = `
      <div class="no-data-box">
        <strong>NO DEMAND DATA</strong> — MTCC ridership is not published for ${code}.<br/>
        Shown as unknown rather than 0%.
      </div>
    `;
  } else {
    const avg = load.load_factor_avg_pct;
    const peak = load.load_factor_peak_pct;
    const scaleMax = 115; // allow >100% visibility
    const leftPct = Math.min(100, (avg / scaleMax) * 100);
    const widthPct = Math.max(3, ((peak - avg) / scaleMax) * 100);
    const line100Pct = (100 / scaleMax) * 100;

    const weekdayNote =
      code === "R1"
        ? `<div style="font-size:10px; color:var(--text-dim); margin-top:4px;">Weekday demand is +13.7% higher (5,212 vs 4,585), which puts R1 at ~102% of seats at 61 trips.</div>`
        : "";

    bandContainer.innerHTML = `
      <div class="band-track-wrap" title="Lower bound (uniform alighting): ${avg}% · Upper bound (full-route ride): ${peak}%">
        <div class="band-fill ${peak >= 95 ? "over" : ""}" style="left:${leftPct.toFixed(1)}%; width:${widthPct.toFixed(1)}%;"></div>
        <div class="band-100-line" style="left:${line100Pct.toFixed(1)}%;" title="100% seat capacity"></div>
      </div>
      <div class="band-labels">
        <span>Avg bound: <strong>${avg.toFixed(1)}%</strong></span>
        <span><strong>${load.boardings_per_day.toLocaleString()}</strong> boardings/day (${load.pax_per_trip} pax/trip)</span>
        <span>Peak bound: <strong>${peak.toFixed(1)}%</strong></span>
      </div>
      ${weekdayNote}
    `;
  }

  // 3. Demand vs Service by Hour SVG Chart
  renderHourlyChart(code, master, hourly);

  // 4. Timetable Ribbon SVG
  renderTimetableRibbon(code, master, hourly);

  // 5. Day-type Strip
  renderDayTypeStrip(code);
}

function renderHourlyChart(code, master, hourly) {
  const container = document.getElementById("rp-hourly-chart");
  const hasDemand = hourly.demand.some((v) => v !== null);
  const hasService = hourly.trips.some((v) => v !== null);

  if (!hasDemand && !hasService) {
    container.innerHTML = `<div class="no-data-box">No ridership data and no live departure timings returned for ${code}.</div>`;
    return;
  }

  // Scale demand by day-type multiplier if route has dayType data
  const dt = FALLBACK_DATA.dayType[code];
  let dayMult = 1.0;
  if (dt && dt.sat_holiday) {
    dayMult = dt[state.selectedDayType] / dt.sat_holiday;
  }

  const demandSeries = hourly.demand.map((d) => (d !== null ? d * dayMult : null));
  const capSeries = hourly.trips.map((t) => (t !== null ? t * master.seats : null));

  const maxVal = Math.max(
    100,
    ...demandSeries.filter((v) => v !== null),
    ...capSeries.filter((v) => v !== null)
  );

  const W = 400;
  const H = 135;
  const padL = 28;
  const padR = 8;
  const padT = 12;
  const padB = 20;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const colW = plotW / 24;

  // Shaded "not captured" morning zone (hours 0..10)
  const uncapW = colW * 11;

  let barsSvg = "";
  for (let h = 0; h < 24; h++) {
    const x0 = padL + h * colW;
    const dVal = demandSeries[h];
    const cVal = capSeries[h];

    // Demand bar
    if (dVal !== null) {
      const bh = (dVal / maxVal) * plotH;
      const by = padT + plotH - bh;
      const over = cVal !== null && dVal > cVal;
      barsSvg += `<rect x="${(x0 + 1.2).toFixed(1)}" y="${by.toFixed(1)}" width="${(colW * 0.42).toFixed(1)}" height="${bh.toFixed(1)}" fill="${over ? "#e9222a" : "#e59849"}"><title>${h}:00 · Demand: ${Math.round(dVal)} pax (modelled)</title></rect>`;
    }

    // Seat capacity bar (only when captured, never 0 for null)
    if (cVal !== null) {
      const ch = (cVal / maxVal) * plotH;
      const cy = padT + plotH - ch;
      barsSvg += `<rect x="${(x0 + colW * 0.46).toFixed(1)}" y="${cy.toFixed(1)}" width="${(colW * 0.42).toFixed(1)}" height="${ch.toFixed(1)}" fill="#4fa39b"><title>${h}:00 · Capacity: ${cVal} seats (${hourly.trips[h]} trips × ${master.seats})</title></rect>`;
    }

    if (h % 3 === 0 || h === 23) {
      barsSvg += `<text x="${(x0 + colW / 2).toFixed(1)}" y="${H - 5}" fill="#9da6a0" font-size="9" text-anchor="middle">${String(h).padStart(2, "0")}</text>`;
    }
  }

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">
      <!-- Grid lines -->
      <line x1="${padL}" y1="${padT}" x2="${W - padR}" y2="${padT}" stroke="#2e3733" stroke-dasharray="2,2" />
      <line x1="${padL}" y1="${padT + plotH / 2}" x2="${W - padR}" y2="${padT + plotH / 2}" stroke="#2e3733" stroke-dasharray="2,2" />
      <line x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" stroke="#3b4641" />

      <!-- Y axis labels -->
      <text x="${padL - 4}" y="${padT + 4}" fill="#6e7772" font-size="9" text-anchor="end">${Math.round(maxVal)}</text>
      <text x="${padL - 4}" y="${padT + plotH / 2 + 3}" fill="#6e7772" font-size="9" text-anchor="end">${Math.round(maxVal / 2)}</text>
      <text x="${padL - 4}" y="${padT + plotH}" fill="#6e7772" font-size="9" text-anchor="end">0</text>

      <!-- Uncaptured window 00:00-10:59 -->
      <rect x="${padL}" y="${padT}" width="${uncapW.toFixed(1)}" height="${plotH}" fill="#1a211f" opacity="0.75" />
      <line x1="${(padL + uncapW).toFixed(1)}" y1="${padT}" x2="${(padL + uncapW).toFixed(1)}" y2="${padT + plotH}" stroke="#d4a857" stroke-dasharray="3,3" />
      <text x="${(padL + uncapW / 2).toFixed(1)}" y="${padT + 12}" fill="#9da6a0" font-size="8.5" text-anchor="middle">00–10h Service Not Captured</text>

      ${barsSvg}
    </svg>
  `;
}

function renderTimetableRibbon(code, master, hourly) {
  const container = document.getElementById("rp-ribbon-chart");
  const noteEl = document.getElementById("rp-capture-note");

  if (!hourly.firstOrder) {
    noteEl.textContent = "No timings returned";
    container.innerHTML = `<div class="no-data-box">Feed returns no scheduled departure times for ${code}.</div>`;
    return;
  }

  noteEl.textContent = `Starts at Trip #${hourly.firstOrder} (${master.capture_first_departure.slice(0, 5)}–${master.capture_last_departure.slice(0, 5)})`;

  const W = 400;
  const H = 46;
  const padL = 28;
  const padR = 8;
  const plotW = W - padL - padR;
  const colW = plotW / 24;
  const uncapW = colW * 11;

  let ticks = "";
  for (let h = 11; h < 24; h++) {
    const depCount = hourly.trips[h];
    if (!depCount) continue;
    for (let i = 0; i < depCount; i++) {
      const frac = (i + 0.5) / depCount;
      const tx = padL + (h + frac) * colW;
      ticks += `<line x1="${tx.toFixed(1)}" y1="8" x2="${tx.toFixed(1)}" y2="26" stroke="#4fa39b" stroke-width="2"><title>${h}:00 hour · ${depCount} departures</title></line>`;
    }
  }

  container.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}">
      <rect x="${padL}" y="6" width="${uncapW.toFixed(1)}" height="22" fill="#1a211f" stroke="#2e3733" stroke-dasharray="2,2" />
      <text x="${(padL + uncapW / 2).toFixed(1)}" y="20" fill="#6e7772" font-size="8.5" text-anchor="middle">Trips #1–#${hourly.firstOrder - 1} not in feed</text>
      ${ticks}
      <line x1="${padL}" y1="28" x2="${W - padR}" y2="28" stroke="#2e3733" />
      <text x="${padL}" y="40" fill="#6e7772" font-size="8.5">00:00</text>
      <text x="${(padL + uncapW).toFixed(1)}" y="40" fill="#d4a857" font-size="8.5" text-anchor="middle">11:00</text>
      <text x="${W - padR}" y="40" fill="#6e7772" font-size="8.5" text-anchor="end">23:59</text>
    </svg>
  `;
}

function renderDayTypeStrip(code) {
  const container = document.getElementById("rp-daytype-strip");
  const dt = FALLBACK_DATA.dayType[code];

  if (!dt) {
    container.innerHTML = `<div class="no-data-box">No day-type ridership data for ${code}.</div>`;
    return;
  }

  const maxPax = Math.max(dt.weekday, dt.sat_holiday, dt.friday);
  const rows = [
    { label: "Weekday", val: dt.weekday, pct: "100%" },
    { label: "Sat / Holiday", val: dt.sat_holiday, pct: `${Math.round((dt.sat_holiday / dt.weekday) * 100)}%` },
    { label: "Friday (−37%)", val: dt.friday, pct: `${Math.round((dt.friday / dt.weekday) * 100)}%` }
  ];

  container.innerHTML = `
    <div class="daytype-rows">
      ${rows
        .map(
          (r) => `
        <div class="daytype-row">
          <span style="color:var(--text-muted)">${r.label}</span>
          <div class="daytype-bar-bg">
            <div class="daytype-bar-fill" style="width:${((r.val / maxPax) * 100).toFixed(1)}%"></div>
          </div>
          <span style="text-align:right; font-weight:600;">${r.val.toLocaleString()}</span>
        </div>
      `
        )
        .join("")}
    </div>
  `;
}

// C3: Scenario Bar & Live Slider
function selectScenario(scenKey) {
  state.selectedScenario = scenKey;

  document.querySelectorAll("#scenario-buttons .scen-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.scen === scenKey);
  });

  const slider = document.getElementById("rebalance-slider");
  const interpBadge = document.getElementById("interp-badge");
  interpBadge.classList.remove("visible");

  if (scenKey === "S3_rebalanced_to_corridor") {
    slider.value = 6;
    document.getElementById("slider-val-label").textContent = "6 trips (S3)";
  } else {
    slider.value = 0;
    document.getElementById("slider-val-label").textContent = "0 trips";
  }

  const scen = FALLBACK_DATA.scenarios[scenKey];
  updateKpiTiles(scen, false);
}

function handleSliderInput(tripsMoved) {
  const sliderValLabel = document.getElementById("slider-val-label");
  const interpBadge = document.getElementById("interp-badge");
  sliderValLabel.textContent = `${tripsMoved} trips`;

  // Linear interpolation between S0 (0 trips) and S3 (6 trips), extended to 0..12 per spec §4 C3
  const s0 = FALLBACK_DATA.scenarios.S0_baseline;
  const s3 = FALLBACK_DATA.scenarios.S3_rebalanced_to_corridor;
  const t = tripsMoved / 6;

  if (tripsMoved === 0) {
    selectScenario("S0_baseline");
    return;
  }
  if (tripsMoved === 6) {
    selectScenario("S3_rebalanced_to_corridor");
    return;
  }

  document.querySelectorAll("#scenario-buttons .scen-btn").forEach((btn) => {
    btn.classList.remove("active");
  });
  interpBadge.classList.add("visible");

  const overCap = Math.round(s0.boardings_over_capacity + t * (s3.boardings_over_capacity - s0.boardings_over_capacity));
  const unmet = +(s0.unmet_share_pct + t * (s3.unmet_share_pct - s0.unmet_share_pct)).toFixed(2);
  const wait = +(s0.mean_wait_min_captured + t * (s3.mean_wait_min_captured - s0.mean_wait_min_captured)).toFixed(1);
  const trips = Math.round(s0.total_trips_captured + t * (s3.total_trips_captured - s0.total_trips_captured));

  const r1Over = Math.max(0, Math.round(s0.corridors.R1 + t * (s3.corridors.R1 - s0.corridors.R1)));
  const r4Over = Math.max(0, Math.round(s0.corridors.R4 + t * (s3.corridors.R4 - s0.corridors.R4)));

  updateKpiTiles(
    {
      boardings_over_capacity: overCap,
      unmet_share_pct: unmet,
      mean_wait_min_captured: wait,
      total_trips_captured: trips,
      over_capacity_change: overCap - s0.boardings_over_capacity,
      wait_change_min: +(wait - s0.mean_wait_min_captured).toFixed(1),
      trips_change: trips - s0.total_trips_captured,
      taxi_capturable_day: s0.taxi_capturable_day,
      corridors: { R1: r1Over, R2: 24, R3: 0, R4: r4Over, R7: 13 }
    },
    true
  );
}

function updateKpiTiles(scen, isInterpolated) {
  const s0 = FALLBACK_DATA.scenarios.S0_baseline;
  const isBaseline = !isInterpolated && scen === s0;

  // Over-capacity
  document.getElementById("kpi-overcap").textContent = scen.boardings_over_capacity;
  const overDelta = document.getElementById("kpi-overcap-delta");
  if (isBaseline) {
    overDelta.textContent = "baseline";
    overDelta.className = "kpi-delta neutral";
  } else {
    const d = scen.over_capacity_change;
    overDelta.textContent = `${d > 0 ? "+" : ""}${d}${isInterpolated ? " (interp)" : ""}`;
    overDelta.className = "kpi-delta " + (d < 0 ? "good" : "neutral");
  }
  const c = scen.corridors;
  document.getElementById("kpi-overcap-sub").textContent = `R1: ${c.R1} · R2: ${c.R2} · R4: ${c.R4} · R7: ${c.R7}`;

  // Unmet %
  document.getElementById("kpi-unmet").textContent = `${scen.unmet_share_pct.toFixed(2)}%`;
  const unmetDelta = document.getElementById("kpi-unmet-delta");
  const uDiff = +(scen.unmet_share_pct - s0.unmet_share_pct).toFixed(2);
  if (isBaseline || uDiff === 0) {
    unmetDelta.textContent = isBaseline ? "baseline" : "0.00 pp";
    unmetDelta.className = "kpi-delta neutral";
  } else {
    unmetDelta.textContent = `${uDiff > 0 ? "+" : ""}${uDiff} pp`;
    unmetDelta.className = "kpi-delta " + (uDiff < 0 ? "good" : "neutral");
  }

  // Mean wait
  document.getElementById("kpi-wait").textContent = `${scen.mean_wait_min_captured.toFixed(1)} min`;
  const waitDelta = document.getElementById("kpi-wait-delta");
  if (isBaseline || scen.wait_change_min === 0) {
    waitDelta.textContent = isBaseline ? "baseline" : "0.0 min";
    waitDelta.className = "kpi-delta neutral";
  } else {
    const w = scen.wait_change_min;
    waitDelta.textContent = `${w > 0 ? "+" : ""}${w.toFixed(1)} min`;
    waitDelta.className = "kpi-delta " + (w < 0 ? "good" : "neutral");
  }

  // Trips captured
  document.getElementById("kpi-trips").textContent = scen.total_trips_captured;
  const tripsDelta = document.getElementById("kpi-trips-delta");
  if (isBaseline || scen.trips_change === 0) {
    tripsDelta.textContent = isBaseline ? "baseline" : "0 trips";
    tripsDelta.className = "kpi-delta neutral";
  } else {
    const tr = scen.trips_change;
    tripsDelta.textContent = `${tr > 0 ? "+" : ""}${tr} trips`;
    tripsDelta.className = "kpi-delta neutral";
  }

  // Taxi capture
  const taxiVal = Math.round(scen.taxi_capturable_day);
  const taxiDiff = Math.round(scen.taxi_capturable_day - s0.taxi_capturable_day);
  document.getElementById("kpi-taxi").textContent = `${taxiVal}/d`;
  const taxiDelta = document.getElementById("kpi-taxi-delta");
  if (isBaseline || taxiDiff === 0) {
    taxiDelta.textContent = isBaseline ? "baseline" : "0/d";
    taxiDelta.className = "kpi-delta neutral";
  } else {
    taxiDelta.textContent = `+${taxiDiff}/d`;
    taxiDelta.className = "kpi-delta good";
  }
}

// Populate C4 Coverage Table
function renderCoverageMatrix() {
  const tbody = document.getElementById("coverage-tbody");
  tbody.innerHTML = FALLBACK_DATA.routesMaster
    .map((r) => {
      const load = FALLBACK_DATA.routeLoad[r.route_code];
      const hasDemand = load && load.load_factor_peak_pct !== null;
      return `
        <tr>
          <td><strong style="color:${r.colour}">${r.route_code}</strong></td>
          <td>${r.route_name}</td>
          <td class="dv">${r.route_name_dv || "—"}</td>
          <td>${r.bus_type} · ${r.seats} seats</td>
          <td class="${hasDemand ? "status-yes" : "status-no"}">${load.demand_source}</td>
          <td class="${r.trips_captured > 0 ? "status-yes" : "status-no"}">${load.service_capture}</td>
          <td>${hasDemand ? `${load.load_factor_avg_pct}% – ${load.load_factor_peak_pct}%` : "—"}</td>
        </tr>
      `;
    })
    .join("");
}

// Wire UI Controls
function bindEvents() {
  // Map colour mode
  const btnLoad = document.getElementById("mode-load-btn");
  const btnRtl = document.getElementById("mode-rtl-btn");
  btnLoad.addEventListener("click", () => {
    state.colourMode = "load";
    btnLoad.classList.add("active");
    btnRtl.classList.remove("active");
    drawMapLayers();
    renderRouteStrip();
  });
  btnRtl.addEventListener("click", () => {
    state.colourMode = "rtl";
    btnRtl.classList.add("active");
    btnLoad.classList.remove("active");
    drawMapLayers();
    renderRouteStrip();
  });

  // Causeway & Stops checkboxes
  document.getElementById("toggle-causeway").addEventListener("change", (e) => {
    state.showCauseway = e.target.checked;
    drawMapLayers();
  });
  document.getElementById("toggle-stops").addEventListener("change", (e) => {
    state.showStops = e.target.checked;
    drawMapLayers();
  });

  // Day-type switcher in Route Panel
  document.querySelectorAll("#daytype-switcher .toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#daytype-switcher .toggle-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.selectedDayType = btn.dataset.day;
      renderHourlyChart(state.selectedRoute, getRouteMaster(state.selectedRoute), FALLBACK_DATA.hourly[state.selectedRoute]);
    });
  });

  // Scenario buttons
  document.querySelectorAll("#scenario-buttons .scen-btn").forEach((btn) => {
    btn.addEventListener("click", () => selectScenario(btn.dataset.scen));
  });

  // Rebalance slider
  document.getElementById("rebalance-slider").addEventListener("input", (e) => {
    handleSliderInput(parseInt(e.target.value, 10));
  });

  // Drawer open/close
  const backdrop = document.getElementById("drawer-backdrop");
  const btnOpen = document.getElementById("btn-toggle-drawer");
  const btnClose = document.getElementById("btn-close-drawer");
  btnOpen.addEventListener("click", () => {
    backdrop.classList.toggle("open");
    btnOpen.classList.toggle("active", backdrop.classList.contains("open"));
  });
  btnClose.addEventListener("click", () => {
    backdrop.classList.remove("open");
    btnOpen.classList.remove("active");
  });
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) {
      backdrop.classList.remove("open");
      btnOpen.classList.remove("active");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  renderRouteStrip();
  renderRoutePanel();
  renderCoverageMatrix();
  bindEvents();
});
