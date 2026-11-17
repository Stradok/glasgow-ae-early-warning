"""Build the weekly Glasgow A&E + weather + air-quality dataset.

Sources (all open, no API key):
  - Public Health Scotland weekly A&E activity (OGL licence)
  - Open-Meteo historical weather archive (ERA5-based reanalysis)
  - Open-Meteo air quality (CAMS modelled, not monitor measurements)

Run:  python3 -I build_dataset.py      (needs only numpy + stdlib)
Output: data/weekly_dataset.csv, data/raw_*.json
"""
import csv
import datetime as dt
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

LAT, LON = 55.8642, -4.2518  # Glasgow city centre
PHS_RESOURCE = "a5f7ca94-c810-41b5-a7c9-25c18d43e5a4"  # weekly A&E activity
SITES = {"G405H": "QEUH", "G107H": "GRI", "G513H": "RHC"}  # RHC = children's hospital
# PHS "All" = New Planned + Unplanned, and planned activity only exists from Dec 2020 (PHS dataset notes),
# so "All" has a definition break. "Unplanned" is defined consistently across 2015-2026.
ATT_CATEGORY = "Unplanned"
# Pin ONE weather model. Open-Meteo's default (best_match) blends ERA5, ERA5-Land and ECMWF IFS,
# which makes the series non-homogeneous; ERA5-Land is a single ~11 km reanalysis.
WEATHER_MODEL = "era5_land"
START, END = dt.date(2015, 2, 16), dt.date(2026, 10, 25)  # Monday before first week .. last Sunday


def get_json(url, params):
    full = url + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(full, timeout=90) as r:
        return json.load(r)


def pull_ae():
    out = {}
    for code in SITES:
        d = get_json(
            "https://www.opendata.nhs.scot/api/3/action/datastore_search",
            {
                "resource_id": PHS_RESOURCE,
                "filters": json.dumps({"TreatmentLocation": code, "AttendanceCategory": ATT_CATEGORY}),
                "limit": 5000,
                "sort": "WeekEndingDate asc",
            },
        )
        rows = d["result"]["records"]
        json.dump(rows, open(os.path.join(DATA, f"raw_ae_{code}.json"), "w"))
        out[code] = {
            dt.datetime.strptime(str(r["WeekEndingDate"]), "%Y%m%d").date(): r["NumberOfAttendancesEpisode"]
            for r in rows
        }
    return out


def pull_weather():
    d = get_json(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": LAT, "longitude": LON,
            "start_date": START.isoformat(), "end_date": END.isoformat(),
            "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min,"
                     "relative_humidity_2m_mean,precipitation_sum",
            "timezone": "Europe/London",
            "models": WEATHER_MODEL,
        },
    )["daily"]
    json.dump(d, open(os.path.join(DATA, "raw_weather_daily.json"), "w"))
    return d


def pull_air_quality():
    """Hourly PM2.5/PM10 pulled one year at a time, reduced to daily means."""
    daily = {}
    y = START.year
    while y <= END.year:
        s = max(START, dt.date(y, 1, 1))
        e = min(END, dt.date(y, 12, 31))
        d = get_json(
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            {"latitude": LAT, "longitude": LON, "start_date": s.isoformat(),
             "end_date": e.isoformat(), "hourly": "pm2_5,pm10", "timezone": "Europe/London"},
        )["hourly"]
        for t, a, b in zip(d["time"], d["pm2_5"], d["pm10"]):
            day = t[:10]
            acc = daily.setdefault(day, {"pm2_5": [], "pm10": []})
            if a is not None:
                acc["pm2_5"].append(a)
            if b is not None:
                acc["pm10"].append(b)
        y += 1
    out = {k: {m: (sum(v) / len(v) if v else None) for m, v in acc.items()} for k, acc in daily.items()}
    json.dump(out, open(os.path.join(DATA, "raw_airquality_daily.json"), "w"))
    return out


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def main():
    ae, w, aq = pull_ae(), pull_weather(), pull_air_quality()
    wd = {dt.date.fromisoformat(t): i for i, t in enumerate(w["time"])}

    weeks = sorted(set().union(*[set(v) for v in ae.values()]))
    rows = []
    for end in weeks:  # PHS weeks end on a Sunday; take Mon..Sun
        days = [end - dt.timedelta(days=k) for k in range(6, -1, -1)]
        idx = [wd[d] for d in days if d in wd]
        if len(idx) < 7:
            continue

        def col(name):
            return [w[name][i] for i in idx]

        aqd = [aq.get(d.isoformat(), {}) for d in days]
        row = {
            "week_ending": end.isoformat(),
            "temp_mean": mean(col("temperature_2m_mean")),
            "temp_max": max(x for x in col("temperature_2m_max") if x is not None),
            "temp_min": min(x for x in col("temperature_2m_min") if x is not None),
            "humidity_mean": mean(col("relative_humidity_2m_mean")),
            "precip_sum": sum(x for x in col("precipitation_sum") if x is not None),
            "pm2_5_mean": mean([a.get("pm2_5") for a in aqd]),
            "pm10_mean": mean([a.get("pm10") for a in aqd]),
        }
        for code, name in SITES.items():
            row[f"att_{name}"] = ae[code].get(end)
        rows.append(row)

    path = os.path.join(DATA, "weekly_dataset.csv")
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(f"wrote {path}: {len(rows)} weeks, {rows[0]['week_ending']} -> {rows[-1]['week_ending']}")


if __name__ == "__main__":
    main()
