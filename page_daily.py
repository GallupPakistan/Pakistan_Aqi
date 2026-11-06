"""
page_daily.py - everything built from  pakistan_air_quality_daily.csv
    * page_overview()  -> "Overview" page
    * page_daily()     -> "Daily Air Quality" page
    * page_forecast()  -> "Forecasting" page
"""
import calendar

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from common import (AQI_BINS, AQI_COLORS, AQI_LABELS, ATM, F, WHO_PM25_24H, aqi_cat, explain, insights, kpis,
                    need, show)

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HAS_SM = True
except Exception:
    HAS_SM = False


# ----------------------------------------------------------------------------
# OVERVIEW
# ----------------------------------------------------------------------------
def page_overview(daily, hourly, cities):
    st.header("What is the Air Quality Analytics Dashboard?")
    if daily is None:
        st.info("Load the daily air-quality file from the sidebar to see the scope of the data.")
    else:
        n, nc = len(daily), daily.city.nunique()
        npv = daily.province.nunique() if "province" in daily.columns else 0
        d0, d1 = daily.date.min(), daily.date.max()
        st.write(f"Air quality shapes health, daily life and public policy in Pakistan, but the numbers are spread "
                 f"across many files and measures. This dashboard brings together **{n:,} daily records** for "
                 f"**{nc} cities** across **{npv} provinces**, from **{d0:%d %b %Y}** to **{d1:%d %b %Y}**. Each "
                 f"record combines pollutant levels, the US AQI and weather conditions, giving a structured "
                 f"view of air quality across the country.")
        kpis([
            ("Daily records", f"{n:,}", "city-days"),
            ("Cities", f"{nc}", "monitored"),
            ("Provinces", f"{npv}", "covered"),
            ("Period", f"{(d1 - d0).days + 1:,} days", f"{d0:%b %Y} to {d1:%b %Y}"),
            ("Average US AQI", f"{daily.us_aqi_avg.mean():.0f}", aqi_cat(daily.us_aqi_avg.mean())),
        ])
    st.markdown(
        '<div class="igrid">'
        '<div class="ic"><div class="it">Explore the data</div><div class="ib">Filter by province, city, season, '
        'month and AQI category to see which cities are worst, how pollution changed over the year, and how the '
        'hour of the day and the weather shape it.</div></div>'
        '<div class="ic"><div class="it">Stay informed</div><div class="ib">Compare cities side by side, spot '
        'smog-season patterns, check the hours when pollution peaks, and use the Forecasting page to see what '
        'the coming weeks may look like for any city.</div></div>'
        '<div class="ic"><div class="it">Who can use it</div><div class="ib">Journalists, researchers, '
        'policymakers, health planners and students who need clear, evidence-based figures on air quality and '
        'its impact on public health, all in one place.</div></div>'
        '</div>', unsafe_allow_html=True)
    if daily is not None:
        st.subheader("Highlights")
        city_aqi = daily.groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
        m = daily.groupby(daily.date.dt.month).us_aqi_avg.mean()
        insights([
            f"**{city_aqi.index[0]}** has the highest average AQI ({city_aqi.iloc[0]:.0f}); "
            f"**{city_aqi.index[-1]}** the lowest ({city_aqi.iloc[-1]:.0f}).",
            f"Air quality is worst in **{calendar.month_name[int(m.idxmax())]}** and best in "
            f"**{calendar.month_name[int(m.idxmin())]}**.",
            f"**{(daily.us_aqi_avg > 150).mean() * 100:.1f}%** of city-days were Unhealthy or worse (AQI above 150).",
        ])
        c4, c5 = st.columns(2)
        with c4:
            t = daily.assign(ym=daily.date.dt.to_period("M").dt.to_timestamp()).groupby("ym").us_aqi_avg.mean().reset_index()
            show(px.line(t, x="ym", y="us_aqi_avg", title="National monthly average US AQI",
                         labels={"ym": "", "us_aqi_avg": "US AQI"}), h=320)
        with c5:
            t = city_aqi.head(F["top_n"]).reset_index()
            show(px.bar(t.sort_values("us_aqi_avg"), x="us_aqi_avg", y="city", orientation="h",
                        title="Average US AQI by city", labels={"us_aqi_avg": "US AQI", "city": ""}), h=320)

        c6, c7, c8 = st.columns(3)
        with c6:
            g = daily.assign(cat=pd.cut(daily.us_aqi_avg, AQI_BINS, labels=AQI_LABELS)).dropna(subset=["cat"])
            t = g.groupby("cat", observed=True).size().reset_index(name="days")
            t["pct"] = t.days / t.days.sum() * 100
            fig = go.Figure(go.Pie(labels=[f"{c} ({p:.1f}%)" for c, p in zip(t.cat, t.pct)], values=t.days,
                                   hole=0.55, sort=False, marker=dict(colors=[AQI_COLORS[c] for c in t.cat]),
                                   textinfo="percent", textposition="inside"))
            fig.update_layout(title="Share of days by AQI category", uniformtext=dict(minsize=11, mode="hide"))
            show(fig, h=380, legend="bottom")
        with c7:
            if "province" in daily.columns:
                t = daily.groupby("province").us_aqi_avg.mean().reset_index().sort_values("us_aqi_avg")
                fig = px.bar(t, x="us_aqi_avg", y="province", orientation="h", color="us_aqi_avg",
                             color_continuous_scale="YlOrRd", text_auto=".0f",
                             title="Average US AQI by province", labels={"us_aqi_avg": "US AQI", "province": ""})
                fig.update_coloraxes(showscale=False)
                show(fig, h=380, legend="off")
        with c8:
            t = daily.groupby(daily.date.dt.month).us_aqi_avg.mean().reset_index()
            t["month"] = t.date.map(lambda x: calendar.month_abbr[int(x)])
            fig = px.bar(t, x="month", y="us_aqi_avg", color="us_aqi_avg", color_continuous_scale="YlOrRd",
                         title="Average US AQI by month of year", labels={"us_aqi_avg": "US AQI", "month": ""})
            fig.update_coloraxes(showscale=False)
            show(fig, h=380, legend="off")


# ----------------------------------------------------------------------------
# DAILY AIR QUALITY
# ----------------------------------------------------------------------------
def page_daily(df):
    st.header("Daily Air Quality & Weather")
    need(df, ["date", "city", "province", "pm2_5_avg", "us_aqi_avg", "season"], "pakistan_air_quality_daily")

    f = df
    top_cities = f.groupby("city").us_aqi_avg.mean().nlargest(F["top_n"]).index.tolist()
    if f.empty:
        st.warning("No data for the selected filters.")
        return

    # ---- KPIs
    city_aqi = f.groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
    worst = f.loc[f.us_aqi_avg.idxmax()]
    pct_bad = (f.us_aqi_avg > 150).mean() * 100
    pm = f.pm2_5_avg.mean()
    kpis([
        ("Average US AQI", f"{f.us_aqi_avg.mean():.0f}", aqi_cat(f.us_aqi_avg.mean())),
        ("Average PM2.5", f"{pm:.1f} µg/m³", f"{pm / WHO_PM25_24H:.1f}× WHO guideline"),
        ("Unhealthy days (AQI>150)", f"{pct_bad:.1f}%", f"{int((f.us_aqi_avg > 150).sum()):,} city-days"),
        ("Most polluted city", city_aqi.index[0], f"avg AQI {city_aqi.iloc[0]:.0f}"),
        ("Worst day on record", f"{worst.us_aqi_avg:.0f} AQI", f"{worst.city} · {worst.date:%d %b %Y}"),
    ])

    # ---- Insights
    ins = []
    s = f.groupby("season").pm2_5_avg.mean().sort_values(ascending=False)
    if len(s) > 1:
        ins.append(f"**{s.index[0]}** is the most polluted season (PM2.5 {s.iloc[0]:.0f} µg/m³), "
                   f"{s.iloc[0] / s.iloc[-1]:.1f}× higher than **{s.index[-1]}**.")
    m = f.groupby(f.date.dt.month).pm2_5_avg.mean()
    ins.append(f"Peak month is **{calendar.month_name[int(m.idxmax())]}**, cleanest is "
               f"**{calendar.month_name[int(m.idxmin())]}**.")
    if "rain_day" in f.columns and f.rain_day.nunique() > 1:
        r = f.groupby("rain_day").pm2_5_avg.mean()
        if {"Yes", "No"} <= set(r.index):
            ins.append(f"Rainy days have **{(1 - r['Yes'] / r['No']) * 100:.0f}% lower** PM2.5 than dry days.")
    if "wind_category" in f.columns:
        w = f.groupby("wind_category").pm2_5_avg.mean().sort_values(ascending=False)
        if len(w) > 1:
            ins.append(f"Wind condition **{w.index[0]}** carries the highest PM2.5 ({w.iloc[0]:.0f} µg/m³).")
    yr = f.groupby(f.date.dt.year).pm2_5_avg.mean()
    if len(yr) > 1:
        ch = (yr.iloc[-1] / yr.iloc[-2] - 1) * 100
        ins.append(f"PM2.5 in {yr.index[-1]} vs {yr.index[-2]}: **{ch:+.1f}%** (check for partial years).")
    insights(ins)

    # ---- Charts
    f = f.assign(ym=f.date.dt.to_period("M").dt.to_timestamp())
    c1, c2 = st.columns(2)
    with c1:
        t = f.groupby(["ym", "city"]).us_aqi_avg.mean().reset_index()
        if F["trend_cities"]:
            t = t[t.city.isin(F["trend_cities"])]
        show(px.line(t, x="ym", y="us_aqi_avg", color="city", title="Monthly average US AQI by city",
                     labels={"ym": "", "us_aqi_avg": "US AQI"}))
    with c2:
        t = f.groupby(["city", "province"]).pm2_5_avg.mean().reset_index().sort_values("pm2_5_avg")
        t = t[t.city.isin(top_cities)]
        fig = px.bar(t, x="pm2_5_avg", y="city", color="province", orientation="h",
                     title="City ranking: average PM2.5 (µg/m³)", labels={"pm2_5_avg": "PM2.5", "city": ""})
        fig.add_vline(x=WHO_PM25_24H, line_dash="dash", annotation_text="WHO guideline")
        show(fig)

    c3, c4 = st.columns(2)
    with c3:
        show(px.box(f, x="season", y="pm2_5_avg", color="season", points=False,
                    title="PM2.5 distribution by season", labels={"pm2_5_avg": "PM2.5", "season": ""}),
             legend="off")
    with c4:
        pv = f.pivot_table(index="city", columns=f.date.dt.month, values="us_aqi_avg", aggfunc="mean")
        pv = pv.loc[pv.index.isin(top_cities)]
        pv.columns = [calendar.month_abbr[int(c)] for c in pv.columns]
        show(px.imshow(pv, color_continuous_scale="YlOrRd", aspect="auto", text_auto=".0f",
                       title="Average US AQI: city × month heatmap"))

    num = [c for c in ["pm2_5_avg", "pm10_avg", "co_avg", "no2_avg", "so2_avg", "ozone_avg", "dust_avg",
                       "aod_avg", "us_aqi_avg", "temp_avg_c", "humidity_avg", "wind_avg_kmh", "rain_mm"]
           if c in f.columns]
    corr = f[num].corr()
    show(px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto",
                   title="What drives pollution? Correlation of pollutants & weather"), h=480)

    st.subheader("Which AQI categories dominate each city?")
    g = f.assign(cat=pd.cut(f.us_aqi_avg, AQI_BINS, labels=AQI_LABELS)).dropna(subset=["cat"])
    g = g[g.city.isin(top_cities)]
    t = g.groupby(["city", "cat"], observed=True).size().reset_index(name="days")
    t["share"] = t.days / t.groupby("city").days.transform("sum") * 100
    show(px.bar(t, x="share", y="city", color="cat", orientation="h", color_discrete_map=AQI_COLORS,
                category_orders={"cat": AQI_LABELS}, title="Share of days by AQI category (%)",
                labels={"share": "% of days", "city": "", "cat": "AQI category"}))

    st.subheader("Compare two cities")
    opts = sorted(f.city.unique())
    if len(opts) >= 2:
        a, b = st.columns(2)
        ca = a.selectbox("City A", opts, index=0)
        cb = b.selectbox("City B", opts, index=1)
        two = f[f.city.isin([ca, cb])]
        cmp = two.groupby([two.date.dt.to_period("M").dt.to_timestamp().rename("month"), "city"]).us_aqi_avg.mean().reset_index()
        show(px.line(cmp, x="month", y="us_aqi_avg", color="city", title=f"{ca} vs {cb}: monthly average US AQI",
                     labels={"us_aqi_avg": "US AQI", "month": ""}), h=340)
        summ = two.groupby("city").agg(avg_aqi=("us_aqi_avg", "mean"), avg_pm25=("pm2_5_avg", "mean"),
                                        unhealthy_pct=("us_aqi_avg", lambda s: (s > 150).mean() * 100),
                                        days=("date", "count")).round(1)
        st.dataframe(summ, use_container_width=True)
    else:
        st.info("Select at least two cities in the filters to compare them.")


# ----------------------------------------------------------------------------
# FORECASTING (uses the FULL daily history, not the sidebar-filtered data)
# ----------------------------------------------------------------------------
def _fourier(idx, k=3):
    doy = idx.dayofyear.values
    cols = []
    for i in range(1, k + 1):
        cols += [np.sin(2 * np.pi * i * doy / 365.25), np.cos(2 * np.pi * i * doy / 365.25)]
    return np.column_stack(cols)


def _future_index(train, h):
    return pd.date_range(train.index[-1] + pd.Timedelta(days=1), periods=h, freq="D")


def m_regression(train, h):
    """Linear trend + annual Fourier seasonality + weekday effect (least squares)."""
    def X(idx):
        t = ((idx - train.index[0]).days.values) / 365.25
        parts = [np.ones(len(idx)), t, *[(idx.weekday == d).astype(float) for d in range(1, 7)]]
        if len(train) >= 300:
            parts.append(_fourier(idx))
        return np.column_stack(parts)
    beta, *_ = np.linalg.lstsq(X(train.index), train.values, rcond=None)
    fut = _future_index(train, h)
    return pd.Series(np.clip(X(fut) @ beta, 0, None), index=fut)


def m_holt_winters(train, h):
    """Damped-trend Holt-Winters with weekly seasonality (statsmodels)."""
    fit = ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal="add",
                               seasonal_periods=7).fit()
    fut = _future_index(train, h)
    return pd.Series(np.clip(np.asarray(fit.forecast(h)), 0, None), index=fut)


def m_climatology(train, h):
    """Day-of-year average across past years + decaying recent anomaly. Best for smog seasonality."""
    d = train.groupby(train.index.dayofyear).mean().reindex(range(1, 367)).interpolate(limit_direction="both")
    ext = pd.concat([d.iloc[-15:], d, d.iloc[:15]])
    sm = ext.rolling(15, center=True, min_periods=1).mean().iloc[15:-15]
    sm.index = range(1, 367)
    fut = _future_index(train, h)
    base = sm.reindex(fut.dayofyear).values
    rec = train.iloc[-14:]
    anom = (rec.values - sm.reindex(rec.index.dayofyear).values).mean()
    return pd.Series(np.clip(base + anom * np.exp(-np.arange(1, h + 1) / 10), 0, None), index=fut)


def b_recent_avg(train, h):
    """Simple baseline: every future day equals the average of the last 7 days."""
    return pd.Series(train.iloc[-7:].mean(), index=_future_index(train, h))


def b_last_year(train, h):
    """Simple baseline: every future day equals the same date one year earlier."""
    fut = _future_index(train, h)
    p = pd.Series(train.reindex(fut - pd.Timedelta(days=365)).values, index=fut)
    return p.fillna(train.iloc[-7:].mean()) if p.notna().any() else p


MODELS = {"Seasonal Regression (trend + annual + weekday)": m_regression,
          "Climatology + recent anomaly (smog-season aware)": m_climatology}
if HAS_SM:
    MODELS["Holt-Winters (damped trend, weekly)"] = m_holt_winters
BASELINES = {"Baseline: recent 7-day average": b_recent_avg,
             "Baseline: same dates last year": b_last_year}
METRIC_LABELS = {"us_aqi_avg": "US AQI", "pm2_5_avg": "PM2.5 (µg/m³)", "pm10_avg": "PM10 (µg/m³)",
                 "no2_avg": "Nitrogen dioxide", "ozone_avg": "Ozone", "temp_avg_c": "Temperature (°C)",
                 "humidity_avg": "Humidity (%)"}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def build_series(df, city, metric):
    f = df if city == "All cities (average)" else df[df.city == city]
    s = f.groupby("date")[metric].mean().sort_index()
    return s.asfreq("D").interpolate(limit=7).ffill().bfill()


def backtest(s, hold):
    """Hide the last `hold` days, forecast them with every method, and score against reality."""
    train, test = s.iloc[:-hold], s.iloc[-hold:]
    rows, preds = [], {}
    jobs = [(n, f, "Model") for n, f in MODELS.items()] + [(n, f, "Baseline") for n, f in BASELINES.items()]
    for name, fn, kind in jobs:
        try:
            p = fn(train, hold)
            if p.isna().all():
                continue
            e = p.values - test.values
            rows.append(dict(name=name, Type=kind, MAE=np.abs(e).mean(), RMSE=np.sqrt((e ** 2).mean()),
                             MAPE=np.mean(np.abs(e) / np.maximum(test.values, 1)) * 100, Bias=e.mean()))
            preds[name] = p
        except Exception:
            pass
    tbl = pd.DataFrame(rows).set_index("name").sort_values("MAE") if rows else pd.DataFrame()
    return tbl, preds, test


def verdict(tbl, name, level):
    mae = float(tbl.loc[name, "MAE"])
    pct = mae / max(level, 1e-9) * 100
    base = tbl[tbl["Type"] == "Baseline"]
    skill = (1 - mae / base["MAE"].min()) * 100 if len(base) else None
    best_base = base.index[0] if len(base) else None
    if pct < 15 and (skill is None or skill > 10):
        grade, color = "Reliable", "#1e9e5a"
    elif pct < 30 and (skill is None or skill > 0):
        grade, color = "Usable, with care", "#d98e04"
    else:
        grade, color = "Weak: treat as a rough guide only", "#d64545"
    return grade, color, pct, skill, best_base


def calendar_heat(pred, title, h=None):
    d = pd.DataFrame({"date": pred.index, "v": pred.values})
    d["wd"] = d.date.dt.weekday
    d["wk"] = d.date - pd.to_timedelta(d.wd, unit="D")
    z = d.pivot(index="wk", columns="wd", values="v").reindex(columns=range(7))
    txt = z.round(0).astype("Int64").astype(str).replace("<NA>", "")
    fig = go.Figure(go.Heatmap(z=z.values, x=WEEKDAYS, y=[f"Week of {w:%d %b}" for w in z.index],
                               text=txt.values, texttemplate="%{text}", colorscale="YlOrRd",
                               hoverongaps=False, xgap=3, ygap=3, colorbar=dict(thickness=12)))
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(title=title)
    show(fig, h=h or max(280, 46 * len(z) + 110))


def page_forecast(df):
    st.header("Forecasting")
    st.caption("Estimate how air quality is likely to move over the coming days or weeks, based on what happened before.")
    need(df, ["date", "city", "us_aqi_avg", "pm2_5_avg"], "pakistan_air_quality_daily")
    if not HAS_SM:
        st.caption("Tip: install `statsmodels` to unlock the Holt-Winters method.")

    with st.expander("How to read this page (simple guide)"):
        st.markdown("""
**Days ahead (forecast horizon)** is how far into the future you want to look. 7 means next week, 30 means next month.
The further ahead, the less certain the forecast, which is why the shaded range widens.

**Test on last N days (backtest window)** is how the page checks itself. It hides the last N days of real data,
forecasts them, and compares the forecast with what really happened.

**MAE** is the average miss, in the same units as the metric (for AQI, points). Lower is better.

**Baselines** are very simple guesses, such as "same as the last 7 days". A method is only worth trusting if it beats them.
""")

    st.markdown("##### Choose what to forecast")
    metrics = [m for m in METRIC_LABELS if m in df.columns]
    c1, c2, c3, c4 = st.columns(4)
    city = c1.selectbox("City", ["All cities (average)"] + sorted(df.city.unique()))
    metric = c2.selectbox("Measure", metrics, format_func=lambda m: METRIC_LABELS[m])
    horizon = c3.slider("Days ahead (forecast horizon)", 7, 180, 30,
                        help="How many days into the future to predict.")
    hold = c4.slider("Test on last N days (backtest window)", 14, 90, 30,
                     help="Number of recent days hidden from the models to test how accurate they are.")
    label = METRIC_LABELS[metric]

    s = build_series(df, city, metric)
    if len(s) < hold + 60:
        st.warning("Not enough history for this selection. Try a shorter backtest window or another city.")
        return
    tbl, preds, test = backtest(s, hold)
    ok = [n for n in tbl.index if n in MODELS]
    if not ok:
        st.error("No forecasting method could be fitted on this series.")
        return
    model_name = st.selectbox("Forecasting method (best performer first)", ok,
                              help="Methods are ranked by their average error on the test days.")
    pred = MODELS[model_name](s, horizon)
    rmse = float(tbl.loc[model_name, "RMSE"])
    width = 1.96 * rmse * np.sqrt(1 + np.arange(horizon) / max(hold, 1) * 0.15)
    lo, hi = np.clip(pred.values - width, 0, None), pred.values + width
    is_aqi = metric == "us_aqi_avg"
    if is_aqi:
        ATM["aqi"], ATM["src"] = float(pred.mean()), "forecast"
        st.session_state["forecast_aqi"] = ATM["aqi"]

    t1, t2, t3, t4 = st.tabs(["Forecast", "Is the model any good?", "Patterns and outlook", "All cities"])

    # ------------------------------------------------------------ tab 1
    with t1:
        pk = pred.idxmax()
        kpis([
            ("Tomorrow", f"{pred.iloc[0]:.0f}", aqi_cat(pred.iloc[0]) if is_aqi else label),
            (f"Average, next {horizon} days", f"{pred.mean():.0f}",
             f"{(pred.mean() / s.iloc[-horizon:].mean() - 1) * 100:+.0f}% vs the last {horizon} days"),
            ("Expected peak", f"{pred.max():.0f}", f"on {pk:%d %b %Y}"),
            ("Peak-day category" if is_aqi else "Expected low", aqi_cat(pred.max()) if is_aqi else f"{pred.min():.0f}",
             "US AQI band" if is_aqi else f"on {pred.idxmin():%d %b %Y}"),
            ("Typical miss (MAE)", f"{tbl.loc[model_name, 'MAE']:.1f}", f"on the last {hold} test days"),
        ])
        hist = s.iloc[-max(180, horizon * 2):]
        fig = go.Figure()
        if is_aqi:
            ymax = max(hi.max(), hist.max()) * 1.12
            for lo_b, hi_b, lab in zip([0, 50, 100, 150, 200, 300], [50, 100, 150, 200, 300, 500], AQI_LABELS):
                if lo_b < ymax:
                    fig.add_hrect(y0=lo_b, y1=min(hi_b, ymax), fillcolor=AQI_COLORS[lab], opacity=0.10,
                                  line_width=0, annotation_text=lab, annotation_position="top left",
                                  annotation_font_size=10)
            fig.update_yaxes(range=[0, ymax])
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, name="Past (real data)", line=dict(color="#2a78d6")))
        fig.add_trace(go.Scatter(x=pred.index, y=hi, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=pred.index, y=lo, fill="tonexty", fillcolor="rgba(235,104,52,.20)",
                                 line=dict(width=0), name="Likely range (95%)"))
        ly = s.reindex(pred.index - pd.Timedelta(days=365))
        if ly.notna().any():
            fig.add_trace(go.Scatter(x=pred.index, y=ly.values, name="Same dates last year",
                                     line=dict(color="#8a94a6", dash="dot", width=1.6)))
        fig.add_trace(go.Scatter(x=pred.index, y=pred.values, name="Forecast", line=dict(color="#eb6834", width=3)))
        fig.add_shape(type="line", x0=s.index[-1], x1=s.index[-1], y0=0, y1=1, yref="paper",
                      line=dict(dash="dot", color="grey"))
        fig.add_annotation(x=s.index[-1], y=1, yref="paper", text="Today", showarrow=False, yanchor="bottom")
        fig.update_layout(title=f"{label} forecast for {city}", hovermode="x unified")
        show(fig, h=470, legend="top")

        # ---- graphs 2-6 (graph 1 is the forecast line above)
        fut0, fut1 = pred.index[0], pred.index[-1]
        ly0, ly1 = fut0 - pd.Timedelta(days=365), fut1 - pd.Timedelta(days=365)
        fmt = lambda d: f"{d:%d %b %Y}"
        yrs = lambda x, y: str(x.year) if x.year == y.year else f"{x.year}-{y.year}"
        polluting = metric not in ("temp_avg_c", "humidity_avg")
        n_wk = int((pred.index - pd.to_timedelta(pred.index.weekday, unit="D")).nunique())
        hh = int(min(520, max(380, 36 * n_wk + 110)))

        g1, g2 = st.columns(2)
        with g1:
            calendar_heat(pred, f"Day-by-day outlook ({label})", h=hh)
            explain(f"Each box is **one day** of the forecast and each row is **one week** (Monday to Sunday). "
                    f"**Redder boxes = higher {label}**, paler boxes = lower. Hover over a box to see the exact value.")
        with g2:
            wk = pred.resample("W-SUN").mean()
            lyw = pd.Series(ly.values, index=pred.index).resample("W-SUN").mean()
            has_ly = bool(lyw.notna().any())
            fc_name, ly_name = f"Forecast {yrs(fut0, fut1)}", f"Actual, a year earlier ({yrs(ly0, ly1)})"
            wdf = pd.DataFrame({"week": wk.index.strftime("%d %b %Y"), fc_name: wk.values})
            if has_ly:
                wdf[ly_name] = lyw.values
            wl = wdf.melt(id_vars="week", var_name="series", value_name="v").dropna()
            fig = px.bar(wl, x="week", y="v", color="series", barmode="group",
                         color_discrete_map={fc_name: "#eb6834", ly_name: "#9aa5b5"},
                         title=f"Weekly average {label}: forecast vs a year earlier",
                         labels={"v": label, "week": "Week ending (Sunday)"})
            show(fig, h=hh)
            txt = (f"**Orange bars = the forecast** for {fmt(fut0)} to {fmt(fut1)}. "
                   f"**Grey bars = what really happened** on the same dates one year earlier "
                   f"({fmt(ly0)} to {fmt(ly1)}). Each pair is one week, averaged, and labelled with the date "
                   f"that week ends. Only the orange bars are predictions; the grey ones are real past data.")
            if has_ly:
                d = (float(pred.mean()) / float(np.nanmean(ly.values)) - 1) * 100
                word = ("more polluted" if d > 0 else "cleaner") if polluting else ("higher" if d > 0 else "lower")
                txt += (f" Overall the forecast is **{abs(d):.0f}% {'higher' if d > 0 else 'lower'}** than the same "
                        f"period last year" + (f" ({word})." if polluting else "."))
            explain(txt)

        g3, g4 = st.columns(2)
        with g3:
            if is_aqi:
                def shares(v):
                    c = pd.cut(pd.Series(np.asarray(v, dtype=float)), AQI_BINS, labels=AQI_LABELS)
                    return c.value_counts(normalize=True).reindex(AQI_LABELS).fillna(0) * 100
                periods = {"Past 12 months (actual)": s.iloc[-365:],
                           f"Last {horizon} days (actual)": s.iloc[-horizon:],
                           f"Next {horizon} days (forecast)": pred}
                t = pd.DataFrame([dict(period=k, category=c, share=sh)
                                  for k, v in periods.items() for c, sh in shares(v).items()])
                t = t[t.share > 0].copy()
                t["txt"] = np.where(t.share >= 6, t.share.round(0).astype(int).astype(str) + "%", "")
                fig = px.bar(t, x="share", y="period", color="category", orientation="h", text="txt",
                             color_discrete_map=AQI_COLORS,
                             category_orders={"category": AQI_LABELS, "period": list(periods)[::-1]},
                             title="Share of days in each AQI category",
                             labels={"share": "% of days", "period": "", "category": ""})
                fig.update_traces(textposition="inside")
                fig.update_xaxes(range=[0, 100])
                show(fig, h=380, legend="top")
                f_bad = float((pred > 100).mean() * 100)
                p_bad = float((s.iloc[-365:] > 100).mean() * 100)
                explain(f"Each bar is **100% of the days** in that period, split by AQI category. Compare the "
                        f"**forecast bar** with the two real-data bars: more orange and red means more unhealthy days "
                        f"than usual, more green and yellow means cleaner air. **{f_bad:.0f}%** of forecast days are "
                        f"above AQI 100 (unhealthy for sensitive groups or worse), against **{p_bad:.0f}%** over the "
                        f"past 12 months. Forecasts are averages, so they show fewer extreme days than real life will.")
            else:
                fig = px.histogram(x=pred.values, nbins=15, title=f"Spread of forecast {label}",
                                   labels={"x": label, "count": "days"})
                show(fig, h=380, legend="off")
                explain(f"Each bar counts **how many forecast days** fall in that range of {label}. A tall bar on the "
                        f"left means mostly low days, on the right mostly high days.")
        with g4:
            mo = s.groupby(s.index.month)
            mean, q10, q90 = mo.mean(), mo.quantile(0.1), mo.quantile(0.9)
            names = [calendar.month_abbr[m] for m in mean.index]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=names, y=q90.values, line=dict(width=0), showlegend=False, hoverinfo="skip"))
            fig.add_trace(go.Scatter(x=names, y=q10.values, fill="tonexty", fillcolor="rgba(42,120,214,.15)",
                                     line=dict(width=0), name="Usual range (10th-90th pct)"))
            fig.add_trace(go.Scatter(x=names, y=mean.values, name="Typical level", line=dict(color="#2a78d6", width=3)))
            fm = pred.groupby(pred.index.month).mean()
            fig.add_trace(go.Scatter(x=[calendar.month_abbr[m] for m in fm.index], y=fm.values, mode="markers",
                                     name="Forecast average", marker=dict(size=12, color="#eb6834", symbol="diamond")))
            fig.update_layout(title=f"A typical year of {label}, forecast marked")
            show(fig, h=380, legend="top")
            cmp = "; ".join(f"{calendar.month_name[int(m)]}: forecast {v:.0f} vs normal {mean[m]:.0f} "
                            f"({(v / mean[m] - 1) * 100:+.0f}%)" for m, v in fm.items() if mean.get(m, 0) > 0)
            explain(f"The **blue line** is the average {label} for each calendar month across all past years in the "
                    f"data. The **shaded area** is the usual range: on 8 days out of 10 the value stayed inside it. "
                    f"The **orange diamonds** are the forecast average for the months ahead. A diamond **above** the "
                    f"blue line means that month is expected to be higher than normal, **below** means lower. "
                    f"{cmp}.")

        # ---- graph 6: scroll back through the whole history
        st.markdown("##### Browse the full history")
        ymax = max(float(s.max()), float(hi.max())) * 1.1
        fig = go.Figure()
        if is_aqi:
            for lo_b, hi_b, lab in zip([0, 50, 100, 150, 200, 300], [50, 100, 150, 200, 300, 500], AQI_LABELS):
                if lo_b < ymax:
                    fig.add_hrect(y0=lo_b, y1=min(hi_b, ymax), fillcolor=AQI_COLORS[lab], opacity=0.10,
                                  line_width=0, annotation_text=lab, annotation_position="top left",
                                  annotation_font_size=10)
        fx = [s.index[-1]] + list(pred.index)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name="Past (real data)", line=dict(color="#2a78d6", width=1.6)))
        fig.add_trace(go.Scatter(x=pred.index, y=hi, line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=pred.index, y=lo, fill="tonexty", fillcolor="rgba(235,104,52,.20)",
                                 line=dict(width=0), name="Likely range (95%)"))
        fig.add_trace(go.Scatter(x=fx, y=[float(s.iloc[-1])] + list(pred.values), name="Forecast",
                                 line=dict(color="#eb6834", width=3)))
        fig.add_shape(type="line", x0=s.index[-1], x1=s.index[-1], y0=0, y1=1, yref="paper",
                      line=dict(dash="dot", color="grey"))
        fig.add_annotation(x=s.index[-1], y=1, yref="paper", text="Today", showarrow=False, yanchor="bottom")
        rng = lambda days: [str((s.index[-1] - pd.Timedelta(days=days)).date()), str(fut1.date())]
        fig.update_xaxes(range=rng(180), rangeslider=dict(visible=True, thickness=0.09))
        fig.update_yaxes(range=[0, ymax])
        fig.update_layout(
            title=f"{label} for {city}: full history and forecast", hovermode="x unified",
            updatemenus=[dict(type="buttons", direction="right", x=0, y=1.0, xanchor="left", yanchor="bottom",
                              showactive=False, pad=dict(t=2, b=6),
                              buttons=[dict(label=l, method="relayout", args=[{"xaxis.range": r}]) for l, r in [
                                  ("Last 3 months", rng(90)), ("Last 6 months", rng(180)),
                                  ("Last year", rng(365)),
                                  ("All history", [str(s.index[0].date()), str(fut1.date())])]])])
        show(fig, h=560, legend="topright")
        explain("This is the same forecast, but you can **travel back in time**. Drag the two handles on the small "
                "strip underneath the chart to choose which dates to look at, drag the middle of the strip to slide "
                "along the timeline, or use the buttons above the chart. The **blue line is real past data**, the "
                "dotted line marks today, and everything to its right is the **orange forecast** with its shaded "
                "likely range. Hover over any day to read its exact value.")

        st.caption("Forecasts use past patterns only. They cannot foresee sudden events such as crop burning or dust "
                   "storms, so treat long horizons as a rough guide.")

    # ------------------------------------------------------------ tab 2
    with t2:
        grade, color, pct, skill, best_base = verdict(tbl, model_name, float(test.mean()))
        mae = float(tbl.loc[model_name, "MAE"])
        line2 = ""
        if skill is not None:
            line2 = (f" It was <b>{abs(skill):.0f}% {'more' if skill > 0 else 'less'} accurate</b> than the best simple "
                     f"guess ({best_base.replace('Baseline: ', '').lower()}).")
        st.markdown(
            f'<div class="verdict" style="border-left:6px solid {color}"><div style="font-size:1.15rem;font-weight:700;'
            f'color:{color}">{grade}</div>On the last {hold} days, the forecast was off by <b>{mae:.1f}</b> '
            f'{label} on average, which is <b>{pct:.0f}%</b> of the typical level.{line2}</div>',
            unsafe_allow_html=True)

        a, b = st.columns(2)
        with a:
            t = tbl.reset_index()
            fig = px.bar(t, x="MAE", y="name", color="Type", orientation="h",
                         color_discrete_map={"Model": "#2a78d6", "Baseline": "#9aa5b5"},
                         title="Average miss per method (lower is better)", labels={"name": "", "MAE": "MAE"})
            fig.update_yaxes(autorange="reversed")
            show(fig, h=330)
        with b:
            st.markdown("**Score table**")
            disp = tbl[["Type", "MAE", "RMSE", "MAPE", "Bias"]].round(1).rename(columns={"MAPE": "MAPE %"})
            st.dataframe(disp, use_container_width=True)
            st.caption("MAE: average miss. RMSE: like MAE but punishes big misses. MAPE: miss as a percentage. "
                       "Bias: positive means the method tends to guess too high.")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=test.index, y=test.values, name="Real values", line=dict(color="#1b1f2a", width=2.5)))
        fig.add_trace(go.Scatter(x=preds[model_name].index, y=preds[model_name].values, name="Selected method",
                                 line=dict(color="#eb6834", width=2.5)))
        if best_base:
            fig.add_trace(go.Scatter(x=preds[best_base].index, y=preds[best_base].values, name="Best simple guess",
                                     line=dict(color="#8a94a6", dash="dot")))
        fig.update_layout(title=f"Test: forecast vs reality on the last {hold} days", hovermode="x unified")
        show(fig, h=380)

        err = preds[model_name] - test
        fig = go.Figure(go.Bar(x=err.index, y=err.values, marker_color=np.where(err.values >= 0, "#eb6834", "#2a78d6")))
        fig.add_hline(y=0, line_color="grey")
        fig.update_layout(title="Daily miss: forecast minus real (orange = guessed too high, blue = too low)")
        show(fig, h=320)

    # ------------------------------------------------------------ tab 3
    with t3:
        a, b = st.columns(2)
        with a:
            w = s.groupby(s.index.weekday).mean()
            fig = px.bar(x=[WEEKDAYS[i] for i in w.index], y=w.values, title="Typical level by weekday (past data)",
                         labels={"x": "", "y": label})
            show(fig, h=360, legend="off")
        with b:
            ym = s.groupby([s.index.year.rename("year"), s.index.month.rename("m")]).mean().reset_index(name="v")
            ym["month"] = ym.m.map(lambda m: calendar.month_abbr[int(m)])
            ym["year"] = ym.year.astype(str)
            fig = px.line(ym, x="month", y="v", color="year", markers=True,
                          title=f"{label}: each year, month by month", labels={"v": label, "month": ""})
            fig.update_xaxes(categoryorder="array", categoryarray=list(calendar.month_abbr)[1:])
            show(fig, h=360)

    # ------------------------------------------------------------ tab 4
    with t4:
        st.write("Run the selected method for every city and compare the projected average with the last 30 days.")
        key = (metric, horizon, model_name)
        if st.button("Run forecast for all cities"):
            rows = []
            with st.spinner("Forecasting every city..."):
                for cty in sorted(df.city.unique()):
                    try:
                        ss = build_series(df, cty, metric)
                        p = MODELS[model_name](ss, horizon)
                        rows.append(dict(city=cty, projected_avg=p.mean(), projected_peak=p.max(),
                                         last_30d_avg=ss.iloc[-30:].mean()))
                    except Exception:
                        pass
            lb = pd.DataFrame(rows).sort_values("projected_avg", ascending=False)
            lb["change_pct"] = (lb.projected_avg / lb.last_30d_avg - 1) * 100
            st.session_state["lb"] = (key, lb)
        saved = st.session_state.get("lb")
        if saved and saved[0] == key:
            lb = saved[1]
            top = lb.head(F["top_n"])
            show(px.bar(top, x="city", y=["last_30d_avg", "projected_avg"], barmode="group",
                        title=f"Last 30 days vs next {horizon} days ({label})",
                        labels={"value": label, "variable": "", "city": ""}), h=400)
            show(px.bar(lb.sort_values("change_pct"), x="change_pct", y="city", orientation="h",
                        title="Expected change vs last 30 days (%)", labels={"change_pct": "% change", "city": ""}),
                 h=max(320, 22 * len(lb) + 100))
            st.dataframe(lb.round(1), use_container_width=True)