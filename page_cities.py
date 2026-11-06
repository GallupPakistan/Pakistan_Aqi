"""
page_cities.py - everything built from  pakistan_cities.csv
    * page_cities()  -> "Cities" page   (also uses the daily data, if present, to add AQI per city)
"""
import plotly.express as px
import streamlit as st

from common import haversine, insights, kpis, need, show


def page_cities(cities, daily):
    st.header("Cities & Geography")
    need(cities, ["city", "province", "latitude", "longitude"], "pakistan_cities")
    c = cities.copy()
    if daily is not None and {"city", "us_aqi_avg", "pm2_5_avg"} <= set(daily.columns):
        stats = daily.groupby("city").agg(avg_aqi=("us_aqi_avg", "mean"), avg_pm25=("pm2_5_avg", "mean")).reset_index()
        c = c.merge(stats, on="city", how="left")
    has_aq = "avg_aqi" in c.columns

    lat, lon = c.latitude.values, c.longitude.values
    span = haversine(lat[:, None], lon[:, None], lat[None, :], lon[None, :]).max()
    n_row, s_row = c.loc[c.latitude.idxmax()], c.loc[c.latitude.idxmin()]
    kpis([
        ("Cities covered", f"{c.city.nunique()}", "in the analysis"),
        ("Provinces", f"{c.province.nunique()}", ", ".join(sorted(c.province.unique()))[:40]),
        ("Northernmost", n_row.city, f"{n_row.latitude:.2f}°N"),
        ("Southernmost", s_row.city, f"{s_row.latitude:.2f}°N"),
        ("Max geographic span", f"{span:,.0f} km", "farthest city pair"),
    ])

    ins = []
    pc = c.province.value_counts()
    ins.append(f"**{pc.index[0]}** has the most monitored cities ({pc.iloc[0]} of {len(c)}).")
    if has_aq:
        w = c.dropna(subset=["avg_aqi"]).sort_values("avg_aqi")
        if len(w):
            ins.append(f"Cleanest city: **{w.iloc[0].city}** (AQI {w.iloc[0].avg_aqi:.0f}); "
                       f"most polluted: **{w.iloc[-1].city}** (AQI {w.iloc[-1].avg_aqi:.0f}).")
        pa = c.groupby("province").avg_aqi.mean().sort_values(ascending=False)
        ins.append(f"Province with the worst average AQI: **{pa.index[0]}** ({pa.iloc[0]:.0f}).")
    else:
        ins.append("Upload the daily dataset to enrich this page with AQI / PM2.5 per city.")
    insights(ins)

    kw = dict(lat="latitude", lon="longitude", hover_name="city", color="province", zoom=4.3)
    if has_aq:
        kw.update(size=c.avg_aqi.fillna(c.avg_aqi.mean()).clip(lower=10), hover_data={"avg_aqi": ":.0f"})
    fn = getattr(px, "scatter_map", None)
    fig = fn(c, map_style="open-street-map", **kw) if fn else px.scatter_mapbox(c, mapbox_style="open-street-map", **kw)
    fig.update_layout(title="Monitored cities (bubble size = average AQI when available)")
    show(fig, h=480)

    c1, c2 = st.columns(2)
    with c1:
        t = pc.reset_index()
        t.columns = ["province", "cities"]
        show(px.bar(t, x="province", y="cities", color="province", text="cities", title="Cities per province",
                    labels={"province": "", "cities": "cities"}), legend="off")
    with c2:
        ref = st.selectbox("Reference city", sorted(c.city))
        r = c[c.city == ref].iloc[0]
        c["dist_km"] = haversine(r.latitude, r.longitude, c.latitude, c.longitude)
        t = c[c.city != ref].sort_values("dist_km")
        show(px.bar(t, x="dist_km", y="city", color="province", orientation="h",
                    title=f"Distance from {ref} (km)", labels={"dist_km": "km", "city": ""}), h=400)

    c3, c4 = st.columns(2)
    with c3:
        if has_aq:
            t = c.dropna(subset=["avg_aqi"]).sort_values("avg_aqi")
            show(px.bar(t, x="avg_aqi", y="city", color="avg_aqi", color_continuous_scale="YlOrRd",
                        orientation="h", title="Average US AQI by city", labels={"avg_aqi": "AQI", "city": ""}))
        else:
            st.info("Load the daily file to see average AQI by city.")
    with c4:
        tm = c.copy()
        tm["value"] = tm.avg_aqi.fillna(1) if has_aq else 1
        show(px.treemap(tm, path=["province", "city"], values="value",
                        color="avg_aqi" if has_aq else None, color_continuous_scale="YlOrRd",
                        title="Province → city treemap" + (" (size/colour = AQI)" if has_aq else "")))