"""
page_hourly.py - "Hourly Profile" page, built from  pakistan_aqi_hourly_profile.csv  (10 simple visuals)
    1 night / morning / afternoon / evening        2 the daily curve in each season
    3 cleanest hour in each city                    4 how much dirtier late night is than the afternoon, per city
    5 hour-by-hour curve for cities you pick        6 months with the biggest day-night difference
    7 unhealthy hours per day, by month             8 at what hour do most cities peak?
    9 safe hours per day, per city                 10 share of all hours in each air-quality category
"""
import calendar

import numpy as np
import pandas as pd
import streamlit as st

import charts as ch
from common import AQI_BINS, AQI_COLORS, AQI_LABELS, F, hr12, insights, kpis, need, season_sort, sticky_multi

PARTS = ["Night (12-6 AM)", "Morning (6 AM-12 PM)", "Afternoon (12-6 PM)", "Evening (6 PM-12 AM)"]
PART_LABELS = [p.replace(" (", "<br>(") for p in PARTS]   # two-line axis labels


def hourly_agg(f, by, col="pm2_5_avg"):
    """Average weighted by the number of days behind each row ('samples')."""
    w = f["samples"] if "samples" in f.columns else pd.Series(1, index=f.index)
    t = f.assign(_num=f[col] * w, _w=w)
    g = t.groupby(by, observed=False).agg(_num=("_num", "sum"), _w=("_w", "sum")).reset_index()
    g[col] = g["_num"] / g["_w"]
    return g.drop(columns=["_num", "_w"])


def page_hourly(df):
    st.header("Pollution Around the Clock")
    need(df, ["city", "province", "month", "season", "hour", "pm2_5_avg", "us_aqi_avg"], "pakistan_aqi_hourly_profile")
    f = df.assign(part=pd.cut(df.hour, [-1, 5, 11, 17, 23], labels=PARTS))
    if f.empty:
        st.warning("No data for the selected filters.")
        return

    by_hour = hourly_agg(f, "hour")
    peak, low = by_hour.loc[by_hour.pm2_5_avg.idxmax()], by_hour.loc[by_hour.pm2_5_avg.idxmin()]
    parts = hourly_agg(f, "part")
    city_hour = hourly_agg(f, ["city", "hour"])
    safe_lim, bad_lim = ch.PM25_SAFE, ch.PM25_UNHEALTHY   # PM2.5 equal to AQI 100 and AQI 150
    kpis([
        ("Dirtiest hour", hr12(peak.hour), f"PM2.5 {peak.pm2_5_avg:.0f} µg/m³ on average"),
        ("Cleanest hour", hr12(low.hour), f"PM2.5 {low.pm2_5_avg:.0f} µg/m³ on average"),
        ("Night vs afternoon", f"{peak.pm2_5_avg / low.pm2_5_avg:.1f}×", "dirtiest hour ÷ cleanest hour"),
        ("Safe hours a day", f"{(city_hour.pm2_5_avg <= safe_lim).sum() / city_hour.city.nunique():.0f} of 24",
         "average city, PM2.5 in the safe range"),
        ("Cities covered", f"{f.city.nunique()}", "in the hourly file"),
    ])
    night = parts.set_index("part").pm2_5_avg
    insights([
        f"Air is dirtiest around **{hr12(peak.hour)}** and cleanest around **{hr12(low.hour)}**.",
        f"Night-time air ({night.get(PARTS[0], np.nan):.0f} µg/m³) is much dirtier than afternoon air "
        f"({night.get(PARTS[2], np.nan):.0f} µg/m³): in the afternoon the sun warms the ground and pollution mixes "
        f"upwards; at night it is trapped near the ground.",
        "**Best time to be outdoors: early to mid afternoon.** Late evening and night are the worst.",
    ])

    # 1 + 2
    a, b = st.columns(2)
    with a:
        ch.bar([PART_LABELS[PARTS.index(str(x))] for x in parts.part], parts.pm2_5_avg.values,
               "1. Which part of the day has the dirtiest air?",
               horizontal=False, scale="pm25", key_note=False, y_title="PM2.5 (µg/m³)")
        ch.note("Average PM2.5 in each quarter of the day, all cities and months together.")
    with b:
        t = hourly_agg(f, ["season", "hour"])
        seasons = season_sort(t.season.unique())
        ch.lines([hr12(h) for h in range(24)],
                 {s: t[t.season == s].set_index("hour").pm2_5_avg.reindex(range(24)).values for s in seasons},
                 "2. The daily rhythm in each season", y_title="PM2.5 (µg/m³)",
                 colors=["#7bb36b", "#e8a33d", "#2a78d6", "#a16207", "#d64545"])
        ch.note("One line per season. In smog season the whole curve is higher and the night-time peak is much "
                "stronger.")
    ch.legend_note("pm25")

    # 3 + 4
    a, b = st.columns(2)
    with a:
        best = city_hour.loc[city_hour.groupby("city").pm2_5_avg.idxmin()].sort_values("pm2_5_avg")
        ch.bar(best.city, best.pm2_5_avg.values, "3. Cleanest hour of the day in each city", scale="pm25",
               text=[f"{hr12(h)} · {v:.0f}" for h, v in zip(best.hour, best.pm2_5_avg)], key_note=False)
        ch.note("The label shows **the cleanest hour and its PM2.5**. Plan outdoor activity around this time.")
    with b:
        nt = hourly_agg(f, ["city", "part"]).pivot(index="city", columns="part", values="pm2_5_avg")
        gap = ((nt[PARTS[0]] / nt[PARTS[2]] - 1) * 100).sort_values(ascending=False)
        ch.bar(gap.index, gap.values, "4. How much dirtier is night than afternoon?", scale="#7c5cbf",
               fmt="{:+.0f}", suffix="%", key_note=False)
        ch.note("Night (12-6 AM) PM2.5 compared with afternoon (12-6 PM) in the same city. **+80% means night air "
                "carries 80% more fine dust and smoke.** Coastal and desert cities can be slightly cleaner at night.")

    # 5
    city_opts = sorted(f.city.unique())
    default = hourly_agg(f, "city").nlargest(4, "pm2_5_avg").city.tolist()
    sel = sticky_multi(st, "Cities to compare (chart 5)", city_opts, "hourly_cities", default=default)
    if sel:
        ch.lines([hr12(h) for h in range(24)],
                 {c: city_hour[city_hour.city == c].set_index("hour").pm2_5_avg.reindex(range(24)).values for c in sel},
                 "5. Hour by hour in the cities you picked", y_title="PM2.5 (µg/m³)", h=380)
        ch.note("Average PM2.5 at each hour for the chosen cities.")

    # 6 + 7
    a, b = st.columns(2)
    with a:
        mp = hourly_agg(f, ["month", "part"]).pivot(index="month", columns="part", values="pm2_5_avg")
        mg = (mp[PARTS[0]] - mp[PARTS[2]])
        ch.bar([calendar.month_abbr[int(m)] for m in mg.index], mg.values,
               "6. In which months is the night-day gap biggest?", horizontal=False, scale="#7c5cbf",
               key_note=False, y_title="µg/m³ more at night")
        ch.note("How much more PM2.5 there is at night than in the afternoon, month by month. Winter nights trap the "
                "most smoke.")
    with b:
        mh = hourly_agg(f, ["city", "month", "hour"])
        uh = (mh.assign(bad=mh.pm2_5_avg > bad_lim).groupby(["city", "month"]).bad.sum()
              .groupby("month").mean())
        ch.bar([calendar.month_abbr[int(m)] for m in uh.index], uh.values,
               "7. Hours a day with unhealthy air, by month", horizontal=False, scale="#d64545", fmt="{:.1f}",
               key_note=False, y_title="hours per day", value_range=[0, 27])
        ch.note(f"For a typical city, how many of the 24 hours have PM2.5 above {bad_lim:.0f} µg/m³ (the level that "
                f"counts as unhealthy for everyone) in each month.")

    # 8 + 9
    a, b = st.columns(2)
    with a:
        pk = city_hour.loc[city_hour.groupby("city").pm2_5_avg.idxmax()].hour.value_counts().sort_index()
        ch.bar([hr12(h) for h in pk.index], pk.values, "8. At what hour do most cities hit their worst air?",
               horizontal=False, scale="#5b6b82", key_note=False, y_title="number of cities")
        ch.note("Each bar counts **how many cities have their dirtiest hour** at that time.")
    with b:
        safe = (city_hour.assign(ok=city_hour.pm2_5_avg <= safe_lim).groupby("city").ok.sum()
                .sort_values(ascending=False))
        ch.bar(safe.index, safe.values, "9. Safe-air hours per day in each city", scale="#1e9e5a",
               suffix=" h", key_note=False, value_range=[0, 27])
        ch.note(f"How many of the 24 hours have average PM2.5 of {safe_lim:.0f} µg/m³ or less (the safe range for "
                f"most people).")

    # 10
    cat = f.pm2_5_avg.map(ch.pm25_cat).astype(pd.CategoricalDtype(AQI_LABELS))
    w = f["samples"] if "samples" in f.columns else pd.Series(1, index=f.index)
    sh = w.groupby(cat, observed=False).sum().reindex(AQI_LABELS).fillna(0)
    a, b = st.columns([3, 2])
    with a:
        ch.donut(AQI_LABELS, sh.values, "10. A typical hour, by air quality",
                 colors=[AQI_COLORS[c] for c in AQI_LABELS], center="24 hours<br>× every day")
    with b:
        st.markdown("<div style='height:80px'></div>", unsafe_allow_html=True)
        ch.note("Each slice is the **share of hours** (every city, every month) whose average PM2.5 falls in that "
                "air-quality category. Green and yellow hours are safe for most people.")
