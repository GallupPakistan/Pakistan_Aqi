"""
Pakistan Air Quality + Weather Data Downloader (Open-Meteo)  v3
---------------------------------------------------------------
Pakistan ke 34 shehron (har province + ICT, GB, AJK) ka air quality aur
mausam ka data Open-Meteo se download karta hai aur dashboard ke liye
3 clean CSV files banata hai:

  1. pakistan_air_quality_daily.csv   -> har shehar, har din ki ek row
                                         (pollution + mausam saath saath)
  2. pakistan_aqi_hourly_profile.csv  -> din ke kis ghante pollution zyada hota hai
                                         (shehar x mahina x ghanta ka average)
  3. pakistan_cities.csv              -> shehron ki list + lat/long (map ke liye)

Chalane ka tareeqa:
    python pakistan_aqi.py

Koi extra library ki zaroorat nahi (sirf Python 3.8+).
Dobara chalao toh latest data ke saath files update ho jayengi.

v3 changes:
  * aqi_category ab din ke AVERAGE AQI se banti hai (dashboard ke mutabiq);
    din ke sab se bure ghante ki category alag column aqi_category_peak mein hai.
  * Aakhir mein har shehar ke missing din check hote hain aur report hote hain.
"""

import csv
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta

# ------------------------------------------------------------------
# Settings (zaroorat ho toh yahan badlo)
# ------------------------------------------------------------------
START_DATE = date(2023, 1, 1)                  # global air quality data Aug 2022 se available hai
END_DATE = date.today() - timedelta(days=1)    # kal tak
TIMEZONE = "Asia/Karachi"

DAILY_FILE = "pakistan_air_quality_daily.csv"
PROFILE_FILE = "pakistan_aqi_hourly_profile.csv"
CITIES_FILE = "pakistan_cities.csv"

AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_RECENT_URL = "https://api.open-meteo.com/v1/forecast"

AQ_VARS = [
    "pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide",
    "ozone", "dust", "aerosol_optical_depth", "uv_index", "us_aqi",
]
WEATHER_VARS = [
    "temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation",
]

# (city, province, latitude, longitude)
CITIES = [
    # Punjab
    ("Lahore", "Punjab", 31.5497, 74.3436),
    ("Faisalabad", "Punjab", 31.4504, 73.1350),
    ("Rawalpindi", "Punjab", 33.5651, 73.0169),
    ("Multan", "Punjab", 30.1575, 71.5249),
    ("Gujranwala", "Punjab", 32.1877, 74.1945),
    ("Sialkot", "Punjab", 32.4945, 74.5229),
    ("Bahawalpur", "Punjab", 29.3956, 71.6836),
    ("Sargodha", "Punjab", 32.0836, 72.6711),
    ("Sheikhupura", "Punjab", 31.7131, 73.9783),
    ("Rahim Yar Khan", "Punjab", 28.4202, 70.2952),
    ("Dera Ghazi Khan", "Punjab", 30.0561, 70.6348),
    ("Sahiwal", "Punjab", 30.6682, 73.1114),
    # Sindh
    ("Karachi", "Sindh", 24.8607, 67.0011),
    ("Hyderabad", "Sindh", 25.3960, 68.3578),
    ("Sukkur", "Sindh", 27.7052, 68.8574),
    ("Larkana", "Sindh", 27.5570, 68.2264),
    ("Mirpur Khas", "Sindh", 25.5276, 69.0111),
    ("Nawabshah", "Sindh", 26.2442, 68.4100),
    # Khyber Pakhtunkhwa
    ("Peshawar", "Khyber Pakhtunkhwa", 34.0151, 71.5249),
    ("Mardan", "Khyber Pakhtunkhwa", 34.1989, 72.0231),
    ("Abbottabad", "Khyber Pakhtunkhwa", 34.1688, 73.2215),
    ("Mingora (Swat)", "Khyber Pakhtunkhwa", 34.7717, 72.3600),
    ("Dera Ismail Khan", "Khyber Pakhtunkhwa", 31.8314, 70.9019),
    ("Kohat", "Khyber Pakhtunkhwa", 33.5869, 71.4429),
    # Balochistan
    ("Quetta", "Balochistan", 30.1798, 66.9750),
    ("Gwadar", "Balochistan", 25.1264, 62.3225),
    ("Turbat", "Balochistan", 26.0023, 63.0440),
    ("Khuzdar", "Balochistan", 27.8000, 66.6167),
    ("Sibi", "Balochistan", 29.5430, 67.8773),
    # Islamabad Capital Territory
    ("Islamabad", "Islamabad", 33.6844, 73.0479),
    # Gilgit-Baltistan
    ("Gilgit", "Gilgit-Baltistan", 35.9208, 74.3080),
    ("Skardu", "Gilgit-Baltistan", 35.2971, 75.6333),
    # Azad Jammu & Kashmir
    ("Muzaffarabad", "Azad Kashmir", 34.3700, 73.4711),
    ("Mirpur", "Azad Kashmir", 33.1478, 73.7518),
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def aqi_category(aqi):
    """US AQI ko category mein badalta hai."""
    if aqi is None:
        return ""
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def season(month):
    if month in (11, 12, 1):
        return "Smog Season (Nov-Jan)"
    if month in (2, 3, 4):
        return "Spring (Feb-Apr)"
    if month in (5, 6):
        return "Summer (May-Jun)"
    if month in (7, 8, 9):
        return "Monsoon (Jul-Sep)"
    return "Pre-Smog (Oct)"


def wind_category(kmh):
    if kmh is None:
        return ""
    if kmh < 5:
        return "Stagnant (<5 km/h)"
    if kmh < 12:
        return "Light (5-12 km/h)"
    return "Breezy (12+ km/h)"


def avg(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def get_json(url, params, retries=3):
    full = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(full, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # network / rate-limit errors
            body = ""
            if hasattr(e, "read"):
                try:
                    body = e.read().decode("utf-8")[:200]
                except Exception:
                    pass
            print(f"      attempt {attempt} failed: {e} {body}")
            time.sleep(5 * attempt)
    return None


def year_chunks(start, end):
    """Bari request ko saal-saal ke tukron mein todta hai."""
    cur = start
    while cur <= end:
        chunk_end = min(date(cur.year, 12, 31), end)
        yield cur, chunk_end
        cur = chunk_end + timedelta(days=1)


def collect_hourly(data, variables, store):
    """API response ke hourly data ko {timestamp: {var: value}} mein daalta hai."""
    hourly = (data or {}).get("hourly", {})
    times = hourly.get("time", [])
    for var in variables:
        vals = hourly.get(var) or []
        for i, t in enumerate(times):
            v = vals[i] if i < len(vals) else None
            if v is not None:
                store[t][var] = v


# ------------------------------------------------------------------
# Download per city
# ------------------------------------------------------------------
def download_city(lat, lon):
    aq = defaultdict(dict)
    wx = defaultdict(dict)

    for s, e in year_chunks(START_DATE, END_DATE):
        base = {"latitude": lat, "longitude": lon, "timezone": TIMEZONE,
                "start_date": s.isoformat(), "end_date": e.isoformat()}

        d = get_json(AQ_URL, {**base, "hourly": ",".join(AQ_VARS)})
        if d and not d.get("error"):
            collect_hourly(d, AQ_VARS, aq)
        else:
            print(f"      {s.year} air quality: skip ({(d or {}).get('reason', 'no response')})")

        d = get_json(WEATHER_ARCHIVE_URL, {**base, "hourly": ",".join(WEATHER_VARS)})
        if d and not d.get("error"):
            collect_hourly(d, WEATHER_VARS, wx)
        else:
            print(f"      {s.year} weather: skip ({(d or {}).get('reason', 'no response')})")
        time.sleep(0.5)

    # Archive mein aakhri kuch din ka mausam der se aata hai -> recent API se bhar do
    d = get_json(WEATHER_RECENT_URL, {"latitude": lat, "longitude": lon, "timezone": TIMEZONE,
                                      "past_days": 14, "forecast_days": 1,
                                      "hourly": ",".join(WEATHER_VARS)})
    if d and not d.get("error"):
        recent = defaultdict(dict)
        collect_hourly(d, WEATHER_VARS, recent)
        end_str = END_DATE.isoformat()
        for t, vals in recent.items():
            if t[:10] <= end_str:
                for k, v in vals.items():
                    wx[t].setdefault(k, v)
    return aq, wx


def build_daily(city, prov, lat, lon, aq, wx):
    days = defaultdict(lambda: defaultdict(list))
    for store in (aq, wx):
        for t, vals in store.items():
            for k, v in vals.items():
                days[t[:10]][k].append(v)

    rows = []
    end_str = END_DATE.isoformat()
    for d in sorted(days):
        b = days[d]
        if d > end_str or not b.get("pm2_5"):
            continue
        dt = date.fromisoformat(d)
        aqi_max = max(b["us_aqi"]) if b.get("us_aqi") else None
        aqi_mean = avg(b.get("us_aqi", []))
        wind = avg(b.get("wind_speed_10m", []))
        rain = round(sum(b["precipitation"]), 1) if b.get("precipitation") else None
        rows.append({
            "date": d,
            "year": dt.year,
            "month": dt.month,
            "month_name": dt.strftime("%b"),
            "weekday": dt.strftime("%a"),
            "season": season(dt.month),
            "city": city,
            "province": prov,
            "latitude": lat,
            "longitude": lon,
            # pollution
            "pm2_5_avg": avg(b.get("pm2_5", [])),
            "pm2_5_max": round(max(b["pm2_5"]), 1),
            "pm10_avg": avg(b.get("pm10", [])),
            "co_avg": avg(b.get("carbon_monoxide", [])),
            "no2_avg": avg(b.get("nitrogen_dioxide", [])),
            "so2_avg": avg(b.get("sulphur_dioxide", [])),
            "ozone_avg": avg(b.get("ozone", [])),
            "dust_avg": avg(b.get("dust", [])),
            "aod_avg": avg(b.get("aerosol_optical_depth", [])),
            "uv_index_max": max(b["uv_index"]) if b.get("uv_index") else None,
            "us_aqi_avg": aqi_mean,
            "us_aqi_max": aqi_max,
            "aqi_category": aqi_category(aqi_mean),        # din ka average
            "aqi_category_peak": aqi_category(aqi_max),    # din ka sab se bura ghanta
            # weather
            "temp_avg_c": avg(b.get("temperature_2m", [])),
            "temp_min_c": min(b["temperature_2m"]) if b.get("temperature_2m") else None,
            "temp_max_c": max(b["temperature_2m"]) if b.get("temperature_2m") else None,
            "humidity_avg": avg(b.get("relative_humidity_2m", [])),
            "wind_avg_kmh": wind,
            "wind_category": wind_category(wind),
            "rain_mm": rain,
            "rain_day": "Yes" if rain and rain >= 1 else "No",
            "hours_recorded": len(b["pm2_5"]),
        })
    return rows


def build_hourly_profile(city, prov, aq):
    """Shehar x mahina x ghanta ka average PM2.5 aur AQI."""
    acc = defaultdict(lambda: {"pm": [], "aqi": []})
    end_str = END_DATE.isoformat()
    for t, vals in aq.items():
        if t[:10] > end_str or "pm2_5" not in vals:
            continue
        month = int(t[5:7])
        hour = int(t[11:13])
        acc[(month, hour)]["pm"].append(vals["pm2_5"])
        if "us_aqi" in vals:
            acc[(month, hour)]["aqi"].append(vals["us_aqi"])
    rows = []
    for (month, hour) in sorted(acc):
        a = acc[(month, hour)]
        rows.append({
            "city": city,
            "province": prov,
            "month": month,
            "month_name": date(2000, month, 1).strftime("%b"),
            "season": season(month),
            "hour": hour,
            "hour_label": f"{hour:02d}:00",
            "pm2_5_avg": avg(a["pm"]),
            "us_aqi_avg": avg(a["aqi"]),
            "samples": len(a["pm"]),
        })
    return rows


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    print(f"Data range: {START_DATE} se {END_DATE} tak, {len(CITIES)} shehar")
    print("Air quality + mausam dono download ho rahe hain (5-10 minute lag sakte hain)\n")

    daily, profile, failed, gaps = [], [], [], []
    for n, (city, prov, lat, lon) in enumerate(CITIES, 1):
        print(f"[{n}/{len(CITIES)}] {city}, {prov}")
        aq, wx = download_city(lat, lon)
        d_rows = build_daily(city, prov, lat, lon, aq, wx)
        p_rows = build_hourly_profile(city, prov, aq)
        expected = (END_DATE - START_DATE).days + 1
        print(f"      {len(d_rows)} din ka data")
        if not d_rows:
            failed.append(city)
        elif len(d_rows) < expected:
            gaps.append(f"{city} ({expected - len(d_rows)} din missing)")
        daily.extend(d_rows)
        profile.extend(p_rows)

    if not daily:
        print("\nKoi data nahi mila. Internet connection check karein.")
        return

    write_csv(DAILY_FILE, daily)
    write_csv(PROFILE_FILE, profile)
    write_csv(CITIES_FILE, [{"city": c, "province": p, "latitude": la, "longitude": lo}
                            for c, p, la, lo in CITIES])

    print("\nDone!")
    print(f"  {DAILY_FILE}: {len(daily):,} rows")
    print(f"  {PROFILE_FILE}: {len(profile):,} rows")
    print(f"  {CITIES_FILE}: {len(CITIES)} rows")
    if failed:
        print("In shehron ka data nahi mila:", ", ".join(failed))
    if gaps:
        print("\nDHYAN: kuch din download nahi hue (script dobara chalayein):")
        for g in gaps:
            print("  -", g)
    elif not failed:
        print("Har shehar ke saare din mil gaye.")


if __name__ == "__main__":
    main()
