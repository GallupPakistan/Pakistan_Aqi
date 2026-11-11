"""
page_overview.py - "Overview" page: the national picture in 10 simple visuals (follows the sidebar filters).
    1 gauge: average AQI            2 donut: share of days by category     3 10 most polluted cities
    4 10 cleanest cities            5 month-by-month AQI over time         6 average AQI in each calendar month
    7 average AQI by province       8 safe / unsafe days each year         9 PM2.5 vs WHO safe limits
   10 average AQI by day of the week
"""
import calendar

import pandas as pd
import streamlit as st

import charts as ch
from common import (AQI_BINS, AQI_COLORS, AQI_LABELS, F, WHO_PM25_24H, WHO_PM25_ANNUAL, aqi_cat, insights, kpis,
                    same_window)


def page_overview(daily, hourly=None, cities=None, full=None):
    st.header("Pakistan's Air at a Glance")
    full = daily if full is None else full
    if daily is None or full is None or daily.empty:
        st.info("Load the daily air-quality file to see this page.")
        return
    d = daily
    n, nc, npv = len(full), full.city.nunique(), full.province.nunique()
    d0, d1 = full.date.min(), full.date.max()
    st.write(f"This dashboard covers **{n:,} days of readings** from **{nc} cities** in **{npv} provinces and "
             f"territories**, from **{d0:%d %b %Y}** to **{d1:%d %b %Y}**. Everything on this page follows the "
             f"filters in the sidebar.")

    avg = d.us_aqi_avg.mean()
    city = d.groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
    unhealthy = (d.us_aqi_avg > 150).mean() * 100
    safe = (d.us_aqi_avg <= 100).mean() * 100
    pm = d.pm2_5_avg.mean()
    kpis([
        ("Average air quality", f"{avg:.0f} AQI", aqi_cat(avg)),
        ("Safe-air days", f"{safe:.0f}%", "AQI 100 or below"),
        ("Unhealthy days", f"{unhealthy:.0f}%", "AQI above 150"),
        ("Most polluted city", city.index[0], f"average AQI {city.iloc[0]:.0f}"),
        ("Cleanest city", city.index[-1], f"average AQI {city.iloc[-1]:.0f}"),
    ])
    month = d.groupby(d.date.dt.month).us_aqi_avg.mean()
    insights([
        f"On average the air is **{aqi_cat(avg).lower()}** (AQI {avg:.0f}). Only **{safe:.0f}%** of days were safe "
        f"for everyone, and **{unhealthy:.0f}%** were unhealthy for everyone.",
        f"The worst month is **{calendar.month_name[int(month.idxmax())]}** and the best is "
        f"**{calendar.month_name[int(month.idxmin())]}**.",
        f"The average PM2.5 is **{pm:.0f} µg/m³**, about **{pm / WHO_PM25_24H:.1f} times** the WHO daily safe limit.",
    ])

    # 1 + 2
    a, b = st.columns(2)
    with a:
        ch.gauge(avg, "1. How clean is the air on average?")
        ch.note("The needle shows the **average AQI** for the current filters. Green is good, yellow is moderate, "
                "orange and red are unhealthy.")
    with b:
        cat = pd.cut(d.us_aqi_avg, AQI_BINS, labels=AQI_LABELS).value_counts().reindex(AQI_LABELS).fillna(0)
        ch.donut(AQI_LABELS, cat.values, "2. What is a typical day like?",
                 colors=[AQI_COLORS[c] for c in AQI_LABELS], center=f"{len(d):,}<br>days")
        ch.note("Each slice is the **share of all city-days** in that air-quality category.")

    # 3 + 4
    a, b = st.columns(2)
    k = min(F["top_n"], len(city))   # sidebar "Top N cities"
    with a:
        top = city.head(k)
        ch.bar(top.index, top.values, f"3. The {k} most polluted cities", scale="aqi", key_note=False)
        ch.note("Average AQI over the selected period. **Longer and redder bar = dirtier air.**")
    with b:
        low = city.tail(k).sort_values()
        ch.bar(low.index, low.values, f"4. The {k} cleanest cities", scale="aqi", key_note=False)
        ch.note("The cities with the **lowest average AQI**. Even many of these are not in the green zone.")
    ch.legend_note("aqi")

    # 5
    m = d.assign(ym=d.date.dt.to_period("M").dt.to_timestamp()).groupby("ym").us_aqi_avg.mean()
    ch.lines(m.index, {"Average AQI": m.values}, "5. How the air changed, month by month", y_title="AQI",
             colors=["#1b2a41"], ref=[(100, "Above this: unhealthy for sensitive groups", "#ff7e00"),
                                      (150, "Above this: unhealthy for everyone", "#d64545")], markers=True)
    ch.note("Each point is the **average AQI of one month** across the selected cities. The peaks every winter are "
            "the smog season.")

    # 6 + 7
    a, b = st.columns(2)
    with a:
        ch.bar([calendar.month_abbr[int(i)] for i in month.index], month.values,
               "6. Which months have the worst air?", horizontal=False, scale="aqi", key_note=False)
        ch.note("Average AQI for each calendar month, all years together.")
    with b:
        prov = d.groupby("province").us_aqi_avg.mean().sort_values(ascending=False)
        ch.bar(prov.index, prov.values, "7. Which provinces have the worst air?", scale="aqi", key_note=False)
        ch.note("Average AQI of all monitored cities in each province or territory.")
    ch.legend_note("aqi")

    # 8 + 9
    a, b = st.columns(2)
    with a:
        w, wl = same_window(d)
        g = w.assign(year=w.date.dt.year.astype(str),
                     grp=pd.cut(w.us_aqi_avg, [-1, 100, 150, 1e9],
                                labels=["Safe (AQI up to 100)", "Unhealthy for sensitive groups",
                                        "Unhealthy or worse"]))
        t = g.groupby(["year", "grp"], observed=False).size().unstack(fill_value=0)
        t = t.div(t.sum(axis=1), axis=0) * 100
        ch.stacked(list(t.index), {c: t[c].values for c in t.columns}, f"8. Safe and unsafe days each year ({wl})",
                   colors={"Safe (AQI up to 100)": "#1e9e5a", "Unhealthy for sensitive groups": "#ff7e00",
                           "Unhealthy or worse": "#d64545"})
        ch.note(f"Every year is counted over the **same dates ({wl})**, so a year still in progress compares fairly. "
                f"A bigger red part means more dangerous days.")
    with b:
        ch.bar(["Pakistan average", "WHO daily safe limit", "WHO yearly safe limit"],
               [pm, WHO_PM25_24H, WHO_PM25_ANNUAL], "9. PM2.5 compared with the WHO safe limits",
               scale=["#d64545", "#1e9e5a", "#1e9e5a"], fmt="{:.0f}", suffix=" µg/m³", key_note=False)
        ch.note(f"PM2.5 is the fine dust and smoke that reaches deep into the lungs. Pakistan's average is **"
                f"{pm / WHO_PM25_ANNUAL:.0f} times** the WHO yearly limit.")

    # 10
    wd = d.groupby(d.date.dt.weekday).us_aqi_avg.mean()
    ch.bar([calendar.day_name[i] for i in wd.index], wd.values, "10. Is the air worse on some days of the week?",
           horizontal=False, scale="aqi", key_note=False,
           value_range=[0, float(wd.max()) * 1.2])
    spread = wd.max() - wd.min()
    ch.note(f"Average AQI for each weekday. The gap between the best and worst day is only **{spread:.0f} AQI "
            f"point{'' if round(spread) == 1 else 's'}**, so weather and season matter far more than the day of the week.")
