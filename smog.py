"""
smog.py - "Smog Equivalency Calculator": turns PM2.5 into cigarettes smoked per day.

Rule of thumb (Berkeley Earth, Rohde & Muller 2015): a 24-hour average of 22 ug/m3 PM2.5 is
roughly the health burden of smoking 1 cigarette a day.  All colours / sizes live in theme.py
(.smog, .cigs, .cig classes), so this file only builds the content.

Used by the Overview tab in app.py:   render_smog_calculator(dflt)   # dflt = filtered daily dataframe
"""
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

CIG_UG = 22.0        # ug/m3 of PM2.5 (24 h average) per cigarette per day
WHO_24H = 15.0       # WHO 2021 24-hour PM2.5 guideline, ug/m3
MAX_ICONS = 30       # cigarette icons drawn before "+ N more"
LATEST, AVERAGE = "Latest day in the data", "Average of the current filters"

# US AQI <-> PM2.5 breakpoints, used only if the data has no PM2.5 column
_AQI_PTS = [0, 50, 51, 100, 101, 150, 151, 200, 201, 300, 301, 400, 401, 500]
_PM_PTS = [0, 12, 12.1, 35.4, 35.5, 55.4, 55.5, 150.4, 150.5, 250.4, 250.5, 350.4, 350.5, 500.4]


def find_pm25_col(df):
    """Best PM2.5 column: prefers a daily average/mean, skips max/min/std columns."""
    norm = {c: str(c).lower().replace("_", "").replace(".", "").replace(" ", "") for c in df.columns}
    cands = [c for c, n in norm.items() if "pm25" in n and not any(k in n for k in ("max", "min", "std"))]
    pref = [c for c in cands if any(k in norm[c] for k in ("avg", "mean"))]
    return (pref or cands or [None])[0]


def aqi_to_pm25(aqi):
    return np.interp(np.clip(aqi, 0, 500), _AQI_PTS, _PM_PTS)


def _fmt(x):
    return f"{x:,.1f}" if x < 10 else f"{x:,.0f}"


def _cig_icons(cigs):
    whole, frac = int(cigs), cigs - int(cigs)
    shown = min(whole, MAX_ICONS)
    html = '<span class="cig"><i style="width:100%"></i></span>' * shown
    if whole < MAX_ICONS and frac >= 0.05:
        html += f'<span class="cig"><i style="width:{frac * 100:.0f}%"></i></span>'
    if whole > MAX_ICONS:
        html += f'<span class="cigmore">+ {whole - MAX_ICONS:,} more</span>'
    return f'<div class="cigs">{html}</div>' if html else ""


def build_card(place, when, cigs, pm, estimated):
    if cigs < 0.5:
        phrase = "<b>less than half a cigarette</b>"
    else:
        phrase = f"<b>{_fmt(cigs)} cigarette{'s' if round(cigs, 1) != 1 else ''}</b>"
    src = "PM2.5 estimated from the US AQI" if estimated else "PM2.5 daily average"
    return (
        '<div class="smog"><div class="sk">SMOG EQUIVALENCY</div>'
        f'<div class="sbig">{when}, breathing the air in <b>{place}</b> was equivalent to smoking {phrase} in a day.</div>'
        f'{_cig_icons(cigs)}'
        f'<div class="sn">{src}: {pm:,.0f} µg/m³. Rule of thumb (Berkeley Earth): 22 µg/m³ of PM2.5 over 24 hours ≈ '
        '1 cigarette a day. A simplified illustration, not a medical measurement: smoke and city air are not '
        'identical, and real exposure depends on time spent indoors and outdoors.</div></div>')


def build_kpis(cigs, pm):
    def kc(label, value, sub):
        return f'<div class="kc"><div class="kl">{label}</div><div class="kv">{value}</div><div class="ks">{sub}</div></div>'
    return ('<div class="kgrid">'
            + kc("Cigarettes per day", _fmt(cigs), f"at {pm:,.0f} µg/m³ PM2.5")
            + kc("In a month", _fmt(cigs * 30), "if the air stayed like this")
            + kc("In a year", _fmt(cigs * 365), "cigarettes, same assumption")
            + kc("× WHO daily limit", f"{pm / WHO_24H:,.1f}×", "WHO guideline: 15 µg/m³ per day")
            + '</div>')


def render_smog_calculator(d):
    if d is None or len(d) == 0:
        return
    col = find_pm25_col(d)
    if col:
        pm = pd.to_numeric(d[col], errors="coerce")
        estimated = False
    else:
        pm = pd.Series(aqi_to_pm25(pd.to_numeric(d["us_aqi_avg"], errors="coerce").to_numpy()), index=d.index)
        estimated = True
    d = d.assign(_pm=pm).dropna(subset=["_pm"])
    if d.empty:
        return

    st.subheader("Smog equivalency calculator")
    cities = sorted(d["city"].dropna().unique())
    options = ["All cities"] + cities
    if st.session_state.get("smog_city") not in options:
        st.session_state.pop("smog_city", None)
    c1, c2 = st.columns(2)
    place = c1.selectbox("City", options, index=options.index("Lahore") if "Lahore" in options else 0,
                         key="smog_city")
    basis = c2.selectbox("Based on", [LATEST, AVERAGE], key="smog_basis")

    latest = d.sort_values("date").groupby("city").tail(1)
    if basis == LATEST:
        per_city = latest.set_index("city")["_pm"]
        if place == "All cities":
            day = d["date"].max()
            value, when = d.loc[d["date"] == day, "_pm"].mean(), f"On {day:%d %b %Y}"
        else:
            row = latest[latest["city"] == place].iloc[0]
            value, when = float(row["_pm"]), f"On {row['date']:%d %b %Y}"
    else:
        per_city = d.groupby("city")["_pm"].mean()
        value = float(d["_pm"].mean() if place == "All cities" else per_city.get(place, np.nan))
        when = "On an average day"
    if not np.isfinite(value):
        st.info("No PM2.5 reading for this selection.")
        return
    cigs = value / CIG_UG

    st.markdown(build_card("Pakistan's monitored cities" if place == "All cities" else place, when, cigs, value,
                           estimated), unsafe_allow_html=True)
    st.markdown(build_kpis(cigs, value), unsafe_allow_html=True)

    top = (per_city / CIG_UG).sort_values(ascending=False).head(10).sort_values().reset_index()
    top.columns = ["city", "cigs"]
    fig = px.bar(top, x="cigs", y="city", orientation="h", text=top["cigs"].map(lambda v: f"{v:.1f}"),
                 title="Cigarettes per day by city (10 worst in the current selection)")
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(height=360, margin=dict(l=10, r=30, t=50, b=10), xaxis_title="Cigarettes per day",
                      yaxis_title=None)
    try:
        st.plotly_chart(fig, width="stretch")
    except TypeError:          # older Streamlit
        st.plotly_chart(fig, use_container_width=True)


def run_overview_with_smog(page_fn, d, *args):
    """Run an overview page function and show the calculator right after its first KPI-card grid
    (the first st.markdown whose HTML contains class="kgrid"). If no grid is found the calculator is
    shown at the end instead, so it never goes missing.  No changes to the page file are needed."""
    state = {"done": False}
    original = st.markdown

    def patched(body="", *a, **k):
        out = original(body, *a, **k)
        if not state["done"] and isinstance(body, str) and 'class="kgrid"' in body:
            state["done"] = True
            st.markdown = original          # restore first so the calculator draws normally
            render_smog_calculator(d)
            st.markdown = patched
        return out

    st.markdown = patched
    try:
        page_fn(*args)
    finally:
        st.markdown = original
    if not state["done"]:
        render_smog_calculator(d)