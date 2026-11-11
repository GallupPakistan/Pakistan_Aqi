"""
page_cities.py - "Cities" page (geography and city-to-city comparison), 10 simple visuals
    1 map of cities coloured by air quality       2 every city ranked by PM2.5
    3 how many cities in each province             4 distance from a city you pick
    5 north to south                               6 west to east
    7 coast vs inland                              8 cleanest and dirtiest city in each province
    9 where Pakistan's unhealthy days happen      10 safe-air days in each city
"""
import pandas as pd
import plotly.express as px
import streamlit as st

import charts as ch
from common import (AQI_COLORS, AQI_LABELS, WHO_PM25_ANNUAL, aqi_cat, haversine, insights, kpis, need, show,
                    sticky_select)

PROV_COLORS = {"Punjab": "#2a78d6", "Sindh": "#eb6834", "Khyber Pakhtunkhwa": "#0f766e", "Balochistan": "#a16207",
               "Islamabad": "#7c3aed", "Gilgit-Baltistan": "#4d7c0f", "Azad Kashmir": "#be185d"}
COASTAL = {"Karachi", "Gwadar"}


def page_cities(cities, daily, provs=None):
    st.header("Cities & Geography")
    need(cities, ["city", "province", "latitude", "longitude"], "pakistan_cities")
    c = cities.copy()
    if provs:
        c = c[c.province.isin(provs)].reset_index(drop=True)
    if daily is None or daily.empty or c.empty:
        st.warning("No data for the current filters.")
        return
    d = daily[daily.city.isin(c.city)]
    stats = d.groupby("city").agg(aqi=("us_aqi_avg", "mean"), pm25=("pm2_5_avg", "mean"),
                                  safe=("us_aqi_avg", lambda s: (s <= 100).mean() * 100),
                                  bad=("us_aqi_avg", lambda s: (s > 150).sum())).reset_index()
    c = c.merge(stats, on="city", how="inner")
    if c.empty:
        st.warning("No air-quality records for these cities under the current filters.")
        return
    c["category"] = c.aqi.map(aqi_cat)

    lat, lon = c.latitude.values, c.longitude.values
    span = haversine(lat[:, None], lon[:, None], lat[None, :], lon[None, :]).max() if len(c) > 1 else 0.0
    best, worst = c.loc[c.aqi.idxmin()], c.loc[c.aqi.idxmax()]
    kpis([
        ("Cities", f"{len(c)}", f"in {c.province.nunique()} provinces / territories"),
        ("Most polluted", worst.city, f"average AQI {worst.aqi:.0f}"),
        ("Cleanest", best.city, f"average AQI {best.aqi:.0f}"),
        ("Above WHO yearly limit", f"{(c.pm25 > WHO_PM25_ANNUAL).sum()} of {len(c)}",
         f"cities with PM2.5 over {WHO_PM25_ANNUAL} µg/m³"),
        ("Distance covered", f"{span:,.0f} km", "between the two farthest cities"),
    ])
    insights([
        f"**{worst.city}** has the dirtiest air (AQI {worst.aqi:.0f}) and **{best.city}** the cleanest "
        f"(AQI {best.aqi:.0f}).",
        f"**{(c.pm25 > WHO_PM25_ANNUAL).sum()} of {len(c)}** cities are above the WHO yearly safe limit for PM2.5.",
        "The plains of central and eastern Punjab form the most polluted belt; the northern mountains are the "
        "cleanest.",
    ])

    # 1
    fn = getattr(px, "scatter_map", None)
    kw = dict(lat="latitude", lon="longitude", hover_name="city", color="category",
              color_discrete_map=AQI_COLORS, category_orders={"category": AQI_LABELS},
              hover_data={"aqi": ":.0f", "pm25": ":.0f", "category": False, "latitude": False, "longitude": False},
              labels={"aqi": "Average AQI", "pm25": "Average PM2.5", "category": "Air quality"}, zoom=4.2)
    fig = (fn(c, map_style="open-street-map", **kw) if fn else px.scatter_mapbox(c, mapbox_style="open-street-map", **kw))
    fig.update_traces(marker=dict(size=16))
    fig.update_layout(title="1. Where the cities are, coloured by their usual air quality")
    show(fig, h=500, legend="right")
    ch.note("Each dot is a city. **The colour is its average air-quality category.** Hover a dot for its numbers.")

    # 2 + 3
    a, b = st.columns(2)
    with a:
        r = c.sort_values("pm25", ascending=False)
        ch.bar(r.city, r.pm25.values, "2. Every city ranked by fine dust and smoke (PM2.5)", scale="pm25",
               ref=[(WHO_PM25_ANNUAL, "WHO yearly limit", "#1e9e5a")], key_note=False)
        ch.note("Average PM2.5 in µg/m³. The green dashed line is the WHO yearly safe limit.")
    with b:
        pc = c.province.value_counts()
        ch.bar(pc.index, pc.values, "3. How many cities are covered in each province?",
               scale=[PROV_COLORS.get(p, "#5b6b82") for p in pc.index], key_note=False)
        ch.note("Number of monitored cities per province or territory. Provinces with few cities are represented "
                "by fewer points, so treat their averages with care.")
        # 4
        ref_opts = sorted(c.city)
        ref = sticky_select(st, "Distance from (chart 4)", ref_opts, "dist_ref", default="Lahore")
        rr = c[c.city == ref].iloc[0]
        dist = c.assign(km=haversine(rr.latitude, rr.longitude, c.latitude, c.longitude))
        dist = dist[dist.city != ref].sort_values("km").head(12)
        ch.bar(dist.city, dist.km.values, f"4. The 12 nearest cities to {ref}", scale="#5b6b82", suffix=" km",
               fmt="{:,.0f}", key_note=False, h=380)
        ch.note("Straight-line distance. Nearby cities often share the same smog cloud.")
    ch.legend_note("pm25")

    # 5 + 6
    a, b = st.columns(2)
    with a:
        ns = c.groupby(pd.cut(c.latitude, [0, 27, 30, 33, 40],
                              labels=["Far south (Sindh coast)", "South", "Centre", "North"]), observed=False).aqi.mean()
        ns = ns.dropna()
        ch.bar(ns.index.astype(str), ns.values, "5. From south to north: where is the air worse?", horizontal=False,
               scale="aqi", key_note=False, y_title="average AQI")
        ch.note("Cities grouped by how far north they are (below 27°N, 27-30°, 30-33°, above 33°).")
    with b:
        we = c.groupby(pd.cut(c.longitude, [0, 66, 69, 72, 80],
                              labels=["Far west (Balochistan coast)", "West", "Centre", "East"]), observed=False).aqi.mean()
        we = we.dropna()
        ch.bar(we.index.astype(str), we.values, "6. From west to east: where is the air worse?", horizontal=False,
               scale="aqi", key_note=False, y_title="average AQI")
        ch.note("Cities grouped by how far east they are (below 66°E, 66-69°, 69-72°, above 72°).")

    # 7 + 8
    a, b = st.columns(2)
    with a:
        ci = c.assign(zone=c.city.map(lambda x: "Coastal cities" if x in COASTAL else "Inland cities")) \
              .groupby("zone").aqi.mean().reindex(["Coastal cities", "Inland cities"]).dropna()
        ch.bar(ci.index, ci.values, "7. Does the sea breeze help?", horizontal=False, scale="aqi", key_note=False,
               y_title="average AQI")
        ch.note("Karachi and Gwadar (on the coast) compared with all inland cities.")
    with b:
        multi = c.province.value_counts()
        multi = multi[multi >= 2].index   # a province with one city has no best/worst pair
        ext = c[c.province.isin(multi)].sort_values("aqi").groupby("province").agg(
            clean=("city", "first"), clean_v=("aqi", "first"), dirty=("city", "last"), dirty_v=("aqi", "last"))
        ext = ext.sort_values("dirty_v", ascending=False)
        ch.grouped(list(ext.index), {"Cleanest city": ext.clean_v.values, "Most polluted city": ext.dirty_v.values},
                   "8. Best and worst city in each province", colors=["#1e9e5a", "#d64545"], horizontal=True,
                   texts={"Cleanest city": [f"{n} {v:.0f}" for n, v in zip(ext.clean, ext.clean_v)],
                          "Most polluted city": [f"{n} {v:.0f}" for n, v in zip(ext.dirty, ext.dirty_v)]})
        ch.note("Average AQI of the cleanest (green) and most polluted (red) city in each province with two or more "
                "cities. A big gap means air quality varies a lot inside that province.")
    ch.legend_note("aqi")

    # 9 + 10
    a, b = st.columns(2)
    with a:
        pb = c.groupby("province").bad.sum().sort_values(ascending=False)
        ch.donut(pb.index, pb.values, "9. Where do Pakistan's unhealthy days happen?",
                 colors=[PROV_COLORS.get(p, "#5b6b82") for p in pb.index], center="unhealthy<br>city-days")
        ch.note("Share of all **city-days with AQI above 150**, by province. A big slice means many bad days in "
                "many cities.")
    with b:
        s = c.sort_values("safe", ascending=False)
        ch.bar(s.city, s.safe.values, "10. Which cities get the most safe-air days?", scale="#1e9e5a", suffix="%",
               key_note=False, value_range=[0, 112])
        ch.note("Share of days with AQI 100 or below (safe for most people).")
    st.caption("Islamabad and Rawalpindi fall in the same model grid cell, so their pollution figures are identical.")
