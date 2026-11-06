"""
page_hourly.py - everything built from  pakistan_aqi_hourly_profile.csv
    * page_hourly()  -> "Hourly Profile" page
"""
import calendar

import pandas as pd
import plotly.express as px
import streamlit as st

from common import F, insights, kpis, need, show


def hourly_agg(f, by, col="pm2_5_avg"):
    w = f["samples"] if "samples" in f.columns else pd.Series(1, index=f.index)
    t = f.assign(_num=f[col] * w, _w=w)
    g = t.groupby(by).agg(_num=("_num", "sum"), _w=("_w", "sum")).reset_index()
    g[col] = g["_num"] / g["_w"]
    return g.drop(columns=["_num", "_w"])


def hr12(h):
    h = int(h) % 24
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"


HOUR_LABELS = [hr12(h) for h in range(24)]


def hour_axis(fig):
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=HOUR_LABELS, dtick=3,
                     title_text="Time of day")
    return fig


def page_hourly(df):
    st.header("Hourly Pollution Profile")
    need(df, ["city", "province", "month", "season", "hour", "pm2_5_avg", "us_aqi_avg"], "pakistan_aqi_hourly_profile")

    f = df
    if f.empty:
        st.warning("No data for the selected filters.")
        return

    by_hour = hourly_agg(f, "hour")
    by_season = hourly_agg(f, "season")
    peak, low = by_hour.loc[by_hour.pm2_5_avg.idxmax()], by_hour.loc[by_hour.pm2_5_avg.idxmin()]
    kpis([
        ("Peak pollution hour", hr12(peak.hour), f"PM2.5 {peak.pm2_5_avg:.0f} µg/m³"),
        ("Cleanest hour", hr12(low.hour), f"PM2.5 {low.pm2_5_avg:.0f} µg/m³"),
        ("Peak ÷ cleanest ratio", f"{peak.pm2_5_avg / low.pm2_5_avg:.2f}×", "daily swing in PM2.5"),
        ("Average PM2.5", f"{hourly_agg(f, lambda x: 0).pm2_5_avg.iloc[0]:.1f} µg/m³", "sample-weighted"),
        ("Worst season", by_season.loc[by_season.pm2_5_avg.idxmax(), "season"],
         f"PM2.5 {by_season.pm2_5_avg.max():.0f} µg/m³"),
    ])

    night = by_hour[by_hour.hour.between(0, 5)].pm2_5_avg.mean()
    day = by_hour[by_hour.hour.between(12, 17)].pm2_5_avg.mean()
    ins = [f"Pollution peaks around **{hr12(peak.hour)}** and bottoms out around **{hr12(low.hour)}**.",
           f"Afternoon (12–5 PM) PM2.5 is **{abs(1 - day / night) * 100:.0f}% "
           f"{'lower' if day < night else 'higher'}** than the early-morning (12–5 AM) level, "
           f"typical of {'boundary-layer mixing' if day < night else 'daytime emissions'}."]
    cg = hourly_agg(f, "city")
    ins.append(f"**{cg.loc[cg.pm2_5_avg.idxmax(), 'city']}** has the highest hourly-average PM2.5 "
               f"({cg.pm2_5_avg.max():.0f} µg/m³).")
    insights(ins)

    c1, c2 = st.columns(2)
    with c1:
        t = hourly_agg(f, ["season", "hour"]).sort_values("hour")
        t["time"] = t.hour.map(hr12)
        show(hour_axis(px.line(t, x="time", y="pm2_5_avg", color="season", markers=True,
                               title="PM2.5 by time of day and season", labels={"pm2_5_avg": "PM2.5"})))
    with c2:
        t = hourly_agg(f, ["month", "hour"]).pivot(index="month", columns="hour", values="pm2_5_avg")
        t.index = [calendar.month_abbr[int(m)] for m in t.index]
        t.columns = [hr12(h) for h in t.columns]
        fig = px.imshow(t, color_continuous_scale="YlOrRd", aspect="auto",
                        title="PM2.5 heatmap: month × time of day",
                        labels=dict(x="Time of day", y="", color="PM2.5"))
        fig.update_xaxes(dtick=3)
        show(fig)

    c3, c4 = st.columns(2)
    with c3:
        top = cg.sort_values("pm2_5_avg", ascending=False).city.head(6).tolist()
        sel = st.multiselect("Cities to compare (hourly curve)", sorted(f.city.unique()), default=top)
        t = hourly_agg(f[f.city.isin(sel)], ["city", "hour"]).sort_values("hour")
        t["time"] = t.hour.map(hr12)
        show(hour_axis(px.line(t, x="time", y="pm2_5_avg", color="city", title="City comparison: PM2.5 by time of day",
                               labels={"pm2_5_avg": "PM2.5"})), h=340)
    with c4:
        parts = pd.cut(f.hour, [-1, 5, 11, 17, 23], labels=["Night (12-5 AM)", "Morning (6-11 AM)",
                                                             "Afternoon (12-5 PM)", "Evening (6-11 PM)"])
        t = hourly_agg(f.assign(part=parts), ["city", "part"])
        t = t[t.city.isin(cg.nlargest(F["top_n"], "pm2_5_avg").city)]
        show(px.bar(t, x="city", y="pm2_5_avg", color="part", barmode="group",
                    title="PM2.5 by part of day", labels={"pm2_5_avg": "PM2.5", "city": ""}), h=420)

    one = st.selectbox("City for the full-day pollution clock", sorted(f.city.unique()))
    t = hourly_agg(f[f.city == one], "hour")
    fig = px.bar_polar(t, r="pm2_5_avg", theta=t.hour * 15, color="pm2_5_avg",
                       color_continuous_scale="YlOrRd", title=f"Full-day pollution clock: {one}")
    fig.update_layout(polar=dict(angularaxis=dict(tickmode="array", tickvals=list(range(0, 360, 45)),
                                                  ticktext=[hr12(h) for h in range(0, 24, 3)],
                                                  direction="clockwise", rotation=90)))
    show(fig, h=460)
