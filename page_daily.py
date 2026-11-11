"""
page_daily.py - built from  pakistan_air_quality_daily.csv
    * page_daily()     -> "Daily Air Quality" page
    * page_forecast()  -> "Forecasting" page
"""
import calendar

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import charts as ch
from common import (AQI_BINS, AQI_COLORS, AQI_LABELS, AQI_SCALE_MAX, ATM, F, WHO_24H, WHO_PM25_24H, WHO_PM25_ANNUAL,
                    aqi_cat, explain, fmt_aqi, insights, kpis, need, season_sort, show, table)

NEUTRAL_BLUE = "#4f6d8f"

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    HAS_SM = True
except Exception:
    HAS_SM = False


# ----------------------------------------------------------------------------
# DAILY AIR QUALITY  (pollution and weather, follows the sidebar filters)
#   1 week-by-week AQI in chosen cities      2 the 10 worst days         3 each pollutant vs its WHO limit
#   4 rain                                    5 wind                      6 temperature
#   7 humidity                                8 mix of good and bad days per city
#   9 haze in the sky by month               10 which pollutants jump in winter
# ----------------------------------------------------------------------------
def page_daily(df):
    st.header("Daily Air Quality & Weather")
    need(df, ["date", "city", "province", "pm2_5_avg", "us_aqi_avg"], "pakistan_air_quality_daily")
    f = df
    if f.empty:
        st.warning("No data for the selected filters.")
        return
    city_aqi = f.groupby("city").us_aqi_avg.mean().sort_values(ascending=False)
    top_cities = city_aqi.head(F["top_n"]).index.tolist()
    worst = f.loc[f.us_aqi_avg.idxmax()]
    pm = f.pm2_5_avg.mean()
    over_who = (f.pm2_5_avg > WHO_PM25_24H).mean() * 100
    kpis([
        ("Average US AQI", f"{f.us_aqi_avg.mean():.0f}", aqi_cat(f.us_aqi_avg.mean())),
        ("Average PM2.5", f"{pm:.1f}", f"µg/m³ · {over_who:.0f}% of days above the WHO limit"),
        ("Unhealthy days", f"{(f.us_aqi_avg > 150).mean() * 100:.0f}%", "AQI above 150"),
        ("Most polluted city", city_aqi.index[0], f"average AQI {city_aqi.iloc[0]:.0f}"),
        ("Worst day", f"{fmt_aqi(worst.us_aqi_avg)} AQI", f"{worst.city} · {worst.date:%d %b %Y}"),
    ])

    # weather effects, computed once for the insights and charts
    rain = None
    if "rain_mm" in f.columns:
        rain = f.groupby(pd.cut(f.rain_mm, [-0.01, 0.0, 5, 1e9],
                                labels=["No rain", "Light rain (up to 5 mm)", "Heavy rain (over 5 mm)"]),
                         observed=False).pm2_5_avg.mean()
    wind = None
    if "wind_category" in f.columns:
        order = [w for w in ["Stagnant (<5 km/h)", "Light (5-12 km/h)", "Breezy (12+ km/h)"]
                 if w in set(f.wind_category)]
        wind = f.groupby("wind_category").pm2_5_avg.mean().reindex(order)
    temp = None
    if "temp_avg_c" in f.columns:
        temp = f.groupby(pd.cut(f.temp_avg_c, [-50, 10, 20, 30, 60],
                                labels=["Cold (below 10°C)", "Cool (10-20°C)", "Warm (20-30°C)", "Hot (above 30°C)"]),
                         observed=False).pm2_5_avg.mean()
    hum = None
    if "humidity_avg" in f.columns:
        hum = f.groupby(pd.cut(f.humidity_avg, [-1, 40, 70, 101],
                               labels=["Dry (under 40%)", "Medium (40-70%)", "Humid (over 70%)"]),
                        observed=False).pm2_5_avg.mean()
    ins = []
    if wind is not None and len(wind.dropna()) > 1:
        ins.append(f"Still air traps pollution: PM2.5 is **{wind.iloc[0]:.0f}** µg/m³ when the wind is under 5 km/h "
                   f"but **{wind.iloc[-1]:.0f}** when it is breezy.")
    if temp is not None and temp.notna().sum() > 1:
        tt_ = temp.dropna()
        ins.append(f"PM2.5 is highest on **{str(tt_.idxmax()).split(' (')[0].lower()}** days "
                   f"({tt_.max():.0f} µg/m³) and lowest on **{str(tt_.idxmin()).split(' (')[0].lower()}** days "
                   f"({tt_.min():.0f}).")
    if rain is not None and rain.notna().sum() > 1:
        rr_ = rain.dropna()
        ch_r = (rr_.iloc[-1] / rr_.iloc[0] - 1) * 100
        ins.append(f"Heavy-rain days have **{abs(ch_r):.0f}% {'less' if ch_r < 0 else 'more'}** PM2.5 than dry days "
                   f"(rain falls mostly in cleaner months, so part of this is the season).")
    insights(ins)

    # 1
    sel = F["trend_cities"] or top_cities[:5]
    wk = (f[f.city.isin(sel)].assign(m=f.date.dt.to_period("M").dt.to_timestamp())
          .groupby(["m", "city"]).us_aqi_avg.mean().unstack())
    ch.lines(wk.index, {c: wk[c].values for c in wk.columns}, "1. Month by month in the cities you pick",
             y_title="AQI", ref=[(150, "Unhealthy above this line", "#d64545")], h=400)
    ch.note("Each line is one city's **monthly average AQI**. Choose the cities in the sidebar under "
            "*Cities (trend chart)*.")

    # 2 + 3
    a, b = st.columns(2)
    with a:
        w10 = f.nlargest(10, "us_aqi_avg")
        ch.bar([f"{r.city} · {r.date:%d %b %Y}" for r in w10.itertuples()], w10.us_aqi_avg.values,
               "2. The 10 worst days in the data", scale="aqi",
               text=[fmt_aqi(v) for v in w10.us_aqi_avg.values], key_note=False)
        ch.note("The single days with the **highest average AQI**. A * means the value is above the top of the "
                "official 500 scale (desert dust).")
    with b:
        rows = [(lab, f[col].mean() / lim) for col, (lab, lim) in WHO_24H.items() if col in f.columns]
        rows.sort(key=lambda r: -r[1])
        ch.bar([r[0] for r in rows], [r[1] for r in rows], "3. How far above the WHO safe limit is each pollutant?",
               scale=["#d64545" if r[1] > 1 else "#1e9e5a" for r in rows], fmt="{:.1f}", suffix="×",
               ref=[(1, "safe limit", "#1e9e5a")], key_note=False)
        ch.note("**1× = exactly at the WHO daily safe limit** (green dashed line). Red bars are above it, green bars "
                "are within it.")

    # 4-7 weather
    a, b = st.columns(2)
    with a:
        if rain is not None:
            ch.bar(rain.index, rain.values, "4. Does rain clean the air?", horizontal=False, scale="pm25",
                   suffix="", key_note=False, y_title="PM2.5 (µg/m³)")
            ch.note("Average PM2.5 on days with no rain, light rain and heavy rain.")
    with b:
        if wind is not None:
            ch.bar([w.split(" (")[0] + " wind" for w in wind.index], wind.values, "5. Does wind blow pollution away?",
                   horizontal=False, scale="pm25", key_note=False, y_title="PM2.5 (µg/m³)")
            ch.note("Average PM2.5 when the air is still (under 5 km/h), light (5-12) and breezy (over 12).")
    a, b = st.columns(2)
    with a:
        if temp is not None:
            ch.bar(temp.index, temp.values, "6. Is the air worse when it is cold?", horizontal=False, scale="pm25",
                   key_note=False, y_title="PM2.5 (µg/m³)")
            ch.note("Average PM2.5 by daily temperature. The worst air comes on **cool winter days** in the plains; the "
                    "very coldest days are mostly in the clean northern mountains.")
    with b:
        if hum is not None:
            ch.bar(hum.index, hum.values, "7. Does humid air hold more pollution?", horizontal=False, scale="pm25",
                   key_note=False, y_title="PM2.5 (µg/m³)")
            ch.note("Average PM2.5 by how humid the day was. Moist winter fog mixes with smoke to form smog.")
    ch.legend_note("pm25")

    # 8
    g = f[f.city.isin(top_cities)].assign(grp=pd.cut(f.us_aqi_avg, [-1, 100, 150, 200, 1e9],
                                                     labels=["Safe", "Unhealthy for sensitive groups", "Unhealthy",
                                                             "Very unhealthy or worse"]))
    t = g.groupby(["city", "grp"], observed=False).size().unstack(fill_value=0).reindex(top_cities)
    t = t.div(t.sum(axis=1), axis=0) * 100
    ch.stacked(top_cities, {c: t[c].values for c in t.columns},
               f"8. Good and bad days in the {len(top_cities)} most polluted cities",
               colors={"Safe": "#1e9e5a", "Unhealthy for sensitive groups": "#ff7e00", "Unhealthy": "#d64545",
                       "Very unhealthy or worse": "#8f3f97"})
    ch.note("Each bar is **100% of a city's days**, split by how bad the air was. More green = more safe days.")

    # 9 + 10
    a, b = st.columns(2)
    with a:
        if "aod_avg" in f.columns:
            hz = f.groupby(f.date.dt.month).aod_avg.mean()
            ch.bar([calendar.month_abbr[int(i)] for i in hz.index], hz.values, "9. How hazy is the sky each month?",
                   horizontal=False, scale=NEUTRAL_BLUE, fmt="{:.2f}", key_note=False, y_title="haze level")
            ch.note("Haze level (aerosol optical depth): how much sunlight is blocked by particles in the whole sky. "
                    "**Higher = hazier.** Above 0.5 the sky looks visibly milky.")
    with b:
        win_ = f[f.date.dt.month.isin([11, 12, 1])]
        sum_ = f[f.date.dt.month.isin([5, 6])]
        rows = [(lab, win_[col].mean() / sum_[col].mean()) for col, (lab, _) in WHO_24H.items()
                if col in f.columns and len(win_) and len(sum_) and sum_[col].mean() > 0]
        if rows:
            rows.sort(key=lambda r: -r[1])
            ch.bar([r[0] for r in rows], [r[1] for r in rows], "10. Which pollutants jump in winter?",
                   scale=["#2a78d6" if r[1] >= 1 else "#e8a33d" for r in rows], fmt="{:.1f}", suffix="×",
                   ref=[(1, "same as summer", "#7a8496")], key_note=False)
            ch.note("Winter (Nov-Jan) level divided by summer (May-Jun) level; the grey dashed line is 'same as "
                    "summer'. **Blue = higher in winter** "
                    "(smoke from burning and heating, trapped by cold air); amber = higher in summer (dust and "
                    "sun-made ozone).")
        else:
            st.info("Needs both winter and summer months in the filters.")


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
SHORT_CAT = {"Unhealthy for Sensitive Groups": "Sensitive", "Very Unhealthy": "V. Unhealthy"}   # fits a KPI card


def build_series(df, city, metric):
    f = df if city == "All cities (average)" else df[df.city == city]
    s = f.groupby("date")[metric].mean().sort_index()
    return s.asfreq("D").interpolate(limit=7).ffill().bfill()


def _windows(s, hold):
    """Test windows (start positions) for the backtest.
    1. the most recent `hold` days (how the methods do right now), and
    2. the same calendar window 1 and 2 years earlier, starting the day after the last data date
       (how the methods do in the season the forecast is about to enter, e.g. the start of smog season)."""
    last = s.index[-1]
    starts = [len(s) - hold]
    for yrs in (1, 2):
        origin = last - pd.Timedelta(days=365 * yrs)
        pos = int(s.index.searchsorted(origin)) + 1
        if pos >= 300 and pos + hold <= len(s) - hold:   # enough history to train, no overlap with window 1
            starts.append(pos)
    return starts


def backtest(s, hold):
    """Hide `hold` days, forecast them with every method, and score against reality.
    Done on several windows (see _windows) and averaged, so one calm or unusual month cannot decide
    which method is "best". The charts on the accuracy tab show the most recent window."""
    starts = _windows(s, hold)
    jobs = [(n, f, "Model") for n, f in MODELS.items()] + [(n, f, "Baseline") for n, f in BASELINES.items()]
    scores, preds, tests = {}, {}, []
    for k, st0 in enumerate(starts):
        train, test = s.iloc[:st0], s.iloc[st0:st0 + hold]
        tests.append(test)
        for name, fn, kind in jobs:
            try:
                p = fn(train, hold)
                if p.isna().all():
                    continue
                e = p.values - test.values
                scores.setdefault((name, kind), []).append(
                    (np.abs(e).mean(), (e ** 2).mean(), np.mean(np.abs(e) / np.maximum(test.values, 1)) * 100, e.mean()))
                if k == 0:
                    preds[name] = p
            except Exception:
                pass
    rows = []
    for (name, kind), v in scores.items():
        if len(v) < len(starts) or name not in preds:   # must work on every window to be ranked fairly
            continue
        a = np.array(v)
        rows.append(dict(name=name, Type=kind, MAE=a[:, 0].mean(), RMSE=np.sqrt(a[:, 1].mean()), MAPE=a[:, 2].mean(),
                         Bias=a[:, 3].mean()))
    tbl = pd.DataFrame(rows).set_index("name").sort_values("MAE") if rows else pd.DataFrame()
    level = float(pd.concat(tests).mean())
    return tbl, preds, tests[0], len(starts), level


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


def aqi_bands(fig, ymax):
    """Shade the US AQI bands; label a band only when it is tall enough for the label to be readable."""
    for lo_b, hi_b, lab in zip([0, 50, 100, 150, 200, 300], [50, 100, 150, 200, 300, 500], AQI_LABELS):
        if lo_b < ymax:
            top = min(hi_b, ymax)
            label = (dict(annotation_text=lab, annotation_position="top left", annotation_font_size=10)
                     if (top - lo_b) >= ymax * 0.07 else {})
            fig.add_hrect(y0=lo_b, y1=top, fillcolor=AQI_COLORS[lab], opacity=0.10, line_width=0, **label)


def last_data_marker(fig, x):
    """Dotted line on the last day with real data, labelled at the bottom so it never hits the legend."""
    fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, yref="paper", line=dict(dash="dot", color="grey"))
    fig.add_annotation(x=x, y=0, yref="paper", text=f"Last data ({x:%d %b})", showarrow=False, xanchor="right",
                       yanchor="bottom", font=dict(size=10, color="#555"), bgcolor="rgba(255,255,255,.7)")


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

**Test window (days)** is how the page checks itself. It hides N days of real data, forecasts them, and
compares the forecast with what really happened. This is done on the most recent N days **and** on the same
dates one and two years earlier (the season the forecast is heading into), and the errors are averaged.

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
    hold = c4.slider("Test window (days)", 14, 90, 30,
                     help="Days hidden from the methods to test how accurate they are (recent days, plus the same "
                          "dates in earlier years).")
    label = METRIC_LABELS[metric]

    s = build_series(df, city, metric)
    if len(s) < hold + 60:
        st.warning("Not enough history for this selection. Try a shorter backtest window or another city.")
        return
    tbl, preds, test, n_win, level = backtest(s, hold)
    ok = [n for n in tbl.index if n in MODELS] if len(tbl) else []
    if not ok:
        st.error("No forecasting method could be fitted on this series.")
        return
    model_name = st.selectbox("Forecasting method (best performer first)", ok,
                              help="Methods are ranked by their average error over the test windows.")
    win_txt = (f"{n_win} test windows of {hold} days (the most recent one, plus the same dates in "
               f"{'the previous year' if n_win == 2 else 'each of the previous two years'})" if n_win > 1
               else f"the last {hold} days")
    pred = MODELS[model_name](s, horizon)
    rmse = float(tbl.loc[model_name, "RMSE"])
    width = 1.96 * rmse * np.sqrt(1 + np.arange(horizon) / max(hold, 1) * 0.15)
    lo, hi = np.clip(pred.values - width, 0, None), pred.values + width
    is_aqi = metric == "us_aqi_avg"
    if is_aqi:
        ATM["aqi"], ATM["src"] = float(pred.mean()), "forecast"
        st.session_state["forecast_aqi"] = ATM["aqi"]
    else:
        st.session_state.pop("forecast_aqi", None)   # background follows the filters for non-AQI measures
    last_day = s.index[-1]
    st.info(f"The data ends on **{last_day:%d %b %Y}**, so the forecast starts on **{pred.index[0]:%d %b %Y}**. "
            f"Days that have already passed are still forecasts, not measurements. Refresh the data file to move "
            f"the starting point forward.")

    pk = pred.idxmax()
    kpis([
        ("First forecast day", f"{pred.iloc[0]:.0f}",
         f"{pred.index[0]:%d %b %Y}" + (f" · {aqi_cat(pred.iloc[0])}" if is_aqi else "")),
        (f"Average, next {horizon} days", f"{pred.mean():.0f}",
         f"{(pred.mean() / s.iloc[-horizon:].mean() - 1) * 100:+.0f}% vs the last {horizon} days"),
        ("Expected peak", f"{pred.max():.0f}", f"on {pk:%d %b %Y}"),
        ("Peak-day category" if is_aqi else "Expected low",
         SHORT_CAT.get(aqi_cat(pred.max()), aqi_cat(pred.max())) if is_aqi else f"{pred.min():.0f}",
         aqi_cat(pred.max()) if is_aqi else f"on {pred.idxmin():%d %b %Y}"),
        ("Typical miss", f"{tbl.loc[model_name, 'MAE']:.1f}", f"{label} points, in testing"),
    ])
    ly = s.reindex(pred.index - pd.Timedelta(days=365))
    fut0, fut1 = pred.index[0], pred.index[-1]

    # ================================================================ THE FORECAST
    st.subheader("The forecast")
    # 1. forecast line with history (buttons and slider to look further back)
    hist_from = s.index[-1] - pd.Timedelta(days=180)
    ymax = max(float(s.max()), float(hi.max())) * 1.1
    fig = go.Figure()
    if is_aqi:
        aqi_bands(fig, ymax)
    fig.add_trace(go.Scatter(x=s.index, y=s.values, name="Real past values", line=dict(color="#2a78d6", width=1.8)))
    fig.add_trace(go.Scatter(x=pred.index, y=hi, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=pred.index, y=lo, fill="tonexty", fillcolor="rgba(235,104,52,.20)", line=dict(width=0),
                             name="Likely range"))
    if ly.notna().any():
        fig.add_trace(go.Scatter(x=pred.index, y=ly.values, name="Same dates last year",
                                 line=dict(color="#8a94a6", dash="dot", width=1.6)))
    fig.add_trace(go.Scatter(x=[s.index[-1]] + list(pred.index), y=[float(s.iloc[-1])] + list(pred.values),
                             name="Forecast", line=dict(color="#eb6834", width=3.2)))
    last_data_marker(fig, s.index[-1])
    rng = lambda days: [str((s.index[-1] - pd.Timedelta(days=days)).date()), str(fut1.date())]
    fig.update_xaxes(range=[str(hist_from.date()), str(fut1.date())], rangeslider=dict(visible=True, thickness=0.07))
    fig.update_yaxes(range=[0, ymax])
    fig.update_layout(title=f"1. {label} forecast for {city}", hovermode="x unified",
                      updatemenus=[dict(type="buttons", direction="right", x=0, y=1.0, xanchor="left",
                                        yanchor="bottom", showactive=False, pad=dict(t=2, b=6),
                                        buttons=[dict(label=l, method="relayout", args=[{"xaxis.range": r}])
                                                 for l, r in [("3 months", rng(90)), ("6 months", rng(180)),
                                                              ("1 year", rng(365)),
                                                              ("All", [str(s.index[0].date()), str(fut1.date())])]])])
    show(fig, h=520, legend="topright")
    explain("**Blue = what really happened, orange = the forecast**, and the shaded band is the likely range. The "
            "dotted grey line is the same dates last year. Use the buttons or the strip under the chart to look "
            "further back.")

    # 2. next 7 days as tiles
    first7 = pred.iloc[:7]
    ch.tiles([(f"{d:%a %d %b}", f"{v:.0f}", aqi_cat(v) if is_aqi else label,
               AQI_COLORS.get(aqi_cat(v), "#5b6b82") if is_aqi else "#5b6b82") for d, v in first7.items()],
             f"2. The first 7 forecast days at a glance ({label})")

    a, b = st.columns(2)
    # 3. weekly forecast vs a year earlier
    with a:
        wk = pred.resample("W-SUN").mean()
        lyw = pd.Series(ly.values, index=pred.index).resample("W-SUN").mean()
        series = {"Forecast": wk.values}
        if lyw.notna().any():
            series["Same weeks last year (real)"] = lyw.values
        ch.grouped([f"w/e {d:%d %b}" for d in wk.index], series, f"3. Week by week: forecast vs last year",
                   colors=["#eb6834", "#9aa5b5"], y_title=label)
        if lyw.notna().any():
            dd = (float(pred.mean()) / float(np.nanmean(ly.values)) - 1) * 100
            explain(f"Orange = weekly average forecast, grey = what really happened in the same weeks last year. "
                    f"Overall the forecast is **{abs(dd):.0f}% {'higher' if dd > 0 else 'lower'}** than last year.")
        else:
            explain("Weekly average of the forecast (no data for the same weeks last year).")
    # 4. share of days by category
    with b:
        if is_aqi:
            def shares(v):
                c = pd.cut(pd.Series(np.asarray(v, dtype=float)), [-1, 100, 150, 1e9],
                           labels=["Safe (up to 100)", "Unhealthy for sensitive groups", "Unhealthy or worse"])
                return c.value_counts(normalize=True).reindex(c.cat.categories).fillna(0) * 100
            periods = {"Past 12 months": s.iloc[-365:], f"Last {horizon} days": s.iloc[-horizon:],
                       f"Next {horizon} days (forecast)": pred}
            sh = {k: shares(v) for k, v in periods.items()}
            parts = {c: [sh[k][c] for k in periods] for c in sh[list(periods)[0]].index}
            ch.stacked(list(periods), parts, "4. How many days will be safe?",
                       colors={"Safe (up to 100)": "#1e9e5a", "Unhealthy for sensitive groups": "#ff7e00",
                               "Unhealthy or worse": "#d64545"}, h=330)
            explain("Each bar is 100% of the days in that period. Compare the **forecast** with the real past. "
                    "Forecasts are averages, so real life will have a few more extreme days.")
        else:
            vals = [s.iloc[-365:].mean(), s.iloc[-horizon:].mean(), pred.mean()]
            ch.bar(["Past 12 months", f"Last {horizon} days", f"Next {horizon} days (forecast)"], vals,
                   f"4. Average {label}: past and forecast", horizontal=False, scale=["#9aa5b5", "#5b6b82", "#eb6834"],
                   key_note=False, fmt="{:.1f}")
            explain("The average over the past year, the last few weeks, and the forecast period.")

    # 5. forecast months vs their usual level
    mo = s.groupby(s.index.month).mean()
    fm = pred.groupby(pred.index.month).mean()
    months = list(dict.fromkeys(pred.index.month))
    ch.grouped([calendar.month_name[m] for m in months],
               {"Usual for this month (past years)": [mo.get(m, np.nan) for m in months],
                "Forecast": [fm[m] for m in months]},
               "5. Will the coming months be better or worse than usual?", colors=["#9aa5b5", "#eb6834"],
               y_title=label, h=340)
    explain("Grey = the normal level for that month in past years, orange = the forecast. **Orange taller than grey "
            "means worse than usual.**")
    st.caption("Forecasts use past patterns only. They cannot foresee sudden events such as crop burning or dust "
               "storms, so treat long horizons as a rough guide.")

    # ================================================================ CAN WE TRUST IT?
    st.subheader("Can we trust this forecast?")
    grade, color, pct, skill, best_base = verdict(tbl, model_name, level)
    mae = float(tbl.loc[model_name, "MAE"])
    line2 = ""
    if skill is not None:
        line2 = (f" It was <b>{abs(skill):.0f}% {'more' if skill > 0 else 'less'} accurate</b> than the best simple "
                 f"guess ({best_base.replace('Baseline: ', '').lower()}).")
    st.markdown(
        f'<div class="verdict" style="border-left:6px solid {color}"><div style="font-size:1.15rem;font-weight:700;'
        f'color:{color}">{grade}</div>Tested on {win_txt}, the method was off by <b>{mae:.1f}</b> '
        f'{label} on average, which is <b>{pct:.0f}%</b> of the typical level.{line2}</div>',
        unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:   # 6
        t = tbl.reset_index()
        ch.bar([n.replace("Baseline: ", "Simple guess: ") for n in t["name"]], t.MAE.values,
               "6. Average miss of each method (shorter is better)",
               scale=["#2a78d6" if k == "Model" else "#b8c2d1" for k in t.Type], fmt="{:.1f}", key_note=False,
               highlight=None)
        explain("How far off each method was, on average, when tested on days it had not seen. Blue = forecasting "
                "methods, grey = simple guesses. A good method beats the simple guesses.")
    with b:   # 7
        series = {"What really happened": test.values, "Selected method": preds[model_name].values}
        if best_base:
            series["Best simple guess"] = preds[best_base].values
        ch.lines(test.index, series, f"7. Test run: forecast vs reality ({hold} days)",
                 colors=["#1b1f2a", "#eb6834", "#9aa5b5"], dashes={"Best simple guess": "dot"}, y_title=label)
        explain("The method was asked to forecast days it had not seen. **The closer the orange line follows the "
                "black line, the better.**")
    with st.expander("Detailed score table"):
        disp = tbl[["Type", "MAE", "RMSE", "MAPE", "Bias"]].round(1).rename(columns={"MAPE": "MAPE %"})
        table(disp)
        st.caption("MAE: average miss. RMSE: like MAE but punishes big misses. MAPE: miss as a percentage. "
                   "Bias: positive means the method tends to guess too high.")

    # ================================================================ PATTERNS
    st.subheader("Patterns the forecast learns from")
    a, b = st.columns(2)
    with a:   # 8
        band = pd.Series(hi - lo, index=pred.index).resample("W-SUN").mean() / 2
        ch.bar([f"Week {i + 1}" for i in range(len(band))], band.values,
               "8. How sure is the forecast further ahead?", horizontal=False, scale="#eb6834", fmt="± {:.0f}",
               key_note=False, y_title=f"± {label}")
        explain(f"The likely range around the forecast, week by week. **A bigger number means less certainty**: "
                f"in week 1 the real value should usually be within ± {band.iloc[0]:.0f} of the forecast.")
    with b:   # 9
        ym = s.groupby([s.index.year, s.index.month]).mean()
        yrs_ = sorted(set(ym.index.get_level_values(0)))
        mnames = list(calendar.month_abbr)[1:]
        ch.lines(mnames, {str(y): [ym.get((y, m), np.nan) for m in range(1, 13)] for y in yrs_},
                 f"9. Every year, month by month", y_title=label, markers=True,
                 colors=["#b8c2d1", "#7a8496", "#2a78d6", "#d64545", "#eb6834"])
        explain("One line per year. If the lines rise and fall together, the season is predictable, which helps "
                "the forecast.")

    # ================================================================ ALL CITIES
    st.subheader("All cities")
    lb = all_city_forecast(df, metric, horizon, model_name)
    if len(lb):   # 10
        lb = lb.sort_values("change_pct", ascending=False)
        ch.bar(lb.city, lb.change_pct.values, f"10. Next {horizon} days vs the last 30 days, every city",
               scale=["#d64545" if v > 0 else "#1e9e5a" for v in lb.change_pct], fmt="{:+.0f}", suffix="%",
               key_note=False, value_range=[min(0, float(lb.change_pct.min()) * 1.25),
                                            max(0, float(lb.change_pct.max()) * 1.25)])
        explain(f"Using the selected method for every city. **Red = expected to get worse**, green = expected to "
                f"improve, compared with each city's last 30 days of data.")
        with st.expander("Table for all cities"):
            table(lb.rename(columns={"city": "City", "projected_avg": f"Next {horizon} days (avg)",
                                     "projected_peak": "Expected peak", "last_30d_avg": "Last 30 days (avg)",
                                     "change_pct": "Change %"}).round(1), hide_index=True)
    else:
        st.info("The selected method could not be fitted for the cities.")


@st.cache_data(show_spinner="Forecasting every city...")
def all_city_forecast(df, metric, horizon, model_name):
    rows = []
    for cty in sorted(df.city.unique()):
        try:
            ss = build_series(df, cty, metric)
            p = MODELS[model_name](ss, horizon)
            rows.append(dict(city=cty, projected_avg=p.mean(), projected_peak=p.max(), last_30d_avg=ss.iloc[-30:].mean()))
        except Exception:
            pass
    lb = pd.DataFrame(rows, columns=["city", "projected_avg", "projected_peak", "last_30d_avg"])
    lb["change_pct"] = (lb.projected_avg / lb.last_30d_avg - 1) * 100
    return lb
