"""
page_analysis.py - deeper analysis built from  pakistan_air_quality_daily.csv  (+ hourly file for the city report)
    * page_city_report()      -> "City Report" page      (one city, full history)
    * page_sources_trends()   -> "Sources & Trends" page (what drives pollution, is it getting worse)
    * page_episodes()         -> "Smog Episodes" page    (runs of very polluted days)

Methods (kept simple and stated on the pages):
    * Driver of a day  = the pollutant with the higher US AQI sub-index that day, PM2.5 ("smoke / fine particles")
                         or PM10 ("dust / coarse particles"), using the US EPA 2024 breakpoints on daily averages.
    * Trend            = monthly means minus that city's usual level for the calendar month (removes the seasons),
                         Theil-Sen slope, Mann-Kendall test corrected for month-to-month persistence.
    * Episode          = at least N consecutive days with daily average AQI above a threshold.
"""
import calendar
import math

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import charts as ch
from common import (AQI_BINS, AQI_COLORS, AQI_LABELS, F, WHO_24H, WHO_PM25_24H, WHO_PM25_ANNUAL, aqi_cat, download_csv,
                    explain, hr12, insights, kpis, need, same_window, show, sticky_select, table)

SMOKE, DUST, OZONE = "Smoke / fine particles (PM2.5)", "Dust / coarse particles (PM10)", "Ozone"
DRIVER_COLORS = {SMOKE: "#5b6472", DUST: "#c8913a", OZONE: "#3fa7b5"}
EP_COLORS = {"Smog": "#5b6472", "Dust": "#c8913a", "Ozone": "#3fa7b5"}
TREND_COLORS = {"Rising (clear)": "#d64545", "Falling (clear)": "#1e9e5a", "No clear trend": "#a3aab5"}
SHARED_CELL = {"Islamabad", "Rawalpindi"}   # same CAMS model grid cell: identical pollution values in the data
METRICS = {"pm2_5_avg": "PM2.5 (µg/m³)", "us_aqi_avg": "US AQI"}

# ----------------------------------------------------------------------------
# US EPA AQI sub-indices (2024 breakpoints), daily averages
# ----------------------------------------------------------------------------
_PM25 = [(0.0, 9.0, 0, 50), (9.1, 35.4, 51, 100), (35.5, 55.4, 101, 150), (55.5, 125.4, 151, 200),
         (125.5, 225.4, 201, 300), (225.5, 325.4, 301, 500)]
_PM10 = [(0, 54, 0, 50), (55, 154, 51, 100), (155, 254, 101, 150), (255, 354, 151, 200), (355, 424, 201, 300),
         (425, 604, 301, 500)]
_O3 = [(0, 54, 0, 50), (55, 70, 51, 100), (71, 85, 101, 150), (86, 105, 151, 200), (106, 200, 201, 300)]   # 8-h, ppb
UG_PER_PPB_O3 = 1.96   # ozone µg/m³ -> ppb at 25 °C


def _sub_index(conc, bp, decimals):
    c = np.floor(np.asarray(conc, dtype=float) * 10 ** decimals) / 10 ** decimals   # EPA truncation rule
    lo = np.array([b[0] for b in bp]); hi = np.array([b[1] for b in bp])
    ilo = np.array([b[2] for b in bp]); ihi = np.array([b[3] for b in bp])
    k = np.clip(np.searchsorted(lo, c, side="right") - 1, 0, len(bp) - 1)
    return ilo[k] + (ihi[k] - ilo[k]) / (hi[k] - lo[k]) * (c - lo[k])   # above the top band: extended linearly


@st.cache_data(show_spinner=False)
def with_drivers(df):
    out = df.copy()
    out["idx_pm25"] = _sub_index(out.pm2_5_avg, _PM25, 1)
    out["idx_pm10"] = _sub_index(out.pm10_avg, _PM10, 0)
    if "ozone_avg" in out.columns:   # daily mean used as a stand-in for the 8-hour average
        out["idx_o3"] = _sub_index(out.ozone_avg / UG_PER_PPB_O3, _O3, 0)
    else:
        out["idx_o3"] = 0.0
    idx = out[["idx_pm25", "idx_pm10", "idx_o3"]].to_numpy()
    out["driver"] = np.array([SMOKE, DUST, OZONE])[np.argmax(idx, axis=1)]
    out["fine_ratio"] = out.pm2_5_avg / out.pm10_avg.where(out.pm10_avg > 0)
    return out


# ----------------------------------------------------------------------------
# Trend statistics (numpy only, no extra packages)
# ----------------------------------------------------------------------------
def _sen_slope(x, y):
    i, j = np.triu_indices(len(x), 1)
    dx = x[j] - x[i]
    ok = dx != 0
    return float(np.median((y[j] - y[i])[ok] / dx[ok]))


def _mk_pvalue(y):
    """Mann-Kendall two-sided p-value; variance inflated for lag-1 autocorrelation of the detrended series."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 8:
        return np.nan
    i, j = np.triu_indices(n, 1)
    s = float(np.sign(y[j] - y[i]).sum())
    t = np.arange(n, dtype=float)
    res = y - _sen_slope(t, y) * t
    r1 = pd.Series(res).autocorr() if n > 3 else 0.0
    inflate = (1 + r1) / (1 - r1) if (r1 is not None and 0 < r1 < 0.95) else (39.0 if r1 and r1 >= 0.95 else 1.0)
    var = n * (n - 1) * (2 * n + 5) / 18 * inflate
    z = (s - np.sign(s)) / math.sqrt(var) if s != 0 else 0.0
    return math.erfc(abs(z) / math.sqrt(2))


@st.cache_data(show_spinner=False)
def monthly_anomalies(df, metric):
    """City x month means, the usual level for that calendar month, and the anomaly (mean - usual)."""
    m = (df.assign(ym=df.date.dt.to_period("M"))
         .groupby(["city", "province", "ym"])
         .agg(value=(metric, "mean"), days=("date", "count")).reset_index())
    m = m[m.days >= 15].copy()                       # ignore a month with too few days
    m["month"] = m.ym.dt.month
    m["usual"] = m.groupby(["city", "month"]).value.transform("mean")
    m["anom"] = m.value - m.usual
    m["t"] = m.ym.dt.year + (m.ym.dt.month - 0.5) / 12
    m["ts"] = m.ym.dt.to_timestamp()
    return m


@st.cache_data(show_spinner=False)
def city_trends(df, metric):
    m = monthly_anomalies(df, metric)
    rows = []
    for (city, prov), g in m.groupby(["city", "province"]):
        g = g.sort_values("t")
        slope = _sen_slope(g.t.values, g.anom.values)
        p = _mk_pvalue(g.anom.values)
        mean = g.value.mean()
        status = ("Rising (clear)" if slope > 0 else "Falling (clear)") if (p == p and p < 0.05) else "No clear trend"
        rows.append(dict(city=city, province=prov, per_year=slope, pct_per_year=slope / mean * 100 if mean else np.nan,
                         p_value=p, status=status, months=len(g), average=mean))
    return pd.DataFrame(rows).sort_values("pct_per_year", ascending=False).reset_index(drop=True)


def national_trend(df, metric):
    m = monthly_anomalies(df, metric)
    n = m.groupby("ts").agg(anom=("anom", "mean"), value=("value", "mean")).reset_index()
    t = n.ts.dt.year + (n.ts.dt.month - 0.5) / 12
    slope = _sen_slope(t.values, n.anom.values)
    p = _mk_pvalue(n.anom.values)
    return n, slope, p, slope / n.value.mean() * 100


def smog_seasons(df, metric):
    """Nov-Jan seasons that are complete in the data, labelled '2023-24' etc."""
    s = df[df.date.dt.month.isin([11, 12, 1])].copy()
    s["sy"] = np.where(s.date.dt.month == 1, s.date.dt.year - 1, s.date.dt.year)
    days = s.groupby("sy").date.nunique()
    full = [y for y, n in days.items() if n >= 90]
    s = s[s.sy.isin(full)]
    s["season"] = s.sy.astype(int).astype(str) + "-" + (s.sy.astype(int) + 1).astype(str).str[-2:]
    return s, sorted(s.season.unique())


# ----------------------------------------------------------------------------
# Episodes
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def find_episodes(df, threshold, min_days):
    d = with_drivers(df)
    rows = []
    for city, g in d.sort_values("date").groupby("city"):
        hit = (g.us_aqi_avg > threshold).values
        dates = g.date.values
        # a new run starts when a day is above the threshold and the previous row is not (or is not the day before)
        gap = np.r_[True, (np.diff(dates).astype("timedelta64[D]").astype(int) != 1)]
        start_flag = hit & (np.r_[True, ~hit[:-1]] | gap)
        run_id = np.cumsum(start_flag) * hit
        for rid in np.unique(run_id[run_id > 0]):
            x = g[run_id == rid]
            if len(x) < min_days:
                continue
            pk = x.loc[x.us_aqi_avg.idxmax()]
            rows.append(dict(
                city=city, province=x.province.iloc[0], start=x.date.min(), end=x.date.max(), days=len(x),
                peak_aqi=float(x.us_aqi_avg.max()), peak_date=pk.date, avg_aqi=float(x.us_aqi_avg.mean()),
                avg_pm25=float(x.pm2_5_avg.mean()), avg_pm10=float(x.pm10_avg.mean()),
                type=["Smog", "Dust", "Ozone"][int(np.argmax([x.idx_pm25.mean(), x.idx_pm10.mean(),
                                                              x.idx_o3.mean()]))]))
    cols = ["city", "province", "start", "end", "days", "peak_aqi", "peak_date", "avg_aqi", "avg_pm25", "avg_pm10", "type"]
    return pd.DataFrame(rows, columns=cols).sort_values(["start", "city"]).reset_index(drop=True)


def _fmt_range(a, b):
    return f"{a:%d %b %Y}" if a == b else (f"{a:%d %b} to {b:%d %b %Y}" if a.year == b.year else f"{a:%d %b %Y} to {b:%d %b %Y}")


# ============================================================================
# CITY REPORT  (one city, full history, 10 visuals)
#   1 gauge: average AQI         2 donut: share of days by category     3 month by month vs Pakistan
#   4 every day as a calendar    5 worst months of the year             6 worst hours of the day
#   7 year by year (same dates)  8 what causes the pollution            9 vs other cities in the province
#  10 each pollutant vs its WHO limit
# ============================================================================
def page_city_report(full, hourly):
    st.header("City Report Card")
    need(full, ["date", "city", "province", "pm2_5_avg", "pm10_avg", "us_aqi_avg"], "pakistan_air_quality_daily")
    cities = sorted(c_ for c_ in full.city.unique() if c_ in set(F.get("city_options") or full.city.unique()))
    if not cities:
        st.warning("No cities in the selected provinces.")
        return
    city = sticky_select(st, "City", cities, "report_city", default="Lahore")

    d = with_drivers(full)
    c = d[d.city == city].sort_values("date")
    prov = c.province.iloc[0]
    d0, d1 = c.date.min(), c.date.max()
    rank_tbl = d.groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
    rank = int(list(rank_tbl.index).index(city)) + 1
    avg, pm = c.us_aqi_avg.mean(), c.pm2_5_avg.mean()
    bad = (c.us_aqi_avg > 150).mean() * 100
    safe = (c.us_aqi_avg <= 100).mean() * 100
    tr = city_trends(full, "pm2_5_avg").set_index("city").loc[city]
    shares = c.driver.value_counts(normalize=True).reindex([SMOKE, DUST, OZONE]).fillna(0) * 100
    main_drv = shares.idxmax()
    ce = find_episodes(full, 200, 3)
    ce = ce[ce.city == city]
    mon = c.groupby(c.date.dt.month).us_aqi_avg.mean()
    short = {SMOKE: "Smoke", DUST: "Dust", OZONE: "Ozone"}

    kpis([
        ("Average AQI", f"{avg:.0f}", aqi_cat(avg)),
        ("National rank", f"{rank} of {len(rank_tbl)}", "1 = most polluted"),
        ("Safe-air days", f"{safe:.0f}%", "AQI 100 or below"),
        ("Unhealthy days", f"{bad:.0f}%", "AQI above 150"),
        ("Main cause", short[main_drv], f"{shares.max():.0f}% of days"),
        ("Episodes", f"{len(ce)}", "3+ days in a row above AQI 200"),
    ])
    lines = [f"**{city}** ({prov}) has an average AQI of **{avg:.0f}** ({aqi_cat(avg).lower()}), ranking **{rank} of "
             f"{len(rank_tbl)}** cities (1 = most polluted), from {d0:%d %b %Y} to {d1:%d %b %Y}.",
             f"Only **{safe:.0f}%** of days were safe; **{bad:.0f}%** were unhealthy for everyone. The worst month is "
             f"**{calendar.month_name[int(mon.idxmax())]}**, the best is **{calendar.month_name[int(mon.idxmin())]}**.",
             {SMOKE: f"The main problem is **smoke** (vehicles, industry, brick kilns, crop and waste burning): it set "
                     f"the AQI on {shares[SMOKE]:.0f}% of days.",
              DUST: f"The main problem is **desert dust**: it set the AQI on {shares[DUST]:.0f}% of days.",
              OZONE: f"The AQI is mostly set by **ozone** ({shares[OZONE]:.0f}% of days), a modelled effect over high "
                     f"ground; particle pollution is low here."}[main_drv]]
    lines.append("With the seasons removed, PM2.5 shows " + (
        f"**no clear trend** ({tr.pct_per_year:+.1f}% a year)." if tr.status == "No clear trend" else
        f"a **clear {'rise' if tr.per_year > 0 else 'fall'} of about {abs(tr.pct_per_year):.1f}% a year**."))
    if len(ce):
        lg = ce.loc[ce.days.idxmax()]
        lines.append(f"The longest bad spell lasted **{lg.days} days** ({_fmt_range(lg.start, lg.end)}).")
    if city in SHARED_CELL:
        lines.append("Islamabad and Rawalpindi fall in the **same model grid cell**, so their pollution figures are "
                     "identical; only the weather differs.")
    insights(lines)

    # 1 + 2
    a, b = st.columns(2)
    with a:
        ch.gauge(avg, f"1. {city}: average air quality")
        ch.note(f"The needle is {city}'s **average AQI** over the whole period.")
    with b:
        cat = pd.cut(c.us_aqi_avg, AQI_BINS, labels=AQI_LABELS).value_counts().reindex(AQI_LABELS).fillna(0)
        ch.donut(AQI_LABELS, cat.values, f"2. What a typical day in {city} is like",
                 colors=[AQI_COLORS[x] for x in AQI_LABELS], center=f"{len(c):,}<br>days")
        ch.note("Share of all days in each air-quality category.")

    # 3
    m = d.assign(ym=d.date.dt.to_period("M").dt.to_timestamp())
    cm = m[m.city == city].groupby("ym").us_aqi_avg.mean()
    nm = m.groupby("ym").us_aqi_avg.mean().reindex(cm.index)
    ch.lines(cm.index, {city: cm.values, "Pakistan average": nm.values}, f"3. {city} compared with Pakistan, month by month",
             colors=["#d64545", "#9aa5b5"], y_title="AQI", widths={city: 3.2}, dashes={"Pakistan average": "dot"})
    ch.note(f"Red = {city}'s monthly average AQI, grey dotted = the average of all cities. **Red above grey means "
            f"{city} is worse than the country.**")

    # 4 calendar
    cal = c.assign(year=c.date.dt.year, doy=c.date.dt.dayofyear)
    years = sorted(cal.year.unique())
    z = np.full((len(years), 366), np.nan)
    txt = np.full((len(years), 366), "", dtype=object)
    for r in cal.itertuples():
        yi = years.index(r.year)
        z[yi, r.doy - 1] = r.us_aqi_avg
        txt[yi, r.doy - 1] = f"{r.date:%d %b %Y}<br>AQI {r.us_aqi_avg:.0f} · {aqi_cat(r.us_aqi_avg)}"
    month_starts = [pd.Timestamp(2001, mo, 1).dayofyear for mo in range(1, 13)]
    edges = [0, 50, 100, 150, 200, 300]
    scale = []
    for (lo, hi_), lab in zip(zip(edges, edges[1:] + [300]), AQI_LABELS[:5]):
        scale += [[lo / 300, AQI_COLORS[lab]], [min(hi_, 300) / 300, AQI_COLORS[lab]]]
    fig = go.Figure(go.Heatmap(z=z, x=list(range(1, 367)), y=[str(y) for y in years], text=txt,
                               hovertemplate="%{text}<extra></extra>", colorscale=scale[:-1] + [[1.0, AQI_COLORS["Very Unhealthy"]]],
                               zmin=0, zmax=300, ygap=5, showscale=False))
    fig.update_xaxes(tickmode="array", tickvals=month_starts, ticktext=list(calendar.month_abbr)[1:])
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=f"4. Every day in {city}, one row per year")
    show(fig, h=140 + 48 * len(years), legend="off")
    ch.note("Each thin stripe is **one day**, coloured by its air-quality category (green = good, yellow = moderate, "
            "orange = unhealthy for sensitive groups, red = unhealthy, purple = very unhealthy or worse).")

    # 5 + 6
    a, b = st.columns(2)
    with a:
        ch.bar([calendar.month_abbr[int(i)] for i in mon.index], mon.values, "5. Which months are worst?",
               horizontal=False, scale="aqi", key_note=False, y_title="average AQI")
        ch.note("Average AQI for each calendar month.")
    with b:
        if hourly is not None and {"city", "hour", "pm2_5_avg"} <= set(hourly.columns) and city in set(hourly.city):
            hh = hourly[hourly.city == city]
            w = hh["samples"] if "samples" in hh.columns else pd.Series(1, index=hh.index)
            blk = (hh.hour // 3).map(lambda i: ch.BLOCKS[int(i)])
            hb = ((hh.pm2_5_avg * w).groupby(blk).sum() / w.groupby(blk).sum()).reindex(ch.BLOCKS)
            ch.bar(hb.index, hb.values, "6. Which hours of the day are worst?", horizontal=False, scale="pm25",
                   key_note=False, y_title="PM2.5 (µg/m³)")
            ch.note(f"Average PM2.5 in each 3-hour block in {city}, all months together. **Lowest bars = best time "
                    f"to be outdoors.**")
        else:
            st.info("The hourly file has no data for this city.")
    ch.legend_note("aqi")

    # 7 + 8
    a, b = st.columns(2)
    with a:
        w_, wl = same_window(c)
        yr = w_.groupby(w_.date.dt.year).us_aqi_avg.mean()
        ch.bar([str(y) for y in yr.index], yr.values, f"7. Year by year ({wl})", horizontal=False, scale="aqi",
               key_note=False, y_title="average AQI")
        ch.note(f"Average AQI for the **same dates ({wl})** in every year, so the latest year compares fairly.")
    with b:
        ch.bar(["Smoke (PM2.5)", "Dust (PM10)", "Ozone"], shares.values, f"8. What makes {city}'s air dirty?",
               scale=[DRIVER_COLORS[k] for k in [SMOKE, DUST, OZONE]], suffix="% of days", key_note=False,
               value_range=[0, 125], h=260)
        ch.note("Share of days on which **smoke (PM2.5)**, **dust (PM10)** or **ozone** was the pollutant that set "
                "the AQI.")

    # 9 + 10
    a, b = st.columns(2)
    with a:
        peers = d[d.province == prov].groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
        ch.bar(peers.index, peers.values, f"9. {city} among the cities of {prov}", scale="aqi", highlight=city,
               key_note=False)
        ch.note(f"Average AQI of every monitored city in {prov}; **{city} is in colour**, the others are grey.")
    with b:
        rows = [(lab, c[col].mean() / lim) for col, (lab, lim) in WHO_24H.items() if col in c.columns]
        rows.sort(key=lambda r: -r[1])
        ch.bar([r[0] for r in rows], [r[1] for r in rows], f"10. {city}: each pollutant vs its WHO limit",
               scale=["#d64545" if r[1] > 1 else "#1e9e5a" for r in rows], fmt="{:.1f}", suffix="×",
               ref=[(1, "safe limit", "#1e9e5a")], key_note=False)
        ch.note("**1× = at the WHO daily safe limit** (green dashed line). Red = above it.")

    with st.expander(f"Table: {city} and the other cities of {prov}"):
        trs = city_trends(full, "pm2_5_avg").set_index("city")
        eps = find_episodes(full, 200, 3)
        pt = d[d.province == prov].groupby("city").agg(avg_aqi=("us_aqi_avg", "mean"), avg_pm25=("pm2_5_avg", "mean"),
                                                       unhealthy=("us_aqi_avg", lambda s: (s > 150).mean() * 100))
        pt["trend"] = trs.reindex(pt.index).pct_per_year
        pt["status"] = trs.reindex(pt.index).status
        pt["episodes"] = eps.groupby("city").size().reindex(pt.index).fillna(0).astype(int)
        pt = pt.sort_values("avg_aqi", ascending=False).round(1)
        pt["avg_aqi"] = pt.avg_aqi.round(0).astype(int)
        pt.index.name = "City"
        pt.columns = ["Average AQI", "Average PM2.5", "% days AQI>150", "PM2.5 trend %/yr", "Trend",
                      "Episodes (3+ days >200)"]
        table(pt)
    download_csv(c.drop(columns=["idx_pm25", "idx_pm10", "idx_o3", "fine_ratio"]),
                 f"{city.lower().replace(' ', '_')}_daily.csv", f"Download {city} daily data (CSV)")


# ============================================================================
# SOURCES & TRENDS  (10 visuals)
#   what drives it: 1 donut of causes   2 cause in each city   3 cause in each month   4 dustiest cities
#                   5 traffic gas (NO2) by city
#   where heading:  6 trend in each city   7 PM2.5 year by year   8 smog season by smog season
#                   9 month by month: first full year vs latest  10 dust year by year
# ============================================================================
def page_sources_trends(dflt, full):
    st.header("Sources & Trends")
    need(full, ["date", "city", "province", "pm2_5_avg", "pm10_avg", "us_aqi_avg"], "pakistan_air_quality_daily")
    if dflt is None or dflt.empty:
        st.warning("No records match the current filters.")
        return
    d = with_drivers(dflt)
    provs = F["provs"] or sorted(full.province.unique())
    sub = full[full.province.isin(provs)]
    tt = city_trends(full, "pm2_5_avg")
    tt = tt[tt.city.isin(sub.city.unique())]
    nat, slope, p, pct = national_trend(sub, "pm2_5_avg")
    share = d.driver.value_counts(normalize=True).reindex([SMOKE, DUST, OZONE]).fillna(0) * 100
    up = int((tt.status == "Rising (clear)").sum())
    seasons, labels = smog_seasons(sub, "pm2_5_avg")
    s_tbl = seasons.groupby("season").pm2_5_avg.mean() if len(labels) else pd.Series(dtype=float)

    kpis([
        ("Days caused by smoke", f"{share[SMOKE]:.0f}%", "fine particles set the AQI"),
        ("Days caused by dust", f"{share[DUST]:.0f}%", "coarse dust set the AQI"),
        ("PM2.5 trend", f"{pct:+.1f}% / yr", "clear" if p < 0.05 else "not statistically clear"),
        ("Cities getting worse", f"{up} of {len(tt)}", "clear rise, seasons removed"),
        ("Smog season change", f"{(s_tbl.iloc[-1] / s_tbl.iloc[0] - 1) * 100:+.0f}%" if len(s_tbl) > 1 else "n/a",
         f"Nov-Jan {labels[-1]} vs {labels[0]}" if len(s_tbl) > 1 else "needs two full seasons"),
    ])
    lines = [f"**Smoke is the main problem**: it set the AQI on **{share[SMOKE]:.0f}%** of city-days, dust on "
             f"**{share[DUST]:.0f}%** and ozone on **{share[OZONE]:.0f}%**." if share[SMOKE] >= 50 else
             f"Dust set the AQI on **{share[DUST]:.0f}%** of city-days and smoke on **{share[SMOKE]:.0f}%**.",
             f"With the seasons removed, PM2.5 is changing by **{pct:+.1f}% a year** "
             f"({'a statistically clear' if p < 0.05 else 'not a statistically clear'} trend); **{up} of {len(tt)}** "
             f"cities are clearly getting worse and none are clearly improving." if (tt.status == "Falling (clear)").sum() == 0
             else f"With the seasons removed, PM2.5 is changing by **{pct:+.1f}% a year**; {up} cities are clearly "
                  f"getting worse and {(tt.status == 'Falling (clear)').sum()} clearly better."]
    insights(lines)

    st.subheader("What causes the pollution?")
    a, b = st.columns(2)
    with a:   # 1
        ch.donut([SMOKE, DUST, OZONE], share.values, "1. What sets the AQI on most days?",
                 colors=[DRIVER_COLORS[k] for k in [SMOKE, DUST, OZONE]], center="all<br>city-days")
        ch.note("For each day we check **which pollutant pushed the AQI highest**: smoke-type fine particles "
                "(PM2.5), coarse dust (PM10) or ozone.")
    with b:   # 3
        mm = (d.groupby(d.date.dt.month).driver.value_counts(normalize=True).unstack(fill_value=0)
              .reindex(columns=[SMOKE, DUST, OZONE], fill_value=0) * 100)
        ch.stacked([calendar.month_abbr[int(i)] for i in mm.index], {k: mm[k].values for k in mm.columns},
                   "2. Does the cause change through the year?", colors=DRIVER_COLORS, h=420)
        ch.note("Each bar is one month (100% of its days). Dust and ozone show up in the hot months; smoke "
                "dominates in winter.")
    # 2
    cc = (d.groupby("city").driver.value_counts(normalize=True).unstack(fill_value=0)
          .reindex(columns=[SMOKE, DUST, OZONE], fill_value=0) * 100).sort_values(SMOKE)
    ch.stacked(list(cc.index), {k: cc[k].values for k in cc.columns}, "3. What causes the pollution in each city?",
               colors=DRIVER_COLORS)
    ch.note("Each bar is 100% of a city's days. **Cities at the top have the most dust or ozone days**; the rest are "
            "almost entirely smoke.")
    a, b = st.columns(2)
    with a:   # 4
        if "dust_avg" in d.columns:
            du = d.groupby("city").dust_avg.mean().sort_values(ascending=False).head(F["top_n"])
            ch.bar(du.index, du.values, f"4. The {len(du)} dustiest cities", scale="#c8913a", key_note=False,
                   suffix=" µg/m³")
            ch.note("Average amount of desert dust in the air near the ground.")
    with b:   # 5
        if "no2_avg" in d.columns:
            no = d.groupby("city").no2_avg.mean().sort_values(ascending=False).head(F["top_n"])
            ch.bar(no.index, no.values, "5. Where is traffic pollution highest?", scale="#2a78d6", key_note=False,
                   fmt="{:.0f}", suffix=" µg/m³", ref=[(25, "WHO daily limit", "#1e9e5a")])
            ch.note("Average nitrogen dioxide (NO₂), a gas that comes mostly from vehicle exhaust and power "
                    "generation. The green dashed line is the WHO daily safe limit (25 µg/m³).")

    st.subheader("Is it getting better or worse?")
    st.caption("This part uses every month for the provinces selected in the sidebar; year, month, season and "
               "category filters are ignored because a trend needs the whole time series.")
    # 6
    t = tt.sort_values("pct_per_year", ascending=False)
    ch.bar(t.city, t.pct_per_year.values, "6. How fast is PM2.5 changing in each city?",
           scale=[TREND_COLORS[s_] for s_ in t.status], fmt="{:+.1f}", suffix="% / yr", key_note=False,
           value_range=[min(0, float(t.pct_per_year.min()) * 1.3), float(t.pct_per_year.max()) * 1.3])
    ch.note("Yearly change with the normal seasonal ups and downs removed. **Red = clearly getting worse**, grey = "
            "change too small or uneven to be sure, green = clearly improving.")
    a, b = st.columns(2)
    w, wl = same_window(sub)
    with a:   # 7
        yr = w.groupby(w.date.dt.year).pm2_5_avg.mean()
        ch.bar([str(y) for y in yr.index], yr.values, f"7. PM2.5 year by year ({wl})", horizontal=False,
               scale="pm25", key_note=False, fmt="{:.1f}", y_title="PM2.5 (µg/m³)")
        ch.note(f"Average PM2.5 of the selected cities over the **same dates ({wl})** in each year.")
    with b:   # 10
        if "dust_avg" in w.columns:
            dy = w.groupby(w.date.dt.year).dust_avg.mean()
            ch.bar([str(y) for y in dy.index], dy.values, f"8. Desert dust year by year ({wl})", horizontal=False,
                   scale="#c8913a", key_note=False, fmt="{:.0f}", y_title="dust (µg/m³)")
            ch.note("Average desert dust over the same dates each year. If this rises together with PM2.5, part of "
                    "the rise is dust rather than smoke.")
    a, b = st.columns(2)
    with a:   # 8
        if len(labels) > 1:
            top = sub.groupby("city").pm2_5_avg.mean().nlargest(8).index
            g = seasons[seasons.city.isin(top)].groupby(["city", "season"]).pm2_5_avg.mean().unstack()
            g = g.reindex(top)
            ch.grouped(list(g.index), {s_: g[s_].values for s_ in labels}, "9. Smog season after smog season",
                       colors=["#c3ccd8", "#7a8496", "#1b2a41", "#000000"], horizontal=True)
            ch.note("Average PM2.5 from November to January in each complete smog season, for the 8 most polluted "
                    "cities. **Darker bar = more recent season.**")
    with b:   # 9
        yrs_full = [y for y, n in sub.groupby(sub.date.dt.year).date.nunique().items() if n >= 365]
        if len(yrs_full) >= 2:
            y0, y1 = yrs_full[0], yrs_full[-1]
            mo = sub[sub.date.dt.year.isin([y0, y1])].groupby([sub.date.dt.year, sub.date.dt.month]).pm2_5_avg.mean()
            ch.grouped([calendar.month_abbr[m] for m in range(1, 13)],
                       {str(y0): [mo.get((y0, m), np.nan) for m in range(1, 13)],
                        str(y1): [mo.get((y1, m), np.nan) for m in range(1, 13)]},
                       f"10. Which months got worse? {y0} vs {y1}", colors=["#c3ccd8", "#d64545"],
                       y_title="PM2.5 (µg/m³)", h=420)
            ch.note(f"Average PM2.5 in each month of {y0} (light) and {y1} (red), the first and latest complete years.")
    st.caption("Method: the cause of a day is the pollutant with the highest US AQI sub-index (US EPA 2024 "
               "breakpoints) from daily averages of PM2.5, PM10 and ozone. Trends: monthly averages minus each city's "
               "usual level for that month; Theil-Sen slope; Mann-Kendall test corrected for month-to-month "
               "persistence (clear = p < 0.05). The record is under four years and comes from a model, so trends are "
               "indicative.")


# ============================================================================
# POLLUTION EPISODES  (10 visuals)
#   1 timeline of episodes        2 cities in a bad spell each day      3 days in episodes per city
#   4 month episodes start        5 episodes per winter                  6 smog / dust / ozone split
#   7 the 10 longest              8 the 10 most intense                  9 how long episodes usually last
#  10 normal days vs episode days, per city
# ============================================================================
def page_episodes(full):
    st.header("Pollution Episodes")
    need(full, ["date", "city", "province", "pm2_5_avg", "pm10_avg", "us_aqi_avg"], "pakistan_air_quality_daily")
    st.caption("An episode (bad spell) is a run of days in a row above the AQI level you choose below.")
    c1, c2 = st.columns(2)
    level = c1.selectbox("Daily AQI above", [150, 200, 300], index=1,
                         format_func=lambda v: f"{v} ({aqi_cat(v + 1)})", key="ep_level")
    min_days = c2.slider("Minimum length (days)", 2, 10, 3, key="ep_min")
    sub = full[full.province.isin(F["provs"] or full.province.unique())]
    if F["years"]:
        sub = sub[sub.date.dt.year.isin(F["years"])]
    if sub.empty:
        st.warning("No data for the selected provinces and years.")
        return
    eps = find_episodes(sub, level, min_days)
    if eps.empty:
        st.info("No episodes at this level and length. Try a lower AQI level or fewer days.")
        return
    longest, worst = eps.loc[eps.days.idxmax()], eps.loc[eps.peak_aqi.idxmax()]
    tc = eps.type.value_counts()
    kpis([
        ("Episodes", f"{len(eps)}", f"in {eps.city.nunique()} cities"),
        ("Days in episodes", f"{int(eps.days.sum()):,}", f"city-days above AQI {level}"),
        ("Longest", f"{int(longest.days)} days", f"{longest.city} · {longest.start:%b %Y}"),
        ("Highest peak", f"{worst.peak_aqi:.0f}" + ("*" if worst.peak_aqi > 500 else ""),
         f"{worst.city} · {worst.peak_date:%d %b %Y}"),
        ("Smog / dust / ozone", f"{tc.get('Smog', 0)} / {tc.get('Dust', 0)} / {tc.get('Ozone', 0)}",
         "episodes by main cause"),
    ])
    by_city = eps.groupby("city").days.sum().sort_values(ascending=False)
    start_m = eps.groupby(eps.start.dt.month).size()
    lines = [f"**{by_city.index[0]}** spent the most days in bad spells (**{int(by_city.iloc[0])}** days).",
             f"Most episodes begin in **{calendar.month_name[int(start_m.idxmax())]}**."]
    sm = eps[eps.type == "Smog"]
    if len(sm):
        sl = sm.loc[sm.days.idxmax()]
        lines.append(f"The longest **smog** spell was in **{sl.city}**: {int(sl.days)} days "
                     f"({_fmt_range(sl.start, sl.end)}).")
    du = eps[eps.type == "Dust"]
    if len(du):
        vc = du.city.value_counts()
        main = vc[vc >= 2].index.tolist()[:3] or vc.index.tolist()[:3]
        lines.append(f"**{len(du)}** episodes were caused by dust, mostly in **" + ", ".join(main) + "**.")
    insights(lines)

    # 1
    order = by_city.index.tolist()
    fig = px.timeline(eps.assign(end_plus=eps.end + pd.Timedelta(days=1)), x_start="start", x_end="end_plus", y="city",
                      color="type", color_discrete_map=EP_COLORS,
                      hover_data={"days": True, "peak_aqi": ":.0f", "end_plus": False},
                      category_orders={"city": order, "type": list(EP_COLORS)},
                      title=f"1. When did the bad spells happen? (AQI above {level} for {min_days}+ days)",
                      labels={"type": "", "city": "", "peak_aqi": "peak AQI"})
    fig.update_yaxes(dtick=1)
    show(fig, h=max(320, 22 * len(order) + 140), legend="top")
    ch.note("Each block is one bad spell, from its first to its last day. **Grey = smog, amber = dust, teal = ozone.** "
            "Blocks lining up across many cities at the same time are country-wide smog events.")

    # 2
    daily = sub[sub.us_aqi_avg > level].groupby("date").city.nunique()
    daily = daily.reindex(pd.date_range(sub.date.min(), sub.date.max()), fill_value=0)
    fig = go.Figure(go.Scatter(x=daily.index, y=daily.values, mode="lines", fill="tozeroy",
                               line=dict(color="#d64545", width=1)))
    fig.update_layout(title=f"2. How many cities were above AQI {level} on each day?")
    fig.update_yaxes(title_text="cities")
    show(fig, h=320, legend="off")
    ch.note("The taller the red area, the more cities had very bad air on that day.")

    a, b = st.columns(2)
    with a:   # 3
        ch.bar(by_city.index, by_city.values, "3. Total days spent in bad spells, per city", scale="#d64545",
               key_note=False)
        ch.note("All episode days added up for each city.")
    with b:   # 4
        sm_ = start_m.reindex(range(1, 13), fill_value=0)
        ch.bar([calendar.month_abbr[m] for m in sm_.index], sm_.values, "4. In which month do bad spells start?",
               horizontal=False, scale="#7a8496", key_note=False, y_title="episodes")
        ch.note("Number of episodes that began in each calendar month.")
        # 5
        win = eps.assign(w=np.where(eps.start.dt.month >= 7, eps.start.dt.year, eps.start.dt.year - 1))
        wc = win.groupby("w").size()
        ch.bar([f"{y}-{str(y + 1)[-2:]}" for y in wc.index], wc.values, "5. Bad spells per year (July to June)",
               horizontal=False, scale="#5b6b82", key_note=False, y_title="episodes", h=320)
        ch.note("Counted from July to June so each winter smog season stays in one year. The first and last years "
                "may be incomplete.")
    a, b = st.columns(2)
    with a:   # 6
        ch.donut(list(EP_COLORS), [tc.get(k, 0) for k in EP_COLORS], "6. What caused the bad spells?",
                 colors=list(EP_COLORS.values()), center=f"{len(eps)}<br>episodes", pct=True)
        ch.note("Smog = fine smoke particles, dust = coarse desert dust, ozone = ozone gas.")
    with b:   # 9
        lb = pd.cut(eps.days, [0, 3, 5, 10, 20, 1000], labels=["3 days or less", "4-5 days", "6-10 days",
                                                             "11-20 days", "Over 20 days"]).value_counts()
        lb = lb.reindex(["3 days or less", "4-5 days", "6-10 days", "11-20 days", "Over 20 days"]).fillna(0)
        ch.bar(lb.index, lb.values, "7. How long does a bad spell usually last?", horizontal=False, scale="#7c5cbf",
               key_note=False, y_title="episodes")
        ch.note("Number of episodes by length. Most are short; a few winter smog spells last weeks.")
    a, b = st.columns(2)
    with a:   # 7
        l10 = eps.nlargest(10, "days")
        ch.bar([f"{r.city} · {r.start:%b %Y}" for r in l10.itertuples()], l10.days.values,
               "8. The 10 longest bad spells", scale=[EP_COLORS[t_] for t_ in l10.type], suffix=" days", key_note=False)
        ch.note("Bar colour shows the cause (grey smog, amber dust, teal ozone).")
    with b:   # 8
        p10 = eps.nlargest(10, "peak_aqi")
        ch.bar([f"{r.city} · {r.peak_date:%d %b %Y}" for r in p10.itertuples()], p10.peak_aqi.values,
               "9. The 10 most intense bad spells", scale="aqi", key_note=False,
               text=[f"{v:.0f}" + ("*" if v > 500 else "") for v in p10.peak_aqi.values])
        ch.note("Highest single-day AQI reached during the episode. * = above the top of the 500 scale (dust).")

    # 10
    top = by_city.head(8).index
    in_ep = set()
    for r in eps[eps.city.isin(top)].itertuples():
        for dd in pd.date_range(r.start, r.end):
            in_ep.add((r.city, dd))
    s8 = sub[sub.city.isin(top)].copy()
    s8["ep"] = [(cc, dd) in in_ep for cc, dd in zip(s8.city, s8.date)]
    cmp_ = s8.groupby(["city", "ep"]).us_aqi_avg.mean().unstack().reindex(top)
    ch.grouped(list(cmp_.index), {"Normal days": cmp_.get(False, pd.Series(np.nan, index=top)).values,
                                  "Days in a bad spell": cmp_.get(True, pd.Series(np.nan, index=top)).values},
               "10. How much worse is the air during a bad spell?", colors=["#9aa5b5", "#d64545"], y_title="average AQI")
    ch.note("For the 8 cities with the most episode days: average AQI on normal days (grey) and during bad spells "
            "(red).")

    st.subheader("All episodes")
    out = eps.sort_values(["days", "peak_aqi"], ascending=False)
    view = pd.DataFrame({
        "City": out.city, "Province": out.province, "Cause": out.type,
        "Start": out.start.dt.strftime("%d %b %Y"), "End": out.end.dt.strftime("%d %b %Y"), "Days": out.days,
        "Peak AQI": out.peak_aqi.round(0).astype(int), "Peak date": out.peak_date.dt.strftime("%d %b %Y"),
        "Avg AQI": out.avg_aqi.round(0).astype(int), "Avg PM2.5": out.avg_pm25.round(0).astype(int),
        "Avg PM10": out.avg_pm10.round(0).astype(int)})
    table(view.reset_index(drop=True), hide_index=True)
    download_csv(view, f"aqi_episodes_above_{level}.csv", "Download the episode list (CSV)")
